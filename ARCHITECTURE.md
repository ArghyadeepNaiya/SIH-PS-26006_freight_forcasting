# ARCHITECTURE.md

Intelligent Freight Forecasting and Charter Decision System

---

## 1. Architectural principle

Split the work into what runs overnight and what runs when the user clicks.

Overnight, we pull data, engineer features, retrain models and pre compute forecasts
for every vessel class at every horizon. On click, we do lookups and arithmetic only.

This is the decision that makes the demo instant instead of laggy, and it is worth
stating explicitly during judging.

---

## 2. Services

There are three services and one database.

1. Web. React. Talks only to the Express gateway.
2. API. Node and Express. Handles requests, persistence, and calls the ML service.
3. ML. Python and FastAPI. Holds forecasting, constraints, capacity and cost logic.
4. Database. MongoDB.

Why React does not call Python directly. A single entry point keeps request logging,
scenario saving and future authentication in one place. Say this in one sentence at
judging and a security minded evaluator will notice.

---

## 3. Nightly batch pipeline

Runs on a schedule. Also runnable manually by command.

1. Ingest freight rate history for each vessel class from the configured source file
   or API.
2. Ingest commodity prices, bunker prices and economic indicators.
3. Ingest published port position reports to derive a congestion proxy.
4. Validate and deduplicate. Reject rows outside plausible ranges.
5. Build the feature matrix. Lags, rolling means, rolling volatility, day of week,
   month, and exogenous series.
6. Train the naive baseline, the statistical model and the gradient boosted model.
7. Evaluate with expanding window time series cross validation. Compute skill score
   against naive persistence at every horizon.
8. Persist trained models to disk and forecasts to MongoDB.
9. Write a run record with timestamps, row counts and metric values.

---

## 4. Request time pipeline

Target latency under one second.

Step 1. Candidate generation.
Take the cargo quantity and origin. Build every combination of vessel class and East
Coast discharge port. Four classes by seven ports gives under thirty candidates.

Step 2a. Operator declaration check.
Ask the operator of that port what they are offering this class of ship over the
arrival window. Three answers are possible. No declaration, in which case the
pipeline proceeds on published and assumed reference values exactly as before.
Offered, in which case the best matching declared area is chosen and its figures
become the effective port record for every step that follows. Refused, in which case
the candidate becomes a rejection naming the operator and the date they declared, on
one of two grounds. No declared area accepts this class, or every area that does is
committed over the arrival window.

Step 2b. Hard constraint filtering.
For each candidate, check maximum draft, length overall, beam and deadweight against
the effective port record. Mark infeasible candidates as rejected with a stated
reason. Do not silently drop them. The rejections are useful output.

Step 3. Capacity adjustment.
For each surviving candidate, compute the tonnes actually deliverable under two
independent ceilings. The weight ceiling comes from deadweight reduced by the draft
limit. The volume ceiling comes from the vessel's grain capacity divided by the
cargo's stowage factor. The lower ceiling binds. A cargo held by the volume ceiling
is said to cube out. Flag whether lightering at anchorage is required, noting that
lightering can relieve a weight restriction but never a volume one.

Step 4. Cost assembly.
Look up the pre computed forecast rate for that vessel class over the required
arrival window. Add port charges, expected demurrage derived from current congestion,
expected weather delay priced as demurrage, lightering cost where required, and
inland movement cost to the destination plant. Divide the total by deliverable tonnes
to obtain landed cost per tonne. Weather delay is its own line in the breakdown and is
never folded into ordinary demurrage, because the two have different causes and a user
must be able to see which is which.

Step 5. Ranking.
Sort surviving candidates by landed cost per tonne ascending. Operator declared demand
rank breaks a tie and never outranks money, because a port wanting a cargo does not
make that cargo cheaper to deliver there. Demand is reported beside the ranking, in a
separate port intelligence block, and never inside the landed cost.

Step 6. Timing decision.
Compare the cost of fixing today against the forecast distribution of cost across the
acceptable window. If the expected saving from waiting exceeds the downside risk by
the configured margin, recommend waiting. Otherwise recommend fixing now. If a split
parcel beats every single vessel option, recommend splitting.

