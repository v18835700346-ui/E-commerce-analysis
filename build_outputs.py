"""Build reusable dashboard extracts and lightweight project preview charts."""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "outputs"
IMAGE_DIR = ROOT / "images"
ANALYSIS_END = pd.Timestamp("2026-03-31 23:59:59")


def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    users = pd.read_csv(DATA_DIR / "users.csv", parse_dates=["register_time"])
    events = pd.read_csv(DATA_DIR / "events.csv", parse_dates=["event_time"])
    assignments = pd.read_csv(DATA_DIR / "ab_assignments.csv", parse_dates=["assigned_at"])
    subscriptions = pd.read_csv(DATA_DIR / "subscriptions.csv", parse_dates=["subscription_time"])
    return users, events, assignments, subscriptions


def first_event(events: pd.DataFrame, event_name: str) -> pd.Series:
    return events.loc[events["event_name"].eq(event_name)].groupby("user_id")["event_time"].min()


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    IMAGE_DIR.mkdir(exist_ok=True)
    users, events, assignments, subscriptions = load_data()

    eligible_24h = users.loc[users["register_time"] <= ANALYSIS_END - pd.Timedelta(days=1)].copy()
    eligible_7d = users.loc[users["register_time"] <= ANALYSIS_END - pd.Timedelta(days=7)].copy()
    onboarding_view = first_event(events, "onboarding_view")
    onboarding_complete = first_event(events, "onboarding_complete")
    task_submit = first_event(events, "task_submit")
    result_success = first_event(events, "result_success")

    journey = eligible_24h[["user_id", "register_time"]].copy()
    journey["onboarding_view"] = journey["user_id"].map(onboarding_view)
    journey["onboarding_complete"] = journey["user_id"].map(onboarding_complete)
    journey["task_submit"] = journey["user_id"].map(task_submit)
    journey["result_success"] = journey["user_id"].map(result_success)
    deadline = journey["register_time"] + pd.Timedelta(hours=24)
    journey["viewed"] = journey["onboarding_view"].le(deadline)
    journey["completed"] = journey["onboarding_complete"].le(deadline)
    journey["submitted_after_onboarding"] = (
        journey["completed"]
        & journey["task_submit"].ge(journey["onboarding_complete"])
        & journey["task_submit"].le(deadline)
    )
    journey["succeeded_after_submit"] = (
        journey["submitted_after_onboarding"]
        & journey["result_success"].ge(journey["task_submit"])
        & journey["result_success"].le(deadline)
    )
    funnel = pd.DataFrame(
        {
            "step": ["Registered", "Onboarding viewed", "Onboarding completed", "Task submitted", "Result succeeded"],
            "users": [
                len(journey),
                int(journey["viewed"].sum()),
                int(journey["completed"].sum()),
                int(journey["submitted_after_onboarding"].sum()),
                int(journey["succeeded_after_submit"].sum()),
            ],
        }
    )
    funnel["step_rate"] = funnel["users"] / funnel["users"].shift(1)
    funnel.loc[0, "step_rate"] = 1.0
    funnel.to_csv(OUTPUT_DIR / "activation_funnel.csv", index=False)

    active_days = events.loc[events["event_name"].eq("result_success"), ["user_id", "event_time"]].copy()
    active_days["active_date"] = active_days["event_time"].dt.normalize()
    active_days = active_days[["user_id", "active_date"]].drop_duplicates()
    metrics = eligible_7d[["user_id", "register_time", "channel"]].copy()
    metrics["first_success"] = metrics["user_id"].map(result_success)
    metrics["activated_24h"] = metrics["first_success"].le(metrics["register_time"] + pd.Timedelta(hours=24))
    day7 = metrics[["user_id", "register_time"]].copy()
    day7["active_date"] = day7["register_time"].dt.normalize() + pd.Timedelta(days=7)
    day7_keys = pd.MultiIndex.from_frame(active_days[["user_id", "active_date"]])
    metrics["retained_d7"] = pd.MultiIndex.from_frame(day7[["user_id", "active_date"]]).isin(day7_keys)
    first_payment = subscriptions.groupby("user_id")["subscription_time"].min()
    metrics["first_payment"] = metrics["user_id"].map(first_payment)
    metrics["paid_7d"] = metrics["first_payment"].le(metrics["register_time"] + pd.Timedelta(days=7))

    channel_quality = (
        metrics.groupby("channel")
        .agg(
            registered_users=("user_id", "nunique"),
            activation_rate_24h=("activated_24h", "mean"),
            retention_rate_d7=("retained_d7", "mean"),
            payment_rate_7d=("paid_7d", "mean"),
        )
        .reset_index()
        .sort_values("registered_users", ascending=False)
    )
    channel_quality.to_csv(OUTPUT_DIR / "channel_quality.csv", index=False)

    cohort = eligible_7d[["user_id", "register_time"]].copy()
    cohort["cohort_week"] = cohort["register_time"].dt.to_period("W-SUN").dt.start_time
    for day in (1, 3, 7):
        target = cohort["register_time"].dt.normalize() + pd.Timedelta(days=day)
        cohort[f"d{day}_retained"] = pd.MultiIndex.from_arrays([cohort["user_id"], target]).isin(day7_keys)
    retention = (
        cohort.groupby("cohort_week")
        .agg(
            cohort_users=("user_id", "nunique"),
            d1_retention=("d1_retained", "mean"),
            d3_retention=("d3_retained", "mean"),
            d7_retention=("d7_retained", "mean"),
        )
        .reset_index()
    )
    retention.to_csv(OUTPUT_DIR / "cohort_retention.csv", index=False)

    experiment = eligible_7d[["user_id", "register_time"]].merge(
        assignments[["user_id", "experiment_group"]], on="user_id"
    )
    experiment["first_success"] = experiment["user_id"].map(result_success)
    experiment["activated_24h"] = experiment["first_success"].le(experiment["register_time"] + pd.Timedelta(hours=24))
    exp_day7 = experiment["register_time"].dt.normalize() + pd.Timedelta(days=7)
    experiment["retained_d7"] = pd.MultiIndex.from_arrays([experiment["user_id"], exp_day7]).isin(day7_keys)
    experiment["first_payment"] = experiment["user_id"].map(first_payment)
    experiment["paid_7d"] = experiment["first_payment"].le(experiment["register_time"] + pd.Timedelta(days=7))
    experiment_summary = (
        experiment.groupby("experiment_group")
        .agg(
            users=("user_id", "nunique"),
            activation_rate_24h=("activated_24h", "mean"),
            retention_rate_d7=("retained_d7", "mean"),
            payment_rate_7d=("paid_7d", "mean"),
        )
        .reset_index()
    )
    experiment_summary.to_csv(OUTPUT_DIR / "experiment_summary.csv", index=False)

    plt.figure(figsize=(8, 4.5))
    plt.bar(funnel["step"], funnel["users"], color="#3078B8")
    plt.ylabel("Users")
    plt.title("24-hour Guided Activation Journey")
    plt.xticks(rotation=20, ha="right")
    plt.tight_layout()
    plt.savefig(IMAGE_DIR / "activation_funnel.png", dpi=160)
    plt.savefig(IMAGE_DIR / "activation_funnel.svg")
    plt.close()

    exp_plot = experiment_summary.set_index("experiment_group")[["activation_rate_24h", "retention_rate_d7", "payment_rate_7d"]]
    exp_plot.plot(kind="bar", figsize=(8, 4.5), color=["#3078B8", "#52A675", "#E49B3F"])
    plt.ylabel("Rate")
    plt.title("Onboarding Experiment Outcomes")
    plt.xticks(rotation=0)
    plt.legend(["24h activation", "D7 retention", "7d payment"])
    plt.tight_layout()
    plt.savefig(IMAGE_DIR / "experiment_outcomes.png", dpi=160)
    plt.savefig(IMAGE_DIR / "experiment_outcomes.svg")
    plt.close()

    print(funnel.to_string(index=False))
    print("\nChannel quality")
    print(channel_quality.to_string(index=False))


if __name__ == "__main__":
    main()
