"""Analyze the onboarding experiment with SRM and two-proportion tests."""

from math import sqrt
from pathlib import Path

import pandas as pd
from scipy.stats import chi2, norm
from validate_data import verify_snapshot


DATA_DIR = Path(__file__).parent / "data"
ANALYSIS_END = pd.Timestamp("2026-03-31 23:59:59")


def two_proportion_test(success_a: int, n_a: int, success_b: int, n_b: int) -> dict:
    rate_a = success_a / n_a
    rate_b = success_b / n_b
    pooled = (success_a + success_b) / (n_a + n_b)
    pooled_se = sqrt(pooled * (1 - pooled) * (1 / n_a + 1 / n_b))
    z_score = (rate_b - rate_a) / pooled_se
    p_value = 2 * norm.sf(abs(z_score))

    unpooled_se = sqrt(rate_a * (1 - rate_a) / n_a + rate_b * (1 - rate_b) / n_b)
    delta = rate_b - rate_a
    ci_low = delta - 1.96 * unpooled_se
    ci_high = delta + 1.96 * unpooled_se
    return {
        "rate_a": rate_a,
        "rate_b": rate_b,
        "absolute_lift": delta,
        "relative_lift": delta / rate_a,
        "z_score": z_score,
        "p_value": p_value,
        "ci_low": ci_low,
        "ci_high": ci_high,
    }


def main() -> None:
    verify_snapshot(DATA_DIR)
    (DATA_DIR.parent / "outputs").mkdir(exist_ok=True)
    users = pd.read_csv(DATA_DIR / "users.csv", parse_dates=["register_time"])
    events = pd.read_csv(DATA_DIR / "events.csv", parse_dates=["event_time"])
    assignments = pd.read_csv(DATA_DIR / "ab_assignments.csv", parse_dates=["assigned_at"])
    subscriptions = pd.read_csv(DATA_DIR / "subscriptions.csv", parse_dates=["subscription_time"])

    group_counts = assignments["experiment_group"].value_counts().sort_index()
    expected = len(assignments) / 2
    chi_square = (((group_counts - expected) ** 2) / expected).sum()
    srm_p_value = 1 - chi2.cdf(chi_square, df=1)

    success_events = events.loc[events["event_name"].eq("result_success"), ["user_id", "event_time"]]
    first_success = success_events.groupby("user_id")["event_time"].min()
    base = users[["user_id", "register_time"]].merge(assignments[["user_id", "experiment_group"]], on="user_id")
    base["first_success_time"] = base["user_id"].map(first_success)
    base["activated_24h"] = base["first_success_time"].le(base["register_time"] + pd.Timedelta(hours=24))

    active_days = events.loc[events["event_name"].eq("result_success"), ["user_id", "event_time"]].copy()
    active_days["activity_date"] = active_days["event_time"].dt.normalize()
    active_days = active_days[["user_id", "activity_date"]].drop_duplicates()
    day7 = base[["user_id", "register_time"]].copy()
    day7["day7_date"] = day7["register_time"].dt.normalize() + pd.Timedelta(days=7)
    day7 = day7.merge(active_days, left_on=["user_id", "day7_date"], right_on=["user_id", "activity_date"], how="left")
    base["retained_d7"] = day7["activity_date"].notna().to_numpy()

    first_payment = subscriptions.groupby("user_id")["subscription_time"].min()
    base["first_payment_time"] = base["user_id"].map(first_payment)
    base["paid_7d"] = base["first_payment_time"].le(base["register_time"] + pd.Timedelta(days=7))

    # Use the same mature registration cohort across all reported experiment metrics.
    observed_24h = base.loc[base["register_time"] <= ANALYSIS_END - pd.Timedelta(days=7)]
    observed_7d = base.loc[base["register_time"] <= ANALYSIS_END - pd.Timedelta(days=7)]

    def evaluate(frame: pd.DataFrame, metric: str) -> dict:
        agg = frame.groupby("experiment_group")[metric].agg(["sum", "count"])
        return two_proportion_test(int(agg.loc["A", "sum"]), int(agg.loc["A", "count"]), int(agg.loc["B", "sum"]), int(agg.loc["B", "count"]))

    results = {
        "24h_activation": evaluate(observed_24h, "activated_24h"),
        "d7_retention": evaluate(observed_7d, "retained_d7"),
        "d7_retention_among_activated": evaluate(
            observed_7d.loc[observed_7d["activated_24h"]], "retained_d7"
        ),
        "7d_payment": evaluate(observed_7d, "paid_7d"),
    }

    print(f"SRM p-value: {srm_p_value:.4f}")
    first_day_results = events.loc[events.event_name.isin(["result_success", "result_failed"])].merge(
        observed_24h[["user_id", "register_time"]], on="user_id"
    )
    first_day_results = first_day_results.loc[
        first_day_results.event_time <= first_day_results.register_time + pd.Timedelta(hours=24)
    ]
    print("Task failure rates (descriptive):", first_day_results.assign(
        failed=first_day_results.event_name.eq("result_failed")
    ).groupby("experiment_group").failed.mean().to_dict())
    for metric, result in results.items():
        print(
            f"{metric}: A={result['rate_a']:.2%}, B={result['rate_b']:.2%}, "
            f"lift={result['absolute_lift']:.2%} ({result['relative_lift']:.1%}), "
            f"95% CI=[{result['ci_low']:.2%}, {result['ci_high']:.2%}], p={result['p_value']:.6g}"
        )
    verify_snapshot(DATA_DIR)
    pd.DataFrame(results).T.to_csv(DATA_DIR.parent / "outputs" / "ab_statistics.csv", index_label="metric")
    print("Activated-only comparisons are descriptive: activation is a post-treatment selection.")
    print("Secondary p-values are exploratory and unadjusted. Non-significance does not establish equivalence.")

    first_value_minutes = (
        observed_24h.loc[observed_24h["activated_24h"]]
        .assign(
            first_value_minutes=lambda x: (
                x["first_success_time"] - x["register_time"]
            ).dt.total_seconds() / 60
        )
        .groupby("experiment_group")["first_value_minutes"]
        .median()
    )
    print(
        "median_first_value_minutes: "
        f"A={first_value_minutes['A']:.1f}, B={first_value_minutes['B']:.1f}"
    )


if __name__ == "__main__":
    main()
