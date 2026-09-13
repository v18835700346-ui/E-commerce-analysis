# AI Product Activation & Retention Growth Analysis

An end-to-end simulated growth analytics project for an AI assistant with chat, writing, image-generation and document-analysis features. The project starts with a tracking plan, validates event quality, diagnoses activation and retention, segments users and evaluates an onboarding experiment.

> The dataset is synthetic and reproducible. All business results below are simulated for analytical practice rather than claims about a real product.

## Business question

New-user acquisition is growing, but not every registered user reaches the product's core value. The project asks:

1. Where do new users drop before receiving their first useful AI result?
2. Which acquisition channels and first-use behaviors are associated with stronger retention?
3. Can personalized onboarding increase activation without harming retention or payment conversion?
4. How should users be segmented for activation, engagement and reactivation operations?

## Growth framework

**North-star metric:** weekly users who complete at least two successful AI tasks.

**24-hour activation:** a registered user receives at least one server-confirmed `result_success` within 24 hours.

The analysis separates the guided activation journey from the commercial journey:

```text
Registration -> onboarding -> core task -> successful result
Successful result -> retained use -> paywall -> subscription
```

The full definitions, event ownership and data-quality rules are documented in [tracking_plan.md](tracking_plan.md).

## Data model

| Table | Grain | Main fields |
|---|---|---|
| `users` | One row per user | registration time, channel, device, city tier, referrer |
| `events` | One row per event | event name/time, session, feature, status, latency, app version |
| `ab_assignments` | One row per user and experiment | assignment time and experiment group |
| `subscriptions` | One row per successful subscription | payment time, plan and revenue |

The generator creates 20,000 users, 438,214 product events and 654 subscriptions across a 90-day observation period. Each user's activity is simulated through the observation cutoff, not truncated after 30 days. Recent cohorts are right-censored and excluded from incomplete observation windows.

## Verified findings

### Activation journey

Among users with a complete 24-hour observation window:

- 71.2% completed onboarding.
- 61.0% of onboarding completers submitted a core task through the guided path.
- 90.2% of guided-path task submitters received a successful result.

The largest relative step loss is between onboarding completion and task submission. Feature-selection friction is a hypothesis, not an established cause. The final ratio is user-level guided-path completion, not per-task technical reliability.

![Activation funnel](images/activation_funnel.svg)

### Acquisition quality

Referral users had 59.1% activation versus 44.9% for paid-social users in this simulated sample. Channel differences are partly encoded in the generator and illustrate downstream quality analysis, not a real-world allocation recommendation.

### Onboarding experiment

Control A used the default homepage. Treatment B asked users to select a goal and then recommended a matching feature template.

| Metric | A | B | Absolute lift | p-value | Interpretation |
|---|---:|---:|---:|---:|---|
| 24-hour activation | 48.32% | 52.68% | +4.36 pp | <0.001 | Primary simulated effect |
| D7 effective use | 11.28% | 12.64% | +1.36 pp | 0.0045 | Exploratory secondary result |
| D7 use among activated users | 20.99% | 21.83% | +0.83 pp | 0.3293 | Descriptive, post-treatment selection |
| Seven-day payment | 2.40% | 2.78% | +0.38 pp | 0.1034 | Inconclusive; not evidence of equivalence |

The sample-ratio-mismatch test found no mismatch signal (`p=0.4883`). All experiment metrics use the same cohort with seven complete observation days. The primary activation difference has a 95% CI of +2.92 to +5.81 pp. D7 is registration-cohort effective use, including late activation. Activated-only comparisons cannot establish causal retention effects; non-significant payment results cannot establish no effect. All results reflect assumed simulation probabilities, not a deployed experiment.

![Experiment outcomes](images/experiment_outcomes.svg)

## Growth recommendations

1. Propose a real randomized onboarding pilot with prospective sample-size planning and predefined guardrail tolerances; do not roll out based on synthetic evidence.
2. Add a post-activation recommendation that introduces a second relevant use case; evaluate retained successful use rather than app opens.
3. Optimize paid-social targeting and landing-message consistency using 24-hour activation as a channel-quality metric.
4. Treat result-sharing referrals as a future hypothesis; this dataset does not model the full referral funnel.
5. Trigger scenario-based reminders for activated users who have not completed a second successful task within three days.

## Repository structure

```text
generate_data.py       Synthetic users, event logs, subscriptions and experiment assignment
validate_data.py       Tracking integrity and event-order checks
schema.sql             MySQL 8.0 table definitions
growth_analysis.sql    North star, funnel, channel, cohort, lifecycle and RFE analysis
ab_analysis.py         SRM, confidence intervals and two-proportion tests
build_outputs.py       Dashboard extracts and GitHub preview charts
tracking_plan.md       Metric definitions, event dictionary and QA rules
outputs/               Tableau-ready summary tables
```

## Run locally

```bash
python -m pip install -r requirements.txt
python generate_data.py
python validate_data.py
python ab_analysis.py
python build_outputs.py
python -m unittest test_snapshot.py
```

The generated CSV files and fingerprint manifest are intentionally excluded from version control. Running `generate_data.py` with the fixed seed reproduces the analyzed dataset. Generation records SHA-256 fingerprints; validation and analysis reject changed input snapshots. Regenerate the complete dataset if a snapshot check fails.

## Skills demonstrated

- Product tracking design and data-quality validation
- Activation funnel and time-to-first-value analysis
- Cohort retention with complete observation windows
- Acquisition-channel quality and lifecycle segmentation
- RFE-based user value segmentation
- A/B experiment design, SRM checks and significance testing
- SQL, Python, pandas, SciPy and dashboard-data preparation

## Validation scope

Python generation, tracking validation, A/B analysis and output builds have been executed.
MySQL queries have been reviewed but not executed against a MySQL server in this environment.
SQL payment denominators include non-payers with zero; use the Python output as the reconciliation reference.
Tracking checks cover task-ID ownership and sequence, experiment consistency, referral chronology and cutoff.
Anonymous identity stitching and live tracking deployment are not implemented.
RFE thresholds are illustrative business rules, not empirically optimized segments.
