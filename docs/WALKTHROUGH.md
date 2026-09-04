# WALKTHROUGH.md

Freight Charter Decision System. The complete working reference.

This document explains what actually runs, what every abbreviation means, and the
behind the scenes details that decide whether the project works or breaks. It is
written to be read top to bottom once, then navigated by heading afterwards.

---

## 1. Running and stopping the system

### 1.1 Start

1. Open a terminal in the project root.
2. Run `./run.sh`.
3. Open `http://localhost:8000` in a browser.

### 1.2 What run.sh actually does

1. It changes directory into `ml-service`.
2. It creates a Python virtual environment at `ml-service/venv` if one does not exist.
3. It activates that environment.
4. It installs the packages listed in `ml-service/requirements.txt`.
5. It starts Uvicorn, which serves the FastAPI application on port 8000.

### 1.3 Stop

1. Press Control and C in the terminal where it is running.
2. If it is running in the background, run `pkill -f "uvicorn app.main:app"`.

### 1.4 The single most common failure

Port 8000 is already in use. The error reads `[Errno 98] address already in use`.
This happens when an older copy of the server is still alive, including a copy
started from a different folder. Run `ss -ltnp | grep 8000` to find the process
identifier, confirm which directory it is running from with `ps aux | grep uvicorn`,
then stop it before starting a new one. There is a second project folder on this
machine named `SIH-PS-26006-Freight-forcasting` without the `_claude` suffix, and it
contains an older and different codebase. Serving that one by accident looks exactly
like this project being broken.

---

## 2. Every abbreviation, in plain language

### 2.1 Programme and organisation

1. SIH. Smart India Hackathon.
2. PS. Problem Statement. Ours is SIH26006.
3. SAIL. Steel Authority of India Limited. The user organisation.
4. MoS. Ministry of Steel. The parent organisation.

### 2.2 Ship measurements

1. DWT. Deadweight Tonnage. The total mass a vessel can carry including cargo,
   fuel, water and stores, measured in tonnes. It is a capacity figure, not a weight
   of the ship itself.
2. LOA. Length Overall. The full length of the vessel from bow to stern in metres.
   A berth shorter than the LOA cannot take the ship, and there is no workaround.
3. Beam. The width of the vessel at its widest point in metres. Lock gates and
   channel widths do not flex, so this is also a hard limit.
4. Draft. The vertical distance from the waterline to the lowest point of the hull
   in metres. It is how deep the ship sits in the water.
5. Laden draft. The draft when the vessel is fully loaded. Deepest condition.
6. Light draft. The draft when the vessel is empty. Shallowest condition. This code
   assumes light draft is forty two percent of laden draft.
7. Air draft. Height above the waterline. Not modelled in this system.

### 2.3 Vessel classes

1. Handysize. Roughly ten thousand to forty thousand DWT. Nominal thirty two
   thousand. It carries its own cranes, so it can work at ports with no shore
   equipment. Highest cost per tonne.
2. Supramax. Roughly fifty thousand to sixty thousand DWT. Nominal fifty six
   thousand. Also geared, meaning it has its own cranes. The workhorse for
   constrained ports.
3. Panamax. Roughly sixty thousand to eighty thousand DWT. Nominal seventy five
   thousand. Gearless, so it needs shore cranes. Named for the old Panama Canal
   lock dimensions.
4. Capesize. Roughly one hundred and twenty thousand to two hundred thousand DWT.
   Nominal one hundred and seventy thousand. Too large for the Panama and Suez
   canals, so it sails around the Cape. Lowest cost per tonne when it can berth at
   all.
5. Geared. The vessel has its own cargo cranes. Ungeared or gearless means it
   depends on shore cranes.

### 2.4 Freight market terms

1. TCE. Time Charter Equivalent. The daily earnings of a vessel expressed in US
   dollars per day. This is the number that converts an index level into money.
2. BDI. Baltic Dry Index. The headline composite dry bulk freight index.
3. BCI. Baltic Capesize Index. Used for the Capesize class.
4. BPI. Baltic Panamax Index. Used for the Panamax class.
5. BSI. Baltic Supramax Index. Used for the Supramax class.
6. BHSI. Baltic Handysize Index. Used for the Handysize class.
7. Spot fix. Chartering a single vessel for a single voyage at today's price.
8. Period charter. Hiring a vessel for a fixed span of time rather than one voyage.
9. COA. Contract of Affreightment. An agreement to move a stated quantity of cargo
   over a period across multiple voyages.
