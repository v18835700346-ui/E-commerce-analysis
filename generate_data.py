"""Generate a reproducible event-level dataset for an AI assistant growth case."""

from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd


SEED = 20260911
N_USERS = 20_000
START_DATE = pd.Timestamp("2026-01-01")
END_DATE = pd.Timestamp("2026-03-31 23:59:59")
DATA_DIR = Path(__file__).parent / "data"

CHANNELS = ["organic", "paid_social", "creator", "referral", "app_store"]
CHANNEL_P = [0.25, 0.28, 0.20, 0.12, 0.15]
DEVICES = ["android", "ios"]
FEATURES = ["chat", "writing", "image", "document"]
PLANS = {"monthly": 29.0, "quarterly": 79.0, "annual": 249.0}


def clipped_probability(value: float) -> float:
    return float(np.clip(value, 0.01, 0.98))


def main() -> None:
    rng = np.random.default_rng(SEED)
    DATA_DIR.mkdir(exist_ok=True)

    day_offsets = rng.choice(np.arange(90), size=N_USERS, replace=True)
    second_offsets = rng.integers(0, 86_400, size=N_USERS)
    register_time = START_DATE + pd.to_timedelta(day_offsets, unit="D") + pd.to_timedelta(second_offsets, unit="s")
    channels = rng.choice(CHANNELS, size=N_USERS, p=CHANNEL_P)
    devices = rng.choice(DEVICES, size=N_USERS, p=[0.61, 0.39])
    groups = rng.choice(["A", "B"], size=N_USERS)
    user_quality = rng.normal(0, 1, size=N_USERS)

    users = pd.DataFrame(
        {
            "user_id": [f"u{i:06d}" for i in range(1, N_USERS + 1)],
            "anonymous_id": [f"a{i:06d}" for i in range(1, N_USERS + 1)],
            "register_time": register_time,
            "channel": channels,
            "device": devices,
            "city_tier": rng.choice(["tier_1", "tier_2", "tier_3_plus"], N_USERS, p=[0.31, 0.39, 0.30]),
            "referrer_user_id": "",
        }
    )

    referral_mask = users["channel"].eq("referral")
    referral_count = int(referral_mask.sum())
    for idx in users.index[referral_mask]:
        candidates = users.loc[(~referral_mask) & (users.register_time < users.at[idx, "register_time"]), "user_id"]
        if len(candidates):
            users.at[idx, "referrer_user_id"] = rng.choice(candidates)
        else:
            users.at[idx, "channel"] = "organic"

    assignments = pd.DataFrame(
        {
            "user_id": users["user_id"],
            "experiment_id": "onboarding_interest_v1",
            "experiment_group": groups,
            "assigned_at": users["register_time"],
        }
    )

    events: list[dict] = []
    subscriptions: list[dict] = []
    event_seq = 1
    active_tasks = {}

    def add_event(
        user_idx: int,
        event_time: pd.Timestamp,
        event_name: str,
        session_no: int,
        feature_type: str = "",
        result_status: str = "",
        latency_ms: int | str = "",
    ) -> None:
        nonlocal event_seq
        if event_time > END_DATE:
            return
        if event_name == "task_submit":
            active_tasks[user_idx] = f"t{event_seq:09d}"
        events.append(
            {
                "event_id": f"e{event_seq:09d}",
                "task_id": active_tasks.get(user_idx, "") if event_name in ("task_submit", "result_success", "result_failed") else "",
                "user_id": users.at[user_idx, "user_id"],
                "anonymous_id": users.at[user_idx, "anonymous_id"],
                "session_id": f"s{user_idx + 1:06d}_{session_no:02d}",
                "event_time": event_time,
                "event_name": event_name,
                "feature_type": feature_type,
                "result_status": result_status,
                "latency_ms": latency_ms,
                "experiment_id": "onboarding_interest_v1",
                "experiment_group": groups[user_idx],
                "app_version": "3.2.0" if event_time < pd.Timestamp("2026-02-15") else "3.3.0",
            }
        )
        event_seq += 1

    channel_activation = {
        "organic": 0.02,
        "paid_social": -0.05,
        "creator": 0.04,
        "referral": 0.08,
        "app_store": 0.01,
    }
    feature_success = {"chat": 0.94, "writing": 0.91, "image": 0.84, "document": 0.88}
    feature_retention = {"chat": 0.00, "writing": 0.04, "image": -0.03, "document": 0.07}

    for i in range(N_USERS):
        reg = users.at[i, "register_time"]
        channel = users.at[i, "channel"]
        group = groups[i]
        quality = user_quality[i]
        session_no = 1
        add_event(i, reg, "register_success", session_no)
        add_event(i, reg + pd.Timedelta(seconds=int(rng.integers(3, 25))), "onboarding_view", session_no)

        p_onboarding = clipped_probability(0.67 + (0.09 if group == "B" else 0) + 0.04 * quality)
        onboarding_complete = rng.random() < p_onboarding
        onboarding_end = reg + pd.Timedelta(minutes=float(rng.uniform(0.4, 4.5)))
        if onboarding_complete:
            if group == "B":
                add_event(i, onboarding_end - pd.Timedelta(seconds=15), "interest_selected", session_no)
            add_event(i, onboarding_end, "onboarding_complete", session_no)

        p_task = clipped_probability(
            0.42
            + (0.15 if onboarding_complete else 0)
            + (0.035 if group == "B" else 0)
            + channel_activation[channel]
            + 0.06 * quality
        )
        attempted = rng.random() < p_task
        activated = False
        first_feature = ""
        first_value_time = None
        if attempted:
            base_feature_p = [0.37, 0.24, 0.23, 0.16]
            if group == "B":
                base_feature_p = [0.34, 0.25, 0.22, 0.19]
            first_feature = str(rng.choice(FEATURES, p=base_feature_p))
            task_time = max(onboarding_end, reg + pd.Timedelta(minutes=float(rng.uniform(1, 90))))
            add_event(i, task_time - pd.Timedelta(seconds=20), "feature_click", session_no, first_feature)
            add_event(i, task_time, "task_submit", session_no, first_feature)
            latency = int(max(400, rng.lognormal(mean=7.6, sigma=0.45)))
            success = rng.random() < clipped_probability(feature_success[first_feature] + 0.015 * quality)
            result_time = task_time + pd.Timedelta(milliseconds=latency)
            add_event(
                i,
                result_time,
                "result_success" if success else "result_failed",
                session_no,
                first_feature,
                "success" if success else "failed",
                latency,
            )
            activated = bool(success and result_time <= reg + pd.Timedelta(hours=24))
            if activated:
                first_value_time = result_time
                if rng.random() < 0.18:
                    add_event(i, result_time + pd.Timedelta(seconds=30), "result_save", session_no, first_feature)
                if rng.random() < 0.07:
                    add_event(i, result_time + pd.Timedelta(seconds=50), "result_share", session_no, first_feature)

        retention_base = (
            0.14 + 0.10 * max(quality, -1) + feature_retention[first_feature]
            if activated
            else 0.025 + 0.018 * max(quality, -1)
        )
        for day in range(1, (END_DATE.normalize() - reg.normalize()).days + 1):
            event_day = reg.normalize() + pd.Timedelta(days=day)
            if event_day > END_DATE.normalize():
                break
            decay = (0.18 if activated else 0.045) * np.exp(-day / 6.5)
            milestone = 0
            p_return = clipped_probability(retention_base + decay + milestone)
            if rng.random() < p_return:
                session_no += 1
                open_time = event_day + pd.Timedelta(seconds=int(rng.integers(8 * 3600, 23 * 3600)))
                add_event(i, open_time, "app_open", session_no)
                if activated or rng.random() < 0.68:
                    tasks = 1 + int(activated and rng.random() < clipped_probability(0.20 + 0.08 * quality))
                    for task_no in range(tasks):
                        feature = first_feature if first_feature and rng.random() < 0.62 else str(rng.choice(FEATURES))
                        task_time = open_time + pd.Timedelta(minutes=2 + task_no * 5)
                        add_event(i, task_time, "task_submit", session_no, feature)
                        latency = int(max(400, rng.lognormal(mean=7.55, sigma=0.42)))
                        success = rng.random() < feature_success[feature]
                        result_time = task_time + pd.Timedelta(milliseconds=latency)
                        add_event(
                            i,
                            result_time,
                            "result_success" if success else "result_failed",
                            session_no,
                            feature,
                            "success" if success else "failed",
                            latency,
                        )
                        if success and first_value_time is None:
                            first_value_time = result_time
                            first_feature = feature

        if first_value_time is not None:
            late_activation_penalty = -0.015 if not activated else 0
            p_pay = clipped_probability(
                0.045 + late_activation_penalty + 0.025 * max(quality, -1) + (0.01 if first_feature == "document" else 0)
            )
            if rng.random() < p_pay:
                pay_time = first_value_time + pd.Timedelta(days=float(rng.uniform(0.2, 7)))
                if pay_time <= END_DATE:
                    session_no += 1
                    add_event(i, pay_time - pd.Timedelta(minutes=2), "subscription_view", session_no)
                    add_event(i, pay_time, "payment_success", session_no)
                    plan = str(rng.choice(list(PLANS), p=[0.70, 0.20, 0.10]))
                    subscriptions.append(
                        {
                            "subscription_id": f"sub{len(subscriptions) + 1:07d}",
                            "user_id": users.at[i, "user_id"],
                            "subscription_time": pay_time,
                            "plan": plan,
                            "amount": PLANS[plan],
                            "payment_status": "success",
                            "experiment_group": group,
                        }
                    )

    events_df = pd.DataFrame(events).sort_values(["event_time", "event_id"])
    subscriptions_df = pd.DataFrame(subscriptions)

    users.to_csv(DATA_DIR / "users.csv", index=False)
    assignments.to_csv(DATA_DIR / "ab_assignments.csv", index=False)
    events_df.to_csv(DATA_DIR / "events.csv", index=False)
    subscriptions_df.to_csv(DATA_DIR / "subscriptions.csv", index=False)
    manifest = {name: hashlib.sha256((DATA_DIR / name).read_bytes()).hexdigest()
                for name in ("users.csv", "ab_assignments.csv", "events.csv", "subscriptions.csv")}
    (DATA_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"users={len(users):,}")
    print(f"events={len(events_df):,}")
    print(f"subscriptions={len(subscriptions_df):,}")


if __name__ == "__main__":
    main()
