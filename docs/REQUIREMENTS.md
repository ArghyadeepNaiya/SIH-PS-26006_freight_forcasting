# REQUIREMENTS.md

Intelligent Freight Forecasting and Charter Decision System

Requirement identifiers are stable. Do not renumber them.

---

## 1. Functional requirements

### 1.1 Cargo input

FR-01. The system shall accept a cargo requirement consisting of cargo type,
quantity in tonnes, origin region, earliest acceptable arrival date and latest
acceptable arrival date.

FR-02. The system shall accept an optional destination plant or destination port.
When neither is supplied, the system shall evaluate all East Coast discharge ports.

FR-03. The system shall present no more than five mandatory input fields. All other
parameters shall carry defaults.

### 1.2 Constraint filtering

FR-04. The system shall evaluate every combination of vessel class and discharge port
against maximum draft, maximum length overall, maximum beam and maximum deadweight.

FR-05. The system shall mark infeasible combinations as rejected rather than removing
them from the response.

FR-06. Each rejection shall state the failed constraint, the port limit value, the
vessel requirement value, and the source citation for the port limit.

### 1.3 Capacity and cost

FR-07. The system shall compute deliverable tonnes for each feasible combination,
accounting for draft limited partial loading.

FR-08. The system shall flag whether lightering at anchorage is required.

FR-09. The system shall compute landed cost per tonne as total voyage cost divided by
deliverable tonnes, not by nominal vessel capacity.

FR-10. Total voyage cost shall comprise freight, port charges, expected demurrage,
lightering cost where applicable and inland movement cost.

FR-11. Every cost component shall be individually visible to the user.

### 1.4 Forecasting

FR-12. The system shall forecast freight rates separately for each vessel class.

FR-13. Every forecast shall be accompanied by a prediction interval, never a bare
point estimate.

FR-14. The system shall compute and display a skill score against a naive persistence
baseline at every forecast horizon.

FR-15. Where the skill score is not positive at a horizon, the interface shall display
a no skill notice instead of a confident forecast.

### 1.5 Recommendation

FR-16. The system shall return exactly one of three recommended actions. Fix now,
wait, or split the cargo.

FR-17. The recommendation shall be expressed in plain language, not as a numeric
confidence value.

FR-18. The recommendation shall state the two or three factors that most influenced
it.

### 1.6 Transparency

FR-19. Every numeric value displayed shall be traceable to either a data source or a
named assumption.

FR-20. Every assumption shall be user editable, and the recommendation shall recompute
when an assumption changes.

FR-21. Port constraint values shall display their source citation on demand.

### 1.7 Persistence

FR-22. The system shall allow a scenario to be saved and retrieved.

FR-23. Phase two. The system shall record each recommendation, the user's actual
decision, and the subsequent market outcome.

---

## 2. Non functional requirements

NFR-01. A recommendation request shall return within one second under demo
conditions.

NFR-02. The system shall operate with no internet connection once data is seeded.

NFR-03. The system shall run on a standard laptop. No GPU, no cluster.

NFR-04. Model retraining shall complete within five minutes on the full history.

NFR-05. Every reference data value shall carry a source field. A numeric reference
value without a source shall not be merged into the repository.

NFR-06. Forecast evaluation shall use expanding window time series cross validation.
Random train test splits are prohibited.

NFR-07. The interface shall never display an accuracy figure without the corresponding
baseline figure beside it.

---

## 3. Data requirements

### 3.1 Required for the prototype

DR-01. Daily freight rate history for Capesize, Panamax, Supramax and Handysize.
Minimum three years, target ten years. Sub indices are required. The headline
composite index alone is not sufficient, because vessel selection is inherently a per
class question.

DR-02. Port constraint reference data for Paradip, Visakhapatnam, Gangavaram,
Gopalpur, Dhamra, Haldia and Sagar Sandheads. Fields are maximum draft, maximum
length overall, maximum beam, maximum deadweight, lightering availability.

DR-03. Vessel class reference data. Deadweight range, typical length overall, typical
beam, typical laden draft.

DR-04. Approximate sailing distances for each origin and discharge port pair.

### 3.2 Desirable, phase one and two

DR-05. Commodity price history for coking coal, thermal coal and iron ore.
DR-06. Bunker fuel price history.
DR-07. Economic indicators. An equity index and a dollar index, since published
research on machine learning forecasting of the dry bulk index identified equity
indices, commodity indices and the dollar index as the dominant statistical drivers.
DR-08. Published port position reports for congestion, available from Indian port
authorities and shipping agents.

### 3.3 Data we will not have, and must say so

DR-09. Actual SAIL fixture history, demurrage records and negotiated port tariffs.
DR-10. Licensed broker data from commercial providers.
DR-11. Forward freight agreement curves, which represent the market's own forward
view and would be the honest benchmark for any forecast skill claim.
DR-12. Comprehensive real time vessel positions for the Bay of Bengal.

Consequence. All cost assumptions are drawn from public tariffs, labelled as
assumptions in the interface, and user editable.

### 3.4 Licensing

DR-13. Before any data source is used, its terms of use shall be recorded in
data/reference/SOURCES.md together with the date checked and the person who checked
it. Index data is commercially licensed by its publisher and free mirrors vary in
their terms.

---

## 4. Software environment

### 4.1 Python service

Python three point eleven or later.

Packages.
1. fastapi
2. uvicorn
3. pydantic
4. pandas
5. numpy
6. scikit-learn
7. statsmodels
8. lightgbm
9. shap
10. scipy
11. pymongo
12. python-dotenv
13. pytest

### 4.2 Node service

Node twenty or later.

Packages.
1. express
2. mongoose
3. cors
4. dotenv
5. axios
6. morgan

### 4.3 Web

1. react
2. react-router-dom
3. recharts
4. axios
5. vite

### 4.4 Infrastructure

1. MongoDB seven or later.
2. Docker and Docker Compose.

### 4.5 Explicitly not used

Deep learning frameworks, graph databases, message queues, cloud services and vector
databases are not required by this system. If any is added later, the pull request
must state which requirement it satisfies.

---

## 5. Acceptance criteria for the prototype

The prototype is complete when all of the following are demonstrable end to end.

AC-01. A user enters seventy five thousand tonnes of coking coal from Australia with
an arrival window, and receives a ranked set of options within one second.

AC-02. At least one option is shown as rejected, with the failing constraint named and
the port limit cited.

AC-03. A draft limited option displays deliverable tonnes lower than nominal capacity,
and the resulting landed cost per tonne reflects the reduced quantity.

AC-04. The cost breakdown expands to show every component.

AC-05. The forecast chart displays a widening band and the skill score against naive
persistence.

AC-06. Changing one assumption in the assumptions panel changes the ranking.

AC-07. The entire flow works with networking disabled.

---

## 6. Open items requiring team verification

OI-01. Which SAIL plant is served by which discharge port. Rourkela, Bokaro,
Durgapur, Burnpur and Bhilai each have their own inland logistics, and the inland leg
materially changes landed cost. Verify against SAIL's annual report before displaying
any plant to port mapping.

OI-02. Confirm current published draft figures directly with each port authority.
Secondary sources disagree.

OI-03. Confirm the licence terms of the chosen freight rate data source.

OI-04. Confirm the 2026 idea presentation template slide count on sih.gov.in.