10. FFA. Forward Freight Agreement. A traded contract representing the market's own
    forward view of freight rates. We do not have this data, and we say so.
11. Laytime. The time allowed for loading and discharging under the charter.
12. Demurrage. The penalty paid when laytime is exceeded. Congestion becomes money
    through this term.
13. Ballast leg. The portion of the voyage sailed empty, typically to reach the load
    port. This code allows fifty five percent of laden sea time for it.
14. Lightering, also called lighterage. Transferring part of the cargo to smaller
    vessels at anchorage so the mother vessel floats higher and can enter a shallow
    port.
15. Fixture. A concluded charter deal.
16. VLSFO. Very Low Sulphur Fuel Oil. The bunker fuel grade priced in the
    assumptions file.
17. Bunker. Marine fuel.

### 2.5 Stowage terms

1. Stowage factor, often shortened to SF. The volume that one tonne of a cargo
   occupies, measured in cubic metres per tonne. Iron ore is about 0.40 and thermal
   coal is about 1.30, so a tonne of coal takes over three times the space.
2. Grain capacity. The total volume of the cargo holds in cubic metres.
3. Weighs out. The vessel reaches its deadweight or its draft limit while hold space
   remains empty. Normal for dense cargo such as ore.
4. Cubes out. The vessel fills its holds before reaching its deadweight. Normal for
   bulky cargo such as thermal coal on a large ship.
5. Break even stowage factor. Grain capacity divided by deadweight. A cargo with a
   stowage factor above this figure will cube out on that vessel. It is about 1.34
   for Handysize, 1.27 for Supramax, 1.19 for Panamax and 1.15 for Capesize.
6. HMS. Heavy Melting Scrap. A steel scrap grade. Loose HMS stows far more bulkily
   than baled scrap, which is why the steel scrap stowage factor carries the widest
   uncertainty in the data.

### 2.6 Modelling terms

1. MAE. Mean Absolute Error. The average size of the forecast error, ignoring sign.
2. Skill score. One minus the model error divided by the baseline error. Above zero
   means the model beats doing nothing. At or below zero means it has no skill.
3. Naive persistence. The baseline that assumes tomorrow equals today. Every model
   must beat this or be declared useless.
4. Expanding window cross validation. Train on the earliest data, test on what comes
   next, then extend the training window and repeat. It respects time order.
5. Random split. Shuffling rows before splitting into train and test. Prohibited in
   this project, because it leaks the future into the past.
6. Ridge regression. A linear model with a penalty that shrinks coefficients. It is
   the default here because it does not have enough capacity to overfit a nearly
   random series.
7. GBM. Gradient Boosting Machine. A tree ensemble. Kept as a comparator only,
   because it lost to Ridge on this data.
8. SHAP. SHapley Additive exPlanations. A method for attributing a prediction to its
   input features. Planned for phase one, not yet built.
9. Forward return. The proportional change in the index over the forecast horizon.
   The models predict this rather than the price level.
10. Prediction interval. The band around a point forecast. This system draws an
    approximate eighty percent band.
11. Residual standard deviation. The spread of the model's errors. It sets the width
    of the band.

### 2.7 Software terms

1. API. Application Programming Interface. Here it means the HTTP endpoints.
2. REST. An HTTP style where each URL names a resource.
3. JSON. JavaScript Object Notation. The data format used for every request and
   response.
4. FastAPI. The Python web framework serving the machine learning service.
5. Uvicorn. The server process that runs the FastAPI application.
6. CORS. Cross Origin Resource Sharing. Browser rules about which origins may call
   an API. This service allows all origins, which is fine for a local demo.
7. MCP. Model Context Protocol. Unrelated to the product itself. It is the
   configuration in `.mcp.json` for a Claude tool integration.
8. venv. Python virtual environment. An isolated set of installed packages.

### 2.8 Codes used in the data files

1. Port codes are UN LOCODE style. INPRT is Paradip. INDAH is Dhamra. INGGV is
   Gangavaram. INVTZ is Visakhapatnam. INGPR is Gopalpur. INHAL is Haldia. INSAG is
   Sagar and Sandheads.
2. Origin codes are AU for Australia, US for the United States, MZ for Mozambique,
   RU for Russia and ID for Indonesia.
3. Units are t for tonnes, tpd for tonnes per day, nm for nautical miles, m for
   metres and knots for speed.

### 2.9 Requirement identifiers

