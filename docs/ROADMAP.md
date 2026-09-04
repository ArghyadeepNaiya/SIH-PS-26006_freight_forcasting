# ROADMAP.md

Step by step build order. Six people.

---

## Step 0. Before any code. Two hours.

S0-1. Domain lead performs the hand calculation. Seventy five thousand tonnes of
coking coal from Queensland, computed two ways. Panamax discharging at Haldia versus
Capesize discharging at Dhamra. Include freight, port charges, expected waiting time
and lightering at Haldia. Use assumed numbers where real ones are unavailable and
write down every assumption.

This is not optional. It is the exercise that lets a human answer a judge's question
instead of reciting a slide.

S0-2. Data lead obtains daily freight rate history for the four vessel classes,
records the source and its licence terms in data/reference/SOURCES.md, and saves the
file to data/raw/baltic_indices.csv.

S0-3. Ports lead builds data/reference/ports.json with one source URL per numeric
field. Sources disagree, so a value without a citation is not accepted.

S0-4. Everyone else reads the domain knowledge section. Vessel classes, draft, length
overall, beam, deadweight, voyage versus time charter, laytime, demurrage,
lighterage.

---

## Step 1. Repository skeleton. Thirty minutes. Backend lead.

S1-1. Create the directory structure exactly as given in ARCHITECTURE.md section 9.
S1-2. Initialise git. Add the four documents. Commit.
S1-3. Create requirements.txt, package.json for api and web, and .env.example.
S1-4. Confirm MongoDB runs locally.

Everyone clones from here. Do not start work before this exists.

---

## Step 2. Reference data and seeding. One hour. Ports lead and data lead.

S2-1. Write data/reference/vessel_classes.json with deadweight ranges and typical
dimensions per class.
S2-2. Write data/reference/routes.json with approximate sailing distances per origin
and discharge port pair.
S2-3. Write data/reference/cost_assumptions.json with port charge per tonne,
demurrage rate per day, lightering cost per tonne and inland cost per tonne. Every
entry carries a source and an editable flag.
S2-4. Write app/data/seed.py to load all four JSON files and the rate CSV into
MongoDB.
S2-5. Run the seed. Confirm collection counts.

Checkpoint. Query MongoDB and get back Haldia's draft limit with its citation.

---

## Step 3. The constraint engine. One hour. Backend lead.

Build this before the models. It is deterministic, it is testable, and it is the part
of the product that is provably correct.

S3-1. Write core/candidates.py to generate every vessel class and port combination.
S3-2. Write core/constraints.py to check draft, length overall, beam and deadweight,
returning either feasible or a rejection object naming the failed constraint.
S3-3. Write core/capacity.py to compute deliverable tonnes under a draft limit and to
flag whether lightering is required.
S3-4. Write tests/test_constraints.py and tests/test_capacity.py.

Checkpoint. A test asserts that Capesize at Haldia is rejected on draft, and that
Panamax at Haldia returns deliverable tonnes well below nominal capacity.

This checkpoint is the heart of the project. Reach it before anything else.

---

## Step 4. The cost model. One hour. Domain lead and backend lead.

S4-1. Write core/cost_model.py computing freight, port charges, expected demurrage,
lightering and inland cost, then landed cost per tonne using deliverable tonnes as the
denominator.
S4-2. Every assumption is read from cost_assumptions, never hard coded.
S4-3. Write tests/test_cost_model.py.

Checkpoint. The code reproduces the domain lead's hand calculation from step zero to
within a reasonable tolerance. If it does not, one of the two is wrong and you must
find out which before proceeding.

---

## Step 5. Forecasting. Two hours. Forecasting lead.

Build in this order. Do not skip ahead.

