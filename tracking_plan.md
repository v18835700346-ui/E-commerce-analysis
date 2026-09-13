# Tracking Plan

## Business objective

The product is a simulated AI assistant offering chat, writing, image generation and document analysis. The growth problem is to improve the share of new users who reach value within 24 hours and return to complete useful tasks.

## Metric definitions

| Metric | Definition |
|---|---|
| North-star metric | Weekly users with at least two successful AI results |
| 24-hour activation | Registered user receives at least one `result_success` within 24 hours |
| D1 / D3 / D7 retention | User receives at least one successful result on the exact nth calendar day after registration |
| First-value time | Time from `register_success` to the first `result_success` |
| 7-day payment conversion | Successful subscription within seven days after registration |

These are registration-cohort effective-use rates; D7 may include a user's first successful use. Activated-user return rates are separate descriptive measures. A server success is a proxy for value, not proof of satisfaction. The twice-per-week north star is a proposed threshold, not empirically validated.

## Event dictionary

| Event | Trigger | Key properties | Collection side |
|---|---|---|---|
| `register_success` | Account registration succeeds | channel, device | Server |
| `onboarding_view` | Onboarding is displayed | experiment_id, experiment_group | Client |
| `interest_selected` | User submits interests in variant B | experiment_group | Client |
| `onboarding_complete` | Final onboarding step completes | experiment_group | Client |
| `feature_click` | User selects a core AI feature | feature_type | Client |
| `task_submit` | AI task reaches the server | feature_type | Server |
| `result_success` | A usable result is returned | feature_type, latency_ms | Server |
| `result_failed` | The task fails | feature_type, latency_ms | Server |
| `result_save` | User saves a result | feature_type | Client |
| `result_share` | User shares a result | feature_type | Client |
| `app_open` | A new session begins | device, app_version | Client |
| `subscription_view` | Paywall is displayed | plan entry point | Client |
| `payment_success` | Payment callback succeeds | plan, amount | Server |

## Common properties

Every event contains `event_id`, `user_id`, `anonymous_id`, `session_id`, `event_time`, `app_version`, `experiment_id` and `experiment_group`. Task submissions and results also contain `task_id`. Channel and device are joined from users; plan and amount from subscriptions. Anonymous IDs are reserved fields only: pre-registration events and identity stitching are not implemented.

## Data-quality controls

1. `event_id` must be unique; duplicate rate is monitored before aggregation.
2. Every event and subscription must map to an existing user.
3. A user can belong to only one group in the same experiment.
4. Registration must precede all product events; task submission must precede its result.
5. Client clicks and server-confirmed successes are separate events. Activation uses the server event.
6. Cohorts that have not completed the observation window are excluded from D1, D3 and D7 denominators.
7. App-version discontinuity monitoring is a proposed future control, not implemented.

## Experiment

- Control A: default homepage with self-directed feature selection.
- Treatment B: onboarding asks for the user's goal and recommends a relevant feature template.
- Primary metric: 24-hour activation rate.
- Secondary metrics: D7 retained-task rate and seven-day payment conversion.
- Guardrails: result failure rate and median first-value time.
- Checks: 50/50 sample-ratio mismatch test, mutually exclusive assignment, complete observation windows, two-proportion tests and 95% confidence intervals.

## Simulation limitations

Both groups have a basic onboarding flow; B adds interest selection and recommended templates.
All probabilities are explicit modeling assumptions, including treatment and channel effects.
They are not evidence that these effects exist in a real product. The seed is fixed, not searched for significance.
20,000 users is a demonstration sample, not a completed prospective power calculation.
The experiment uses all assigned users with seven complete days of observation.
Secondary p-values are exploratory and unadjusted. Activated-only and time-to-value among activated users are post-treatment selected comparisons, not causal estimates.
Paywall events currently exist only for purchasers; paywall-to-payment conversion cannot be estimated from this dataset.
Data is simulated after registration only. Full subscription renewal, referral-loop conversion and live tracking deployment are out of scope.