1. FR. Functional Requirement. Numbered FR-01 upward.
2. NFR. Non Functional Requirement. Numbered NFR-01 upward.
3. DR. Data Requirement. Numbered DR-01 upward.
4. AC. Acceptance Criterion. Numbered AC-01 upward.
5. OI. Open Item requiring team verification. Numbered OI-01 upward.
6. These identifiers are stable and must never be renumbered.

---

## 3. What actually runs, versus what is only documented

This is the most important section for avoiding embarrassment at judging.

### 3.1 What is real and working

1. The Python FastAPI service in `ml-service/`. This is the entire working product.
2. The static dashboard at `ml-service/static/index.html`. Three screens, served by
   the same FastAPI process at the root URL.
3. The reference data files in `data/reference/`.
4. The forecasting stack, trained in memory at startup.

### 3.2 What exists on paper but does not run

1. The Express gateway in `api/`. It is scaffolded and is not required. Nothing
   calls it. ARCHITECTURE.md describes it as the public entry point, which is the
   intended design, not the current state.
2. The React application in `web/`. The `web/src` folders are empty. There is no
   React app.
3. MongoDB. ARCHITECTURE.md describes eleven collections. None of them exist. The
   running prototype holds everything in memory and reads JSON files from disk.
4. The nightly batch pipeline. Training happens at server startup instead.

### 3.3 Why this matters

If a judge asks whether you use MongoDB, the honest answer is that the architecture
specifies it for persistence and the prototype does not yet need it, because
reference data is small, version controlled and better reviewed in a pull request
than hidden in a database. Say that rather than implying it is wired up.

---

## 4. The request pipeline, step by step

This runs inside `ml-service/app/core/pipeline.py` every time a recommendation is
requested. Target latency is under one second.

1. Candidate generation, in `candidates.py`. It takes the origin code and cargo
   type, then builds every combination of the four vessel classes and the seven
   ports. That is twenty eight candidates. It raises an error if the origin does not
   supply the requested cargo.
2. Hard constraint filtering, in `constraints.py`. It checks LOA, then beam, then
   DWT, against the port limits. A failure returns a rejection object naming the
   constraint, the limit, the required value and the source citation. Rejections are
   returned to the user, never silently dropped.
3. Capacity adjustment, in `capacity.py`. It computes how many tonnes can actually
   be delivered given the draft at both ends of the voyage.
4. Cost assembly, in `cost_model.py`. It adds freight, demurrage, port charges,
   lightering and inland movement, then divides by deliverable tonnes.
5. Ranking. Options are sorted by landed cost per tonne, ascending.
6. Timing decision, in `decision.py`. It returns fix now, wait, or split.
7. Explanation assembly. It attaches the two or three factors that drove the answer
   plus the full assumption set.
8. Response. One JSON payload containing the recommendation, ranked options,
   rejected options, the forecast summary and the assumptions.

### 4.1 A detail that surprises people

Draft is deliberately not checked in step two. A vessel that cannot float deep
enough is not disqualified, because it can simply load less. That is a capacity
question, not a feasibility question. Only LOA, beam and DWT are hard rejections. A
draft failure becomes a rejection only if the resulting load falls below thirty
percent, which is the point where calling the port stops making commercial sense.

---

## 5. The capacity model, which is the heart of the project

### 5.1 The reasoning

A voyage costs roughly the same whether the ship sails full or half full. So the
number that matters is total cost divided by tonnes actually discharged, not divided
by nominal capacity. At a draft restricted port those two numbers diverge sharply.

### 5.2 There are two independent ceilings

A vessel cannot exceed either of these, so the lower one binds.

1. The weight ceiling. Set by deadweight, and reduced at a shallow port by draft.
2. The volume ceiling. Set by the grain capacity of the holds divided by the cargo's
   stowage factor. This is the ceiling that makes cargo type matter.

### 5.3 The weight calculation

1. Light draft is assumed to be forty two percent of laden draft.
2. Between light draft and laden draft, carrying capacity is approximated as linear
   in draft.
3. The loadable fraction is the allowed draft minus the light draft, divided by the
   laden draft minus the light draft.
4. The model computes this at the load port and at the discharge port, then takes
   whichever is smaller. That end is reported as the binding constraint.

### 5.4 The volume calculation

1. The volume ceiling is the vessel's grain capacity in cubic metres divided by the
   cargo's stowage factor in cubic metres per tonne.
2. If that figure is lower than the weight ceiling, the cargo cubes out. The binding
   constraint is then reported as volume rather than as a draft.
