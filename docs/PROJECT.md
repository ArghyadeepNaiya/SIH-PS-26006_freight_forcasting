# PROJECT.md

Intelligent Freight Forecasting and Charter Decision System

Smart India Hackathon 2026. Problem Statement SIH26006.
Organisation. Ministry of Steel. Department. SAIL.

---

## 1. One sentence definition

The user does not tell the system which ship to use. The system tells the user.

A chartering manager enters a cargo requirement. The system returns a ranked set of
vessel class and discharge port combinations, each priced as a delivered cost per
tonne, together with a recommendation to fix now, wait, or split the cargo.

---

## 2. The four questions the product answers

Everything on screen must serve one of these. If it does not, delete it.

1. Which East Coast discharge port should this cargo come into.
2. Which vessel class should be chartered.
3. Should the charter be fixed today, or should we wait.
4. Should this be a single spot fix or part of a longer term contract.

---

## 3. Who the user is

A chartering or logistics manager at a steel producer. This person receives a
requirement from a plant, for example seventy five thousand tonnes of coking coal
needed by mid November. They currently solve it by calling brokers daily.

They are not a data scientist. They will not read a confusion matrix. They will
distrust any number they cannot trace to an assumption.

---

## 4. Pain points being solved

1. Daily spot market exploration produces reactive decisions and missed savings.
2. Freight rates are extremely volatile, so timing a fix badly is expensive.
3. East Coast ports differ sharply in draft, so the cheapest freight rate is often
   not the cheapest delivered cargo.
4. Vessel idle time and demurrage arise from planning that ignores port limits.
5. There is no structured view of what is actually driving the market.
6. Procurement is stuck on single spot contracts when the stated objective is to
   move to short and medium term multiple voyage contracts.

---

## 5. The central insight

A voyage costs approximately the same whether the ship sails full or half full.
Therefore the number that matters is total voyage cost divided by the tonnes that
can actually be discharged, not divided by the vessel's nominal capacity.

At a draft restricted port these two numbers diverge sharply. Public sources record
Haldia with a maximum draft depth of about nine point one metres, accommodating
Panamax vessels carrying only forty to fifty percent of capacity. Dhamra is recorded
at about eighteen metres of draft and can take super Capesize vessels directly
without lighterage.

So a Panamax discharging at Haldia may deliver roughly thirty thousand tonnes while
costing close to what a full voyage costs. The freight rate looked cheap. The
delivered cost was not.

This single divergence is the product's reason to exist.

---

## 6. Scope

### 6.1 In scope

1. Dry bulk and heavy break bulk cargo. Coking coal, thermal coal, limestone, iron
   ore, manganese ore and steel scrap.
2. Origins named in the problem statement. Australia, United States, Mozambique,
   Russia and Indonesia.
3. East Coast Indian discharge ports. Paradip, Visakhapatnam, Gangavaram, Gopalpur,
   Dhamra, Haldia and Sagar Sandheads.
4. Vessel classes. Handysize, Supramax, Panamax and Capesize.
5. Freight rate forecasting per vessel class with explicit uncertainty.
6. Port constraint feasibility filtering.
7. Landed cost per tonne calculation.
8. Fix now, wait or split recommendation.

### 6.2 Out of scope

1. Live vessel tracking. Free global AIS coverage of the Bay of Bengal is limited
   and we will not promise what we cannot deliver.
2. Actual contract execution or broker integration.
3. Tanker, container or general cargo trades.
4. West Coast ports in the first version.

---

## 7. Feature phasing

### Phase 0. Prototype for the idea presentation

1. Decision Console with five inputs and ranked option cards.
2. Hard constraint filtering with visible rejections.
3. Landed cost per tonne with an expandable breakdown.
4. Rate history chart with a forecast band.
5. Naive persistence baseline and one learned model, with a skill score displayed.

### Phase 1. Internal hackathon

6. Port Intelligence screen with cited constraint sources.
7. Congestion and expected waiting days.
8. Editable assumptions panel.
9. Backtested decision policy against always spot fixing.
10. Driver attribution using SHAP.

### Phase 2. Grand Finale

11. Contract structure recommendation. Spot, period or contract of affreightment.
12. Parcel splitting optimisation.
13. Scenario stress testing.
14. Decision Log with outcome tracking.
15. One page printable recommendation export.
16. Docker packaging for offline deployment.

---

## 8. The three screens

### Screen 1. Decision Console

Purpose. Produce the answer.

Inputs. Cargo type, quantity in tonnes, origin region, required arrival window,
and destination which may be a specific plant or left to the system to choose.

Outputs. A plain English recommendation banner. Three to five ranked option cards
showing landed cost per tonne, deliverable tonnes and a one line reason. At least
one deliberately shown rejected option with the reason for rejection. An expandable
cost breakdown covering freight, port charges, expected demurrage, lightering and
inland movement.

### Screen 2. Market and Forecast

Purpose. Make the number on Screen 1 believable.

Contents. Historical rates per vessel class. Forecast shown as a widening band, not
a line. A forecast honesty panel stating how much better the model is than assuming
tomorrow equals today, at each horizon. Driver attribution. Current market position
relative to the last two years.

### Screen 3. Port Intelligence

Purpose. Answer the question why an option was ruled out.

Contents. Each port with maximum draft, length overall, beam and deadweight limits,
each value carrying a clickable source citation. Largest vessel class that can berth
fully loaded. Loading percentage achievable for larger classes. Congestion and
typical waiting days. Lightering availability and cost.

---

## 9. Non negotiable design rules

1. One screen produces the answer. The other screens justify it.
2. Five inputs maximum. Everything else has a default that can be overridden.
3. Recommendations are in plain language. Not confidence zero point seven two.
4. Every number on screen is clickable and reveals the assumption behind it.
5. Every assumption is user editable. A chartering manager knows their own port
   costs better than our model does.
6. Uncertainty is always visible. A band, never a bare line.
7. Where the model has no forecasting skill at a horizon, the interface says so.

---

## 10. Honesty commitments

These exist because they are the difference between a credible submission and a
generic one. They are to be stated in the presentation, not hidden.

1. Freight indices behave close to a random walk at short horizons. We report a
   skill score against naive persistence and we publish the horizons where we have
   no skill.
2. Port cost, demurrage and inland cost figures are assumptions drawn from public
   tariffs, clearly labelled as such, and user editable.
3. Every port constraint value carries a source citation because published sources
   disagree with each other.
4. We do not claim real time vessel tracking or licensed broker data.

---

## 11. Team of six, role assignment

1. Domain lead. Owns the cost model, the assumptions register and the hand
   calculation that validates it. Owns the answer to every domain question at judging.
2. Data lead. Owns rate history ingestion, the reference data files and licence
   verification of every data source.
3. Forecasting lead. Owns the baseline, the models, the expanding window evaluation
   and the skill score.
4. Backend lead. Owns the FastAPI service, the constraint engine and the Express
   gateway.
5. Frontend lead one. Owns the Decision Console.
6. Frontend lead two. Owns Market and Forecast, Port Intelligence, and the deck.

Rule. Nobody ships code they cannot explain out loud in sixty seconds.
