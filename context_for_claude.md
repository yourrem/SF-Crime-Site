# Context: SF Crime Tracker — Research Task

## What I Built

I built an end-to-end data engineering + machine learning project called **SF Crime Tracker** that pulls real SFPD incident data from the SF Open Data Portal (Socrata API), loads it into a PostgreSQL database, transforms it with dbt, and displays it on a Flask web app. The project is published as a static demo on GitHub Pages and is intended as a portfolio/resume project.

## The Data

**Source:** SFPD Incident Reports dataset (`wg3w-h783`) from data.sfgov.org  
**Coverage:** January 2018 through present (~1 million+ incident records)  
**Update frequency:** Daily pipeline via Apache Airflow

### What each incident record contains:
- `incident_date` and `incident_datetime` — when the crime occurred (or was reported)
- `incident_category` — the type of crime (see list below)
- `analysis_neighborhood` — SF neighborhood where it occurred (~40 neighborhoods)
- `police_district` — SFPD police district (10 districts)
- `latitude` / `longitude` — mapped to nearest intersection
- `resolution` — outcome (arrest, cite, unfounded, etc.)
- `is_unfounded`, `is_non_criminal`, `is_valid_location` — data quality flags applied by dbt

### Crime categories tracked (top ones by volume):
- Larceny Theft (highest volume — includes retail theft, car break-ins)
- Motor Vehicle Theft
- Assault
- Burglary
- Drug Offense
- Vandalism
- Robbery
- Weapons Carrying Etc
- Suspicious Occ
- Fraud
- Warrant
- Traffic Violation Arrest
- Sexual Assault
- Arson
- Missing Person
- Disorderly Conduct
- Other Miscellaneous

### Web App Pages:
- **Overview** — KPI cards (YTD count, last 7 days, top crime type, most active neighborhood) + interactive intersection map with emoji markers
- **By Neighborhood** — date-range filter, ranked neighborhood table, expandable per-neighborhood crime breakdowns and time-of-day charts
- **By Category** — date-range filter, all crime categories ranked, expandable hourly distribution charts
- **Trends** — daily incident bar/line chart, month-by-month (by year), all-time quarterly chart (Q1 2018–present)
- **Forecast** — Ridge regression model, 30-day forward prediction, confidence band, model metrics (MAE 27.7/day)
- **Crime Clusters** — K-Means spatial clustering map (hotspot circles by color) + neighborhood density map (circle size = geographic spread, opacity = frequency)

---

## The Research Task

I want to add a **Research / Insights** dimension to this project. Specifically, I want to identify meaningful external events — legislation, policy shifts, leadership changes, ballot propositions — that can help explain the crime trends visible in the data between **2019 and 2025**.

The goal is to produce an **annotated timeline** of significant events that correlates with crime patterns in San Francisco. This would let me:
1. Add annotation markers to the Trends chart (vertical lines or flags showing "Prop 36 passed", "DA recalled", etc.)
2. Write up a brief "Key Insights" section on the site with meaningful observations
3. Demonstrate data analyst skills — not just moving data, but interpreting it in real-world context

---

## What I Need You to Research

Please research and compile a structured timeline of **significant events from 2019–2025** that would plausibly affect crime rates or enforcement patterns in San Francisco. For each event, include:

- **Date** (as specific as possible — month/year at minimum)
- **Event name / description**
- **Category** (one of: Legislation, Proposition, Policy Change, Leadership Change, External Event)
- **Expected effect** — which crime categories would likely be affected, and in which direction (increase/decrease/shift in reporting)
- **Relevance to SF specifically** — is this city-level, state-level (CA), or federal?

### Areas to cover:

**1. San Francisco District Attorney changes**
- Chesa Boudin — election, prosecution philosophy, recall
- Brooke Jenkins — appointment, policy reversals
- Any other DA-level policy shifts (charging decisions, diversion programs)

**2. San Francisco Police Department**
- Police chief appointments and departures (Bill Scott era and beyond)
- Staffing levels — retirements, hiring freezes, vacancies (SFPD has had significant staffing shortages)
- Policy changes around enforcement priorities (e.g., drug enforcement, encampment clearances)
- Any consent decrees or federal oversight