Step 7. Explanation assembly.
Attach the two or three factors that most influenced the answer, plus the assumption
set used.

Step 8. Response.
Return one JSON payload containing recommendation, ranked options, rejected options,
forecast summary, assumptions, the arrival window the operator availability was
checked against, and the port intelligence block. Every option carries a provenance
map naming the source of each figure the cost model read, as one of PUBLISHED,
OPERATOR DECLARED or ASSUMPTION.

Two rules govern the live inputs.

Rule one. Nothing on this path may open a network socket. The weather read is cache
only. The cache is warmed on a daemon thread at service startup and by
scripts/prime_weather_cache.py. A port with nothing cached contributes zero delay and
says on screen that this is not a claim the weather is good.

Rule two. A declared value never silently replaces a published one. It replaces it
with a label attached, naming who declared it and when. A declared berth draft is
applied only when it is shallower than the published port maximum, because the
approach channel governs and does not care what anyone declares.

---

## 5. API contracts

### 5.1 Express gateway, public

POST /api/recommend

Request body fields.
1. cargo_type. String. One of coking_coal, thermal_coal, limestone, iron_ore,
   manganese_ore, steel_scrap.
2. quantity_tonnes. Number.
3. origin. String. One of australia, usa, mozambique, russia, indonesia.
4. earliest_arrival. ISO date string.
5. latest_arrival. ISO date string.
6. destination_plant. Optional string.
7. destination_port. Optional string. If absent, the system selects.
8. overrides. Optional object of assumption overrides.

Response body fields.
1. recommendation. Object with action, headline, reason and confidence_label.
   Action is one of fix_now, wait, split.
2. options. Array of option objects, ranked.
3. rejected. Array of rejected candidate objects with reason.
4. forecast_summary. Object with horizon days, forecast band and skill score.
5. assumptions. Object listing every assumption value used and whether it was
   defaulted or overridden.
6. generated_at. ISO timestamp.

Option object fields.
1. vessel_class.
2. discharge_port.
3. nominal_capacity_tonnes.
4. deliverable_tonnes.
5. load_percentage.
6. requires_lightering. Boolean.
7. landed_cost_per_tonne.
8. cost_breakdown. Object with freight, port_charges, expected_demurrage,
   lightering, inland.
9. reason. One line string.
10. stowage_factor_m3_per_t. The cargo's stowage factor used for this option.
11. weight_capacity_tonnes. The ceiling set by deadweight and draft.
12. volume_capacity_tonnes. The ceiling set by hold volume and stowage factor.
13. cubes_out. Boolean. True when the volume ceiling is the binding one.
14. cargo_handling_multiplier. The factor applied to load and discharge rates.

Rejected object fields.
1. vessel_class.
2. discharge_port.
3. failed_constraint. One of draft, loa, beam, dwt, stowage.
4. limit_value.
5. required_value.
6. source_citation.

Other endpoints.
1. GET /api/ports. Reference data with citations.
2. GET /api/vessels. Vessel class reference data.
3. GET /api/rates. Historical series with forecast band, filtered by vessel class.
4. POST /api/scenarios. Save a scenario.
5. GET /api/scenarios. List saved scenarios.

### 5.2 ML service, internal only

1. POST /ml/recommend. Full pipeline. Called by Express.
2. POST /ml/forecast. Forecast only, for a vessel class and horizon.
3. GET /ml/skill. Skill scores by vessel class and horizon.
4. GET /ml/health.
5. GET /ml/reference. Ports, vessel classes, origins, plants, cargo types.

### 5.3 Port operator portal, password protected

The port code is always taken from the session token and never from the URL or the
request body, so there is no request an operator can construct that reads or edits
another port.

1. GET /ml/portal/status. Non secret provisioning summary for the sign in page. Which
   ports have a password issued, and how to issue them. Never a hash or a salt.
2. POST /ml/portal/login. Port code and password in, session token out. A wrong port
   code and a wrong password give the same answer, so the endpoint cannot be used to
   enumerate which ports exist. Eight failures lock a port out for fifteen minutes.
3. POST /ml/portal/logout. Discards the session.
4. GET /ml/portal/declaration. The current declaration, or a blank one prefilled from
   the published reference record, plus the vessel classes and cargo types the form
   may offer.