S5-1. Write forecasting/baseline.py implementing naive persistence.
S5-2. Write forecasting/evaluate.py implementing expanding window cross validation,
mean absolute error by horizon, skill score against baseline, and interval coverage.
S5-3. Evaluate the baseline. Record its error. This is the number to beat.
S5-4. Write forecasting/features.py building lags, rolling means, rolling volatility
and calendar features.
S5-5. Write forecasting/train.py training a gradient boosted model per vessel class.
S5-6. Evaluate. Compute skill score by horizon.
S5-7. Write forecasting/predict.py producing point forecasts with prediction
intervals.

Checkpoint. You can state, for each vessel class and each horizon, whether the model
beats doing nothing. Positive skill at some horizons and zero at others is the
expected and honest result. Report it.

Stop here. Do not add more models until phase one.

---

## Step 6. The decision layer. One hour. Backend lead.

S6-1. Write core/decision.py comparing the cost of fixing today against the forecast
cost distribution across the arrival window.
S6-2. Return one of fix now, wait or split, with a plain language reason.
S6-3. Where skill score is not positive at the required horizon, the decision must
default to fix now with a stated no skill reason. Never recommend waiting on a
forecast that has no demonstrated skill.

---

## Step 7. The FastAPI service. One hour. Backend lead.

S7-1. Write schemas/request.py and schemas/response.py as pydantic models matching
the contract in ARCHITECTURE.md section 5.
S7-2. Write api/routes_recommend.py wiring candidates, constraints, capacity, cost,
decision and explanation into one handler.
S7-3. Write api/routes_forecast.py and api/routes_health.py.
S7-4. Write main.py.

Checkpoint. A single curl request returns a complete recommendation payload.

---

## Step 8. The Express gateway. Forty minutes. Backend lead.

S8-1. Write services/mlClient.js calling the Python service.
S8-2. Write routes for recommend, ports, vessels, rates and scenarios.
S8-3. Write mongoose models for Port, RateHistory and Scenario.
S8-4. Add request logging.

Checkpoint. The same curl request works through Express.

---

## Step 9. The Decision Console. Two hours. Frontend lead one.

Build in this order so that something is visible early.

S9-1. CargoInputForm with the five fields.
S9-2. RecommendationBanner showing the plain language action.
S9-3. OptionCard showing landed cost per tonne as the headline, deliverable tonnes,
load percentage and the one line reason.
S9-4. RejectedOptionCard showing the failed constraint and the port limit citation.
S9-5. CostBreakdown expanding on click.

Checkpoint. Entering a cargo returns ranked cards and at least one visible rejection.

---

## Step 10. Market and Forecast. One hour. Frontend lead two.

S10-1. ForecastChart with history and a widening band.
S10-2. SkillPanel stating improvement over naive persistence at each horizon, with an
explicit no skill notice where applicable.

---

## Step 11. Freeze and rehearse. Two hours. Everyone.

S11-1. No new features after this point.
S11-2. Seed a demo database and disable networking. Confirm everything still works.
S11-3. Rehearse the flow three times.
S11-4. Each person explains a component they did not write. If anyone cannot, fix the
understanding, not the code.

---

## Phase one, after the idea presentation

P1-1. Port Intelligence screen with cited constraints.
P1-2. Congestion ingestion from published port position reports.
P1-3. AssumptionsPanel making every assumption editable, with live recomputation.
P1-4. Backtested decision policy against always spot fixing, reported as money saved.
P1-5. SHAP driver attribution.
P1-6. Statistical model added as a third comparator.

P1-4 is the highest value item in this list. It is the money slide.

---

## Phase two, before the finale

P2-1. Contract structure recommendation. Spot, period or contract of affreightment.
P2-2. Parcel splitting optimisation.
P2-3. Scenario stress testing.
P2-4. Decision Log with outcome tracking.
P2-5. Printable one page recommendation export.
P2-6. Docker compose packaging verified offline.

---

## Standing rules

R-1. Nobody ships code they cannot explain out loud in sixty seconds.
R-2. No numeric reference value is merged without a source citation.
R-3. No accuracy figure is ever shown without its baseline beside it.
R-4. No live external API call during a demonstration.
R-5. Feature freeze happens two hours before any presentation, without exception.
