-- AI product growth analysis (MySQL 8.0)
use ai_product_growth;
set @analysis_end = timestamp('2026-03-31 23:59:59');

-- 1. North-star metric: weekly users completing at least two successful tasks.
with weekly_success as (
    select
        date_sub(date(event_time), interval weekday(event_time) day) as week_start,
        user_id,
        count(*) as successful_tasks
    from events
    where event_name = 'result_success'
    group by week_start, user_id
)
select
    week_start,
    count(*) as weekly_effective_task_users
from weekly_success
where successful_tasks >= 2
group by week_start
order by week_start;

-- 2. Strict guided-path funnel. The product-wide activation rate is calculated separately.
with registered as (
    select user_id, register_time
    from users
    where register_time <= @analysis_end - interval 1 day
),
onboarded as (
    select r.user_id, r.register_time, min(e.event_time) as onboarding_time
    from registered r
    left join events e
        on r.user_id = e.user_id
       and e.event_name = 'onboarding_complete'
       and e.event_time between r.register_time and r.register_time + interval 1 day
    group by r.user_id, r.register_time
),
submitted as (
    select o.user_id, o.register_time, o.onboarding_time, min(e.event_time) as submit_time
    from onboarded o
    left join events e
        on o.user_id = e.user_id
       and e.event_name = 'task_submit'
       and o.onboarding_time is not null
       and e.event_time between o.onboarding_time and o.register_time + interval 1 day
    group by o.user_id, o.register_time, o.onboarding_time
),
activated as (
    select s.user_id, s.onboarding_time, s.submit_time, min(e.event_time) as success_time
    from submitted s
    left join events e
        on s.user_id = e.user_id
       and e.event_name = 'result_success'
       and e.event_time between s.submit_time and s.register_time + interval 1 day
    group by s.user_id, s.onboarding_time, s.submit_time
)
select
    count(*) as registered_users,
    count(onboarding_time) as onboarding_completed_users,
    count(submit_time) as task_submitted_users,
    count(success_time) as activated_users,
    count(onboarding_time) / count(*) as onboarding_rate,
    count(submit_time) / count(*) as task_submit_rate,
    count(success_time) / count(*) as guided_path_success_rate
from activated;

-- 3. Acquisition quality by channel: volume, activation, D7 retained use and payment.
with eligible as (
    select user_id, channel, register_time
    from users
    where register_time <= @analysis_end - interval 7 day
),
user_metrics as (
    select
        u.user_id,
        u.channel,
        max(e.event_name = 'result_success'
            and e.event_time <= u.register_time + interval 1 day) as activated_24h,
        max(e.event_name = 'result_success'
            and date(e.event_time) = date(u.register_time) + interval 7 day) as retained_d7
    from eligible u
    left join events e on u.user_id = e.user_id
    group by u.user_id, u.channel
),
paid as (
    select
        u.user_id,
        max(s.subscription_time <= u.register_time + interval 7 day) as paid_7d
    from eligible u
    left join subscriptions s on u.user_id = s.user_id
    group by u.user_id
)
select
    m.channel,
    count(*) as registered_users,
    avg(m.activated_24h) as activation_rate_24h,
    avg(m.retained_d7) as retention_rate_d7,
    avg(p.paid_7d) as payment_rate_7d
from user_metrics m
join paid p on m.user_id = p.user_id
group by m.channel
order by registered_users desc;

-- 4. Registration cohort retention. Incomplete observation windows are excluded.
with cohorts as (
    select user_id, date(register_time) as cohort_date
    from users
),
active_days as (
    select distinct user_id, date(event_time) as active_date
    from events
    where event_name = 'result_success'
)
select
    c.cohort_date,
    count(distinct c.user_id) as cohort_users,
    case when c.cohort_date <= date(@analysis_end) - interval 1 day
         then count(distinct case when a.active_date = c.cohort_date + interval 1 day then c.user_id end)
              / count(distinct c.user_id) end as d1_retention,
    case when c.cohort_date <= date(@analysis_end) - interval 3 day
         then count(distinct case when a.active_date = c.cohort_date + interval 3 day then c.user_id end)
              / count(distinct c.user_id) end as d3_retention,
    case when c.cohort_date <= date(@analysis_end) - interval 7 day
         then count(distinct case when a.active_date = c.cohort_date + interval 7 day then c.user_id end)
              / count(distinct c.user_id) end as d7_retention
