"""Validate tracking integrity before any growth analysis is run."""

from pathlib import Path

import pandas as pd


DATA_DIR = Path(__file__).parent / "data"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    users = pd.read_csv(DATA_DIR / "users.csv", parse_dates=["register_time"])
    events = pd.read_csv(DATA_DIR / "events.csv", parse_dates=["event_time"])
    assignments = pd.read_csv(DATA_DIR / "ab_assignments.csv", parse_dates=["assigned_at"])
    subscriptions = pd.read_csv(DATA_DIR / "subscriptions.csv", parse_dates=["subscription_time"])

    require(users["user_id"].is_unique, "user_id must be unique")
    require(events["event_id"].is_unique, "event_id must be unique")
    require(assignments["user_id"].is_unique, "each user must have one experiment assignment")
    require(events["user_id"].isin(users["user_id"]).all(), "events contain unknown users")
    require(subscriptions["user_id"].isin(users["user_id"]).all(), "subscriptions contain unknown users")

    event_groups = events[["user_id", "experiment_group"]].drop_duplicates()
    require(not event_groups["user_id"].duplicated().any(), "a user appears in multiple experiment groups")
    assignment_groups = assignments.set_index("user_id")["experiment_group"]
    observed_groups = event_groups.set_index("user_id")["experiment_group"]
    require(assignment_groups.equals(observed_groups.reindex(assignment_groups.index)), "event and assignment groups disagree")

    registration = users.set_index("user_id")["register_time"]
    require((events["event_time"] >= events["user_id"].map(registration)).all(), "event occurred before registration")

    first_submit = (
        events.loc[events["event_name"].eq("task_submit")]
        .groupby("user_id")["event_time"]
        .min()
    )
    first_result = (
        events.loc[events["event_name"].isin(["result_success", "result_failed"])]
        .groupby("user_id")["event_time"]
        .min()
    )
    paired = pd.concat([first_submit.rename("submit"), first_result.rename("result")], axis=1).dropna()
    require((paired["result"] >= paired["submit"]).all(), "a result occurred before its task submission")

    event_counts = events["event_name"].value_counts()
    require(event_counts.get("register_success", 0) == len(users), "each user must have one registration event")
    require(event_counts.get("result_success", 0) > 0, "successful result events are missing")

    print("Tracking validation passed")
    print(f"duplicate_event_rate={events['event_id'].duplicated().mean():.4%}")
    print(f"orphan_event_rate={(~events['user_id'].isin(users['user_id'])).mean():.4%}")
    print("experiment_users=" + assignments["experiment_group"].value_counts().sort_index().to_dict().__str__())


if __name__ == "__main__":
    main()