3. Worked example. A Capesize has one hundred and ninety five thousand cubic metres
   of hold and a deadweight of one hundred and seventy thousand tonnes. Thermal coal
   stows at one point three cubic metres per tonne. One hundred and ninety five
   thousand divided by one point three is one hundred and fifty thousand tonnes. The
   ship therefore sails twenty thousand tonnes below its deadweight with full holds,
   in any depth of water.
4. Iron ore at nought point four cubic metres per tonne gives a volume ceiling of
   four hundred and eighty seven thousand tonnes, far above the deadweight, so ore
   always weighs out and leaves most of the hold empty.

### 5.5 An asymmetry worth stating at judging

Lightering can relieve a weight restriction, because it lets the vessel load deeper
at origin and discharge the excess at anchorage. It can do nothing at all about a
volume restriction, because hold space is fixed. The model encodes this, and refuses
to propose lightering for a cargo that cubes out. That is the kind of detail a
domain expert on the panel will look for.

### 5.6 The validation that is worth stating out loud

1. Haldia has a published maximum draft of nine point one metres.
2. A Panamax has a typical laden draft of thirteen point five metres.
3. Light draft is therefore five point six seven metres.
4. The loadable fraction is nine point one minus five point six seven, divided by
   thirteen point five minus five point six seven, which is forty three point eight
   percent.
5. Published sources independently state that Panamax vessels at Haldia carry forty
   to fifty percent of capacity.
6. The model was never given that figure. It derived it from physics and agrees with
   the documented fact.

### 5.7 The caveat you must know before demonstrating this

The forty three point eight percent figure appears only when lightering is
disallowed. Haldia has lightering available, so with lightering permitted the same
call returns one hundred percent load with forty two thousand tonnes moved at
anchorage. Both variants are generated and shown, because they are two genuinely
different commercial choices. If you quote forty three point eight percent, say
explicitly that it is the no lightering case, otherwise a sharp judge will pull up
the other number from your own screen.

---

## 6. The cost model

### 6.1 The rule

Every cost number is read from `data/reference/cost_assumptions.json`. Nothing is
hard coded. This is what makes every figure on screen traceable and editable.

### 6.2 The components

1. Freight. Hire days multiplied by TCE. Hire days are laden sea days multiplied by
   one point five five, to allow for the ballast leg, plus loading days plus
   discharge days.
2. Expected demurrage. Typical waiting days at the port multiplied by a demurrage
   rate, which is TCE multiplied by one point one five.
3. Port charges. Tonnes multiplied by the port charge per tonne, plus a fixed port
   due of twenty five thousand US dollars per call.
4. Lightering. Lightered tonnes multiplied by the lightering cost per tonne, and
   only where draft forced it.
5. Inland movement. Tonnes multiplied by distance in kilometres multiplied by the
   rail rate per tonne per kilometre, converted from rupees to dollars.
6. Landed cost per tonne. The sum of all of the above divided by deliverable tonnes.

### 6.3 Sea time

Distance in nautical miles divided by thirteen knots multiplied by twenty four
hours. Thirteen knots is the assumed service speed.

### 6.4 How cargo type reaches the cost

Cargo affects money through two separate channels, and it is worth being able to
name both.

1. Through the denominator. Stowage factor sets the volume ceiling, which can reduce
   deliverable tonnes. Since landed cost is total voyage cost divided by deliverable
   tonnes, a cargo that cubes out spreads a nearly identical voyage cost over fewer
   tonnes and therefore costs more per tonne.
2. Through time. Each cargo carries a handling rate multiplier that scales both the
   load rate at origin and the discharge rate at the destination. Slower handling
   means more days on hire, which raises the freight component directly. Steel scrap
   at nought point six is the extreme case, because scrap does not flow and is worked
   with magnets and grabs.

### 6.4 The assumptions you can edit

1. `usd_to_inr`, currently eighty eight rupees per dollar.
2. `bunker_price_usd_per_tonne`, currently five hundred and sixty.
3. `demurrage_usd_per_day_multiplier`, currently one point one five times TCE.
4. `inland_cost_inr_per_tonne_per_km`, currently one point six rupees.
5. `port_dues_fixed_usd`, currently twenty five thousand.
6. `wait_risk_premium`, currently zero point three five.
7. `split_advantage_threshold`, currently zero point zero three.
8. `min_skill_score_to_wait`, currently zero point zero two, and deliberately marked
   not editable because it encodes a design rule rather than a market assumption.

