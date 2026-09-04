# HANDOFF PROMPT

Paste everything below the line into a new Claude chat. Attach the project zip or
the four docs if you have them.

---

I am working on Smart India Hackathon 2026, problem statement **SIH26006**,
"Development of an Intelligent Freight Forecasting Model for Optimized Vessel
Chartering and Bulk Cargo Procurement from overseas to East Coast of India".
Organisation: Ministry of Steel. Department: SAIL. Idea submission deadline was
20 September 2026. Grand Finale is roughly two months out.

## My team

Six people. Skills are traditional ML (regression, classification, clustering,
feature engineering, ensembles, evaluation), traditional DL (CNN, basic RNN/LSTM),
and MERN. Willing to learn adjacent tools like FastAPI. Little domain knowledge in
shipping. We chose this problem after comparing it against all 226 SIH 2026
statements, because it needs no computer vision, no NLP and no geospatial work, and
because its data is obtainable.

## Formatting I need

I use the JAWS screen reader. Please use numbered lists with one idea per item,
full stops rather than semicolons or dashes, clear heading hierarchy, and no tables
or multi-column layouts.

## What has already been decided (do not re-litigate unless you have a strong reason)

1. **The product is not a freight rate predictor. It is a charter timing and vessel
   selection decision system.** The user enters a cargo requirement, never a vessel.
   Vessel class is an output.
2. **The output unit is landed cost per tonne delivered**, not an index value. SAIL
   does not care about the Baltic Dry Index. It cares about rupees per tonne at the
   plant gate.
3. **The central insight.** A voyage costs roughly the same whether the ship sails
   full or half full, so cost must be divided by tonnes actually discharged, not by
   nominal capacity. At draft-restricted ports these diverge sharply. Haldia has
   about 9.1 m draft and Panamax vessels there carry 40 to 50 percent of capacity.
   Dhamra has about 18 m and takes super Capesize directly.
4. **Freight indices behave close to a random walk.** Every model is benchmarked
   against naive persistence and reported as a skill score. Where skill is absent we
   say so on screen. Expanding-window time series cross validation only, never a
   random split.
5. **Three screens.** Decision Console (produces the answer), Market and Forecast
   (makes it believable), Port Intelligence (explains rejections).
6. **Stack.** React plus Express plus MongoDB plus a Python FastAPI service running
   pandas, scikit-learn and SHAP. No deep learning. No graph database. No blockchain.
7. **Ridge regression beat gradient boosting** on this data, because a boosted tree
   has far too much capacity for the amount of signal present. Ridge is the default.
   Models predict the forward return, not the price level.

## What has been built and tested

A working prototype exists. Run `./run.sh`, open http://localhost:8000.

1. `ml-service/app/core/constraints.py` filters vessel and port combinations on LOA,
   beam and DWT. Rejections are returned with source citations, not discarded.
2. `ml-service/app/core/capacity.py` computes deliverable tonnes under draft limits
   and flags lightering. **Validation: given only Haldia's published 9.1 m draft, it
   independently computes 43.8 percent maximum Panamax load, against the published
   40 to 50 percent. It was never told this figure.**
3. `ml-service/app/core/cost_model.py` assembles freight, demurrage, port charges,
   lightering and inland cost. Every number is read from
   `data/reference/cost_assumptions.json`, never hard-coded.
4. `ml-service/app/core/decision.py` returns fix now, wait, or split. It is
   hard-wired to refuse "wait" when forecast skill is absent.
5. `ml-service/app/forecasting/` has the naive baseline, feature builder,
   expanding-window CV with skill scoring, Ridge training and interval prediction.
6. `ml-service/static/index.html` is a working three-screen dashboard.
7. `api/src/server.js` is an Express gateway, scaffolded but not required to run.
8. `docs/` contains PROJECT.md, ARCHITECTURE.md, REQUIREMENTS.md and ROADMAP.md.

## Current honest status

Running on scaffolding data the model shows negative skill at almost every horizon.
This is correct, not a bug. The scaffolding is a near-random walk with no signal to
find. **Do not try to make this number look better.** The refusal to recommend
waiting without demonstrated skill is the most defensible feature in the project.

## Known open items

1. OI-01. Plant-to-port distances in `cost_assumptions.json` are assumptions.
   Verify against SAIL's annual report before showing a Ministry of Steel evaluator.
2. Most port fields other than draft, LOA and beam are unverified assumptions.
3. TCE multipliers in `pipeline.py` are placeholders. Replace with published TCE.
4. Real freight rate history has not yet been loaded. Drop a CSV at
   `data/raw/baltic_indices.csv` with columns date, BCI, BPI, BSI, BHSI.
5. React app not yet built. The prototype runs on the static dashboard.

## Standing rules for this project

1. Nobody ships code they cannot explain out loud in sixty seconds.
2. No numeric reference value without a source citation.
3. No accuracy figure without its baseline beside it.
4. No live external API call during a demonstration.
5. Feature freeze two hours before any presentation.

## What I want from you now

[STATE YOUR TASK HERE. For example: build the React front end to replace the static
dashboard. Or: implement the backtested decision policy that simulates our
recommendations against always spot-fixing over five years. Or: help me load real
Baltic index data and re-evaluate skill.]

Please challenge my assumptions where you disagree, distinguish clearly between
verified facts, inferences and assumptions, and do not invent data, statistics or
capabilities. Where something cannot be verified, say so.