from cohorts c
left join active_days a on c.user_id = a.user_id
group by c.cohort_date
order by c.cohort_date;

-- 5. First successful feature and its relationship with activation speed and D7 retention.
with ranked_success as (
    select
        user_id,
        feature_type,
        event_time,
        row_number() over(partition by user_id order by event_time, event_id) as rn
    from events
    where event_name = 'result_success'
),
first_success as (
    select user_id, feature_type, event_time
    from ranked_success
    where rn = 1
),
active_d7 as (
    select distinct u.user_id
    from users u
    join events e
      on u.user_id = e.user_id
     and e.event_name = 'result_success'
     and date(e.event_time) = date(u.register_time) + interval 7 day
)
select
    f.feature_type as first_feature,
    count(*) as users,
    avg(timestampdiff(second, u.register_time, f.event_time) / 60.0) as avg_first_value_minutes,
    avg(a.user_id is not null) as d7_retention_rate
from first_success f
join users u on f.user_id = u.user_id
left join active_d7 a on f.user_id = a.user_id
where u.register_time <= @analysis_end - interval 7 day
group by f.feature_type
order by users desc;

-- 6. Mutually exclusive lifecycle segments as of the analysis date.
with success_profile as (
    select
        u.user_id,
        min(e.event_time) as first_success_time,
        max(e.event_time) as last_success_time,
        sum(e.event_time >= @analysis_end - interval 30 day) as successful_tasks_30d
    from users u
    left join events e
      on u.user_id = e.user_id
     and e.event_name = 'result_success'
    group by u.user_id
)
select
    case
        when first_success_time is null then 'never_activated'
        when first_success_time >= @analysis_end - interval 7 day then 'newly_activated'
        when last_success_time >= @analysis_end - interval 7 day then 'active'
        when last_success_time >= @analysis_end - interval 14 day then 'at_risk'
        else 'dormant'
    end as lifecycle_segment,
    count(*) as users,
    avg(successful_tasks_30d) as avg_successful_tasks_30d
from success_profile
group by lifecycle_segment
order by users desc;

-- 7. RFE scores: recency, frequency and feature breadth over the last 30 days.
with user_rfe as (
    select
        u.user_id,
        datediff(date(@analysis_end), date(max(e.event_time))) as recency_days,
        count(e.event_id) as frequency_30d,
        count(distinct e.feature_type) as feature_breadth_30d
    from users u
    join events e
      on u.user_id = e.user_id
     and e.event_name = 'result_success'
     and e.event_time >= @analysis_end - interval 30 day
    group by u.user_id
),
scored as (
    select
        *,
        ntile(4) over(order by recency_days desc) as r_score,
        ntile(4) over(order by frequency_30d) as f_score,
        ntile(4) over(order by feature_breadth_30d) as e_score
    from user_rfe
)
select
    case
        when r_score >= 3 and f_score >= 3 and e_score >= 3 then 'core_user'
        when r_score >= 3 and f_score >= 2 then 'growing_user'
        when r_score <= 2 and f_score >= 3 then 'churn_risk_high_value'
        else 'regular_user'
    end as value_segment,
    count(*) as users,
    avg(recency_days) as avg_recency_days,
    avg(frequency_30d) as avg_frequency_30d,
    avg(feature_breadth_30d) as avg_feature_breadth_30d
from scored
group by value_segment
order by users desc;

-- 8. Experiment metric table. Statistical tests are implemented in ab_analysis.py.
with experiment_users as (
    select u.user_id, u.register_time, a.experiment_group
    from users u
    join ab_assignments a on u.user_id = a.user_id
    where a.experiment_id = 'onboarding_interest_v1'
      and u.register_time <= @analysis_end - interval 7 day
),
metrics as (
    select
        u.user_id,
        u.experiment_group,
        max(e.event_name = 'result_success'
            and e.event_time <= u.register_time + interval 1 day) as activated_24h,
        max(e.event_name = 'result_success'
            and date(e.event_time) = date(u.register_time) + interval 7 day) as retained_d7,
        max(e.event_name = 'result_failed'
            and e.event_time <= u.register_time + interval 1 day) as failed_24h
    from experiment_users u
    left join events e on u.user_id = e.user_id
    group by u.user_id, u.experiment_group
)
select
    experiment_group,
    count(*) as users,
    avg(activated_24h) as activation_rate_24h,
    avg(retained_d7) as retention_rate_d7,
    avg(failed_24h) as failure_rate_24h
from metrics
group by experiment_group;