---

## 7. The decision layer

### 7.1 The non negotiable guard

If the skill score at the required horizon is at or below the minimum threshold, the
system returns fix now and states that it has no forecasting edge. It will never
recommend waiting on a forecast that has not demonstrated skill. This guard is
written into the code, not left as a comment.

### 7.2 When skill does exist

1. The forecast index ratio is applied only to the freight portion of landed cost,
   because port charges and inland movement do not move with the freight market.
2. Expected saving is today's cost minus the expected future cost.
3. Downside risk is the worst case future cost minus today's cost.
4. Waiting is recommended only if the expected saving exceeds the downside risk
   multiplied by the wait risk premium, and also exceeds fifty cents per tonne.

### 7.3 The split signal

If any smaller vessel class lands cheaper than the best option by more than the
split advantage threshold, the recommendation becomes split the cargo. That happens
when a draft limit penalises the larger vessel enough to erase its scale advantage.

---

## 8. The forecasting stack

### 8.1 What is modelled

1. One model per index per horizon. Four indices multiplied by five horizons gives
   twenty models.
2. The horizons are seven, fourteen, thirty, sixty and ninety days.
3. The target is the forward return, meaning the proportional change over the
   horizon, not the price level. Regressing on the level lets a model chase the
   trend and lose badly to persistence.

### 8.2 The features

1. Lags at one, two, three, five, ten, twenty one, forty two and sixty three days.
2. Rolling mean and rolling standard deviation over five, twenty one and sixty three
   days.
3. Rolling returns over the same windows.
4. Momentum ratios between the five and twenty one day means, and between the twenty
   one and sixty three day means.
5. Level relative to the sixty three day mean.
6. Calendar features. Month, day of week, and sine and cosine of day of year.
7. One exogenous series, the BDI, as a lag and as a twenty one day return.

### 8.3 The evaluation

1. Five expanding window folds with a minimum training size of seven hundred and
   fifty rows.
2. Errors are converted back to index points so that model MAE and baseline MAE are
   directly comparable.
3. The baseline is persistence, which in return space is simply predicting zero
   change. This makes the comparison exact rather than approximate.
4. Skill is declared only above zero point zero two, not merely above zero.

### 8.4 The honest current result

On the scaffolding data the model shows no skill at nineteen of twenty horizons.
This is correct and expected. The scaffolding is generated as a near random walk, so
there is no signal to find. Do not tune this to look better. The refusal to
recommend waiting without demonstrated skill is the most defensible feature in the
project.

---

## 9. Data files and how to change them

### 9.1 The five reference files

1. `data/reference/ports.json`. Seven ports with draft, LOA, beam, DWT, lightering
   availability, charges, discharge rate and typical waiting days. Every numeric
   field has a matching entry in a citations object.
2. `data/reference/vessel_classes.json`. Four classes with DWT ranges, typical
   dimensions, laden draft, geared flag and the index key that prices them.
3. `data/reference/routes.json`. Origins with the cargo types each supplies, load
   rates and load port draft, plus a distance table in nautical miles.
4. `data/reference/cost_assumptions.json`. The eight editable assumptions and the
   five plants with their distances to each port.
5. `data/reference/cargo_types.json`. Six cargo types, each with a stowage factor in
   cubic metres per tonne, a handling rate multiplier, notes and citations. This is
   the file that makes cargo type economically meaningful.

### 9.2 The citation rule

Every numeric reference value carries a source. A value without a citation must not
be merged. Many current values read `ASSUMPTION - verify`, and the dashboard counts
and displays how many unverified fields each port still has. That count is a feature,
not a defect.

### 9.3 Loading real market data

1. Place a CSV at `data/raw/baltic_indices.csv`.
2. Give it the columns `date`, `BCI`, `BPI`, `BSI`, `BHSI`.
3. Restart the server.
4. The loader prefers the real file automatically and the header badge switches from
   SCAFFOLDING to REAL DATA.
5. Nothing else needs to change.

### 9.4 Changes that require a restart

The reference JSON files and the rate history are read once at import and startup.
Editing them while the server runs has no effect until you restart it. The dashboard
HTML is the exception, because it is read from disk on every request.

---

## 10. The HTTP endpoints

1. `GET /`. Serves the dashboard.
2. `GET /ml/health`. Data source label, whether it is real data, row count and date
   range.