**3. California State Legislation**
- **Proposition 47 (2014)** — already in effect but highly relevant; reduced many felonies to misdemeanors, changed theft thresholds — include its ongoing effects
- **AB 109 (2011)** — prison realignment, still impacting county jails
- **Proposition 36 (November 2024)** — reversed parts of Prop 47; increased penalties for retail theft and drug crimes; passed by voters
- **SB 2 (2023)** — police accountability, changes to decertification
- Any legislation specifically targeting retail theft (smash-and-grab epidemic of 2021–2022)
- Fentanyl-related legislation — any laws specifically addressing open-air drug markets, treatment mandates
- Any changes to the felony theft threshold (CA raised it to $950 under Prop 47)

**4. San Francisco Local Ballot Propositions**
- Any SF-specific measures related to public safety, police funding, or criminal justice reform (2019–2025)
- Propositions related to homeless encampments, drug treatment, or open-air drug markets
- Mayor-level executive actions on public safety

**5. COVID-19 and its aftermath (2020–2021)**
- Court closures, deferred prosecutions
- How it affected crime reporting and patterns
- Which categories spiked vs. dropped during lockdowns

**6. Retail Theft Crisis (2021–2022)**
- The organized retail crime wave (Nordstrom, Walgreens closures)
- Any state or local legislative response

**7. Fentanyl / Drug Enforcement**
- The shift from powder to fentanyl in SF's drug market
- Tenderloin drug enforcement operations
- Any Safe Injection Site legislation or decisions
- State-level fentanyl sentencing changes

**8. Mayoral Leadership**
- London Breed — any significant public safety executive orders
- Daniel Lurie — elected November 2024; any early public safety policies

**9. Homelessness Policy**
- CARE Court (SB 1338, 2022) — new conservatorship pathway
- Federal court rulings on encampment clearances (Grants Pass v. Johnson, 2024)
- Any SF-specific encampment sweep policies and their relationship to crime data

---

## Desired Output Format

Please produce two things:

### Part 1: Annotated Timeline
A chronological list of events in this format:

```
DATE | EVENT | CATEGORY | AFFECTED CRIME TYPES | SF RELEVANCE | NOTES
```

Order by date. Include roughly 20–35 significant events total. Be specific about dates.

### Part 2: Key Insights Summary
After the timeline, write 5–8 bullet points summarizing the most meaningful correlations between these events and what we might expect to see in SF crime data. For example:
- "Prop 47 (2014) reduced larceny theft felony threshold — expect elevated larceny reporting post-2014 as misdemeanor filings replaced felony suppression"
- "Chesa Boudin DA recall (June 2022) + Brooke Jenkins appointment likely corresponds with shift in drug offense prosecution rates"

These bullets should be suitable for displaying directly on the site as a "Research Context" section. Write them as if addressing someone reading the SF Crime Tracker dashboard — data-literate but not a criminal justice expert.

### Part 3: Chart Annotation Suggestions
List the 8–10 most important events that should be shown as vertical line annotations on the daily/monthly trends chart, with suggested label text (keep labels under 5 words). Format:

```
DATE | SHORT LABEL | COLOR SUGGESTION
```
Use color suggestions like: red (increase expected), blue (neutral/policy change), green (decrease expected), orange (external event like COVID).

---

## Additional Context for Your Research

- The data shows **daily incident counts** ranging roughly from 100–250 incidents per day in SF over this period
- The city has ~875,000 residents across 49 square miles
- SF has a historically high property crime rate relative to national averages
- The Tenderloin and SoMa neighborhoods consistently appear as the highest-crime areas in this data
- The data covers **reported** incidents only — changes in reporting behavior (e.g., people stop reporting because "nothing happens") are a known confound
- Motor Vehicle Theft and Larceny Theft are the highest-volume categories and most sensitive to policy changes around prosecution thresholds
- Drug Offense numbers are heavily influenced by enforcement priority shifts (if police aren't arresting for drug use, the count drops — not because drug use dropped)

Please be as specific as possible with dates and cite the type of source (e.g., "SF Chronicle reported," "California Legislative Counsel confirmed," "ballot measure certified") where relevant so I can verify independently.