5. PUT /ml/portal/declaration. Saves this operator's declaration. Writes are atomic,
   so a crash mid save cannot leave a port holding half a declaration.
6. GET /ml/portal/weather. The full forecast for this operator's own port and its
   approach anchorage. Accepts refresh=true to fetch rather than read the cache.

### 5.4 Public port data, no authentication

What an operator declares about free area and cargo demand is an advertisement, and
the point of collecting it is that charterers see it. Nothing in this group reads the
credential file, and no response carries a hash, a salt or a token.

1. GET /ml/ports/declarations. Every declaration on file, for the business dashboard.
2. GET /ml/weather. The advisory for every port. Cache only unless refresh=true.
3. GET /ml/weather/{port_code}. One port.

---

## 6. MongoDB collections

1. rate_history. One document per vessel class per date. Fields are vessel_class,
   date, index_value, tce_usd_per_day, source.
2. commodity_history. Date, series name, value, source.
3. congestion_history. Port, date, vessels_at_berth, vessels_at_anchorage,
   estimated_wait_days, source.
4. ports. Port code, name, max_draft_m, max_loa_m, max_beam_m, max_dwt,
   lightering_available, lightering_cost_per_tonne, port_charge_per_tonne,
   and a citations object holding a source URL for every numeric field.
5. vessel_classes. Class name, dwt_min, dwt_max, typical_loa_m, typical_beam_m,
   typical_laden_draft_m, grain_capacity_m3.
5a. cargo_types. Cargo code, name, stowage_factor_m3_per_t,
   handling_rate_multiplier, and a citations object for every numeric field.
6. routes. Origin, discharge port, distance_nm, typical_voyage_days.
7. cost_assumptions. Key, value, unit, source, editable flag.
8. forecasts. Vessel class, generated_at, horizon_days, point, lower, upper.
9. model_runs. Run timestamp, row counts, metrics, skill scores.
10. scenarios. Saved user inputs and the response returned.
11. decision_log. Phase two. Recommendation, user decision, later outcome.

Indexes. Compound index on rate_history by vessel_class and date. Index on forecasts
by vessel_class and generated_at.

---

## 7. Reference data strategy

Port constraints, vessel classes, cargo types and routes live as version controlled
JSON files in the repository and are loaded into MongoDB by a seed script.

Reason. These values are small, rarely change, and every number needs a source
citation that must be reviewable in a pull request. Storing them only in a database
hides the provenance.

Rule. Every numeric field in ports.json carries a matching entry in its citations
object. A value without a citation must not be merged.

---

## 8. Model layer design

Three models, always compared, never one alone.

1. Baseline. Naive persistence. Tomorrow equals today. This is the number every
   other model must beat.
2. Statistical. Seasonal decomposition plus an autoregressive model. Interpretable,
   fast, and often competitive.
3. Learned. Gradient boosting on lagged and exogenous features.

Evaluation is expanding window time series cross validation. Never a random split.

Reported metrics.
1. Mean absolute error at each horizon.
2. Skill score, defined as one minus the model error divided by the baseline error.
   Positive means better than doing nothing. Zero or negative means no skill.
3. Coverage of the prediction interval, meaning how often reality fell inside the
   band we drew.

Rule. If skill score is not positive at a horizon, the interface must show a no skill
banner for that horizon rather than a confident forecast.

---

## 9. File tree

This is the planned tree. Parts of it are still aspirational, and the entries marked
below with a trailing comment are the ones that exist and are running today.