3. `POST /ml/recommend`. The full pipeline. This is the one that matters.
4. `GET /ml/forecast`. A single forecast for one index and horizon.
5. `GET /ml/skill`. The full skill table across every index and horizon.
6. `GET /ml/history`. Historical series for charting.
7. `GET /ml/reference`. Ports, vessel classes, origins, plants and assumptions.

Note that the path prefix is `/ml/`, not `/api/`. The `/api/` prefix in
ARCHITECTURE.md describes the Express gateway that is not running. Calling
`/api/recommend` returns not found, which looks like a broken system but is simply
the wrong URL.

---

## 11. Behind the scenes, the things that actually break this project

### 11.1 Two JavaScript traps that already cost real debugging time

1. Implicit window globals. Referring to an element by its id alone works only when
   that name is not already a Window property. `window.origin` is a built in read
   only string, so `origin.value` silently returned undefined and the request went
   out without its origin field. The server answered 422 and the screen printed
   nothing useful. Always use `document.getElementById`.
2. Inline event handlers. An inline `on` handler is compiled with the form in its
   scope chain, and a form exposes its own controls by id. So inside
   `<form onsubmit="run()">`, the name `run` resolved to `<button id="run">` rather
   than to the function, and calling an element throws. The click did nothing and
   sent no request at all. All handlers are now attached with `addEventListener`,
   where only real lexical scope applies. Do not reintroduce inline handlers.

### 11.2 Browser caching

The dashboard is now served with `Cache-Control: no-store, must-revalidate`. Before
that, a browser tab kept running old JavaScript after the file on disk had been
fixed, which is indistinguishable from the fix not working. If you ever see
behaviour that contradicts the code, confirm the browser actually reloaded before
concluding anything.

### 11.3 Validation failures are now logged

Any request that fails validation prints the received body to the server log. A 422
with nothing logged is close to undebuggable. Read the terminal before guessing.

### 11.4 Cargo and origin must match

Each origin supplies only certain cargo types. Requesting a cargo an origin does not
supply returns a 400 with a clear message. The dashboard now filters the cargo list
to the selected origin, so this cannot happen by accident through the interface.

### 11.5 Two project folders on this machine

There is an older, different codebase at `SIH-PS-26006-Freight-forcasting`. Both
want port 8000. Running the wrong one is the single most confusing failure mode
available to you.

### 11.6 The models are trained at startup

Startup takes several seconds because twenty models are trained before the server
accepts traffic. This is why the health endpoint is worth checking before demoing.
Nothing is persisted between runs except a metrics cache file.

---

## 12. How to verify the system is genuinely working

1. Run `python tests/test_core.py` from inside `ml-service` with the virtual
   environment active. It asserts that Capesize is rejected at Haldia, that Panamax
   at Haldia is draft limited, and that Capesize loads full at Dhamra. It prints the
   landed cost comparison.
2. Check `GET /ml/health` returns a row count and a date range.
3. Send a recommendation request and confirm you receive ranked options and at least
   one rejection.
4. Open the dashboard, select Get recommendation, and confirm cards appear.
5. Watch the server log while you do it. Every request appears there, and any
   validation failure prints the offending body.

---

## 13. Known gaps, stated honestly

1. OI-01. Plant to port distances are assumptions. Verify against the SAIL annual
   report before showing a Ministry of Steel evaluator.
2. Most port fields other than draft, LOA and beam are unverified assumptions.
3. The TCE multipliers in `pipeline.py` are placeholders, roughly calibrated. Replace
   them with published TCE series.
4. Real freight rate history has not been loaded. The system runs on scaffolding.
5. The Express gateway, the React application and MongoDB are not built.
6. Congestion is a static typical waiting days figure per port, not a live feed.
7. Stowage factors and grain capacities are typical published mid range figures
   marked as assumptions, not verified vessel particulars or bills of lading. The
   steel scrap figure carries the widest uncertainty, because real scrap stows
   anywhere between nought point six and one point four cubic metres per tonne
   depending on grade and baling. Verify per fixture before relying on it.
8. Cargo type does not yet affect anything beyond stowage and handling speed. It does
   not change port charges, hold cleaning requirements, cargo damage risk or
   seasonal availability.

---

## 14. Standing rules

1. Nobody ships code they cannot explain out loud in sixty seconds.
2. No numeric reference value is merged without a source citation.
3. No accuracy figure is ever shown without its baseline beside it.
4. No live external API call during a demonstration.
5. Feature freeze happens two hours before any presentation, without exception.