```
freight-decision-system/
├── README.md
├── docker-compose.yml
├── .env.example
│
├── docs/
│   ├── PROJECT.md
│   ├── ARCHITECTURE.md
│   ├── REQUIREMENTS.md
│   └── ROADMAP.md
│
├── data/
│   ├── raw/
│   │   ├── baltic_indices.csv
│   │   └── commodity_prices.csv
│   ├── reference/
│   │   ├── ports.json
│   │   ├── vessel_classes.json
│   │   ├── cargo_types.json
│   │   ├── routes.json
│   │   ├── weather_thresholds.json      # operating limits, every one cited
│   │   └── cost_assumptions.json
│   ├── port_owners/                     # GITIGNORED. Credentials and declarations.
│   │   ├── credentials.json             # salted PBKDF2 hashes only, mode 0600
│   │   └── declarations/                # one JSON file per declaring port
│   ├── cache/
│   │   └── weather/                     # GITIGNORED. Cached forecasts, per position.
│   └── processed/
│       └── .gitkeep
│
├── ml-service/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/
│   │   │   ├── portal.py                # operator endpoints and public port data
│   │   │   ├── routes_recommend.py
│   │   │   ├── routes_forecast.py
│   │   │   └── routes_health.py
│   │   ├── core/
│   │   │   ├── candidates.py
│   │   │   ├── constraints.py
│   │   │   ├── capacity.py
│   │   │   ├── cost_model.py
│   │   │   ├── pipeline.py              # the eight steps, joined up
│   │   │   ├── portal_auth.py           # port operator passwords and sessions
│   │   │   ├── declarations.py          # declarations and the provenance rule
│   │   │   ├── weather.py               # forecast, limits, expected delay days
│   │   │   └── decision.py
│   │   ├── forecasting/
│   │   │   ├── baseline.py
│   │   │   ├── features.py
│   │   │   ├── train.py
│   │   │   ├── predict.py
│   │   │   └── evaluate.py
│   │   ├── data/
│   │   │   ├── loaders.py
│   │   │   ├── synthetic.py
│   │   │   └── seed.py
│   │   └── schemas/
│   │       ├── request.py
│   │       └── response.py
│   ├── static/
│   │   ├── index.html                   # the business dashboard, no sign in
│   │   └── port.html                    # the port operator dashboard, one per password
│   ├── models/
│   │   └── .gitkeep
│   ├── tests/
│   │   ├── test_core.py                 # constraints, capacity, cost, stowage
│   │   ├── test_portal.py               # passwords, declarations, weather, provenance
│   │   ├── test_constraints.py
│   │   ├── test_capacity.py
│   │   ├── test_cost_model.py
│   │   └── test_evaluate.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── scripts/
│   ├── generate_port_credentials.py     # one password per port, run once
│   ├── prime_weather_cache.py           # warm the cache before a demonstration
│   ├── browser_e2e.py                   # real clicks in a real Firefox
│   └── browser/
│       ├── marionette.py                # Firefox's own protocol, no geckodriver
│       ├── checks.py                    # the functional checks
│       └── accessibility.py             # the structural audit
│
├── passwords.txt                        # GITIGNORED. Plaintext, mode 0600, hand out once.
│
├── api/
│   ├── src/
│   │   ├── server.js
│   │   ├── config.js
│   │   ├── routes/
│   │   │   ├── recommend.js
│   │   │   ├── reference.js
│   │   │   ├── rates.js
│   │   │   └── scenarios.js
│   │   ├── controllers/
│   │   ├── models/
│   │   │   ├── Port.js
│   │   │   ├── RateHistory.js
│   │   │   └── Scenario.js
│   │   └── services/
│   │       └── mlClient.js
│   ├── package.json
│   └── Dockerfile
│
└── web/
    ├── src/
    │   ├── main.jsx
    │   ├── App.jsx
    │   ├── pages/
    │   │   ├── DecisionConsole.jsx
    │   │   ├── MarketForecast.jsx
    │   │   └── PortIntelligence.jsx
    │   ├── components/
    │   │   ├── CargoInputForm.jsx
    │   │   ├── RecommendationBanner.jsx
    │   │   ├── OptionCard.jsx
    │   │   ├── RejectedOptionCard.jsx
    │   │   ├── CostBreakdown.jsx
    │   │   ├── ForecastChart.jsx
    │   │   ├── SkillPanel.jsx
    │   │   └── AssumptionsPanel.jsx
    │   ├── api/
    │   │   └── client.js
    │   └── styles/
    ├── package.json
    └── Dockerfile
```

---

## 10. Deployment

Local development runs three processes plus MongoDB.

Production demo runs docker compose with four containers. Everything must work with
no internet connection once data is seeded, because a live API call during a
presentation is an unnecessary way to fail.
