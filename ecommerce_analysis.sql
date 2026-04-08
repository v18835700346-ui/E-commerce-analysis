-- =====================================================
-- 项目名称：电商用户行为与转化分析
-- 工具：SQL（MySQL）
-- 项目目标：
-- 1. 分析用户增长与活跃趋势
-- 2. 评估用户留存与转化表现
-- 3. 分析订单、收入与商品销售情况
-- 4. 识别用户生命周期与高价值用户
-- 5. 评估 AB Test 实验效果
-- =====================================================



-- =====================================================
-- 模块1：用户增长与活跃分析
-- 表：users, user_behavior
-- =====================================================

-- 1. 每日新增用户
select
    register_date,
    count(distinct user_id) as new_users
from users
group by register_date
order by register_date;

-- 2. 累计用户数
with t1 as (
    select
        register_date,
        count(distinct user_id) as new_users
    from users
    group by register_date
)
select
    register_date,
    new_users,
    sum(new_users) over(order by register_date) as cum_users
from t1
order by register_date;

-- 3. 日活跃用户数（DAU）
select
    date(behavior_time) as dt,
    count(distinct user_id) as dau
from user_behavior
group by date(behavior_time)
order by date(behavior_time);

-- =====================================================
-- 模块2：用户留存分析
-- 表：users, user_behavior
-- =====================================================

-- 1. 次日留存
with t1 as (
    select
        u.register_date,
        count(distinct u.user_id) as new_users,
        count(distinct b.user_id) as retained_users
    from users u
    left join user_behavior b
        on u.user_id = b.user_id
       and date(b.behavior_time) = date_add(u.register_date, interval 1 day)
    group by u.register_date
)
select
    register_date,
    new_users,
    retained_users,
    1.0 * retained_users / nullif(new_users, 0) as retention_rate
from t1
order by register_date;

-- 2. 7日留存
with t1 as (
    select
        u.register_date,
        count(distinct u.user_id) as new_users,
        count(distinct b.user_id) as retained_users
    from users u
    left join user_behavior b
        on u.user_id = b.user_id
       and date(b.behavior_time) = date_add(u.register_date, interval 7 day)
    group by u.register_date
)
select
    register_date,
    new_users,
    retained_users,
    1.0 * retained_users / nullif(new_users, 0) as retention_rate
from t1
order by register_date;

-- 3. 留存矩阵（Day1 / Day3 / Day7）
with t1 as (
    select
        u.register_date,
        u.user_id,
        datediff(date(b.behavior_time), u.register_date) as diff_days
    from users u
    left join user_behavior b
        on u.user_id = b.user_id
)
select
    register_date,
    count(distinct user_id) as new_users,
    1.0 * count(distinct case when diff_days = 1 then user_id end)
        / nullif(count(distinct user_id), 0) as day1_retention,
    1.0 * count(distinct case when diff_days = 3 then user_id end)
        / nullif(count(distinct user_id), 0) as day3_retention,
    1.0 * count(distinct case when diff_days = 7 then user_id end)
        / nullif(count(distinct user_id), 0) as day7_retention
from t1
group by register_date
order by register_date;

-- =====================================================
-- 模块3：转化漏斗分析
-- 表：user_behavior
-- =====================================================

-- 1. 每日浏览 / 加购 / 购买用户数
select
    date(behavior_time) as dt,
    count(distinct case when behavior = 'view' then user_id end) as view_users,
    count(distinct case when behavior = 'cart' then user_id end) as cart_users,
    count(distinct case when behavior = 'purchase' then user_id end) as purchase_users
from user_behavior
group by date(behavior_time)
order by date(behavior_time);

-- 2. 整体转化漏斗
select
    behavior,
    count(distinct user_id) as users
from user_behavior
group by behavior
order by case
    when behavior = 'view' then 1
    when behavior = 'cart' then 2
    when behavior = 'purchase' then 3
end;

-- 3. 整体漏斗转化率
with t1 as (
    select
        count(distinct case when behavior = 'view' then user_id end) as view_users,
        count(distinct case when behavior = 'cart' then user_id end) as cart_users,
        count(distinct case when behavior = 'purchase' then user_id end) as purchase_users
    from user_behavior
)
select
    view_users,
    cart_users,
    purchase_users,
    1.0 * cart_users / nullif(view_users, 0) as view_to_cart_rate,
    1.0 * purchase_users / nullif(cart_users, 0) as cart_to_purchase_rate
from t1;

-- 4. 每日漏斗转化率
with t1 as (
    select
        date(behavior_time) as dt,
        count(distinct case when behavior = 'view' then user_id end) as view_users,
        count(distinct case when behavior = 'cart' then user_id end) as cart_users,
        count(distinct case when behavior = 'purchase' then user_id end) as purchase_users
    from user_behavior
    group by date(behavior_time)
)
select
    dt,
    view_users,
    cart_users,
    purchase_users,
    1.0 * cart_users / nullif(view_users, 0) as view_to_cart_rate,
    1.0 * purchase_users / nullif(cart_users, 0) as cart_to_purchase_rate
from t1
order by dt;

-- =====================================================
-- 模块4：订单与收入分析
-- 表：orders
-- =====================================================

-- 1. 每日订单数、下单用户数、GMV
select
    date(order_time) as dt,
    count(distinct order_id) as order_cnt,
    count(distinct user_id) as order_users,
    sum(amount) as gmv
from orders
group by date(order_time)
order by date(order_time);

-- 2. 每日 ARPPU
with t1 as (
    select
        date(order_time) as dt,
        count(distinct user_id) as order_users,
        sum(amount) as gmv
    from orders
    group by date(order_time)
)
select
    dt,
    order_users,
    gmv,
    1.0 * gmv / nullif(order_users, 0) as arppu
from t1
order by dt;

-- 3. 用户平均购买次数
with t1 as (
    select
        user_id,
        count(order_id) as buy_times
    from orders
    group by user_id
)
select
    avg(buy_times) as avg_purchase_times
from t1;

-- 4. 用户复购率
with t1 as (
    select
        user_id,
        count(order_id) as purchase_times
    from orders
    group by user_id
)
select
    count(case when purchase_times >= 1 then user_id end) as total_buy_users,
    count(case when purchase_times >= 2 then user_id end) as repurchase_users,
    1.0 * count(case when purchase_times >= 2 then user_id end)
        / nullif(count(case when purchase_times >= 1 then user_id end), 0) as repurchase_rate
from t1;

-- 5. 首购用户数（日级）
with t1 as (
    select
        user_id,
        min(date(order_time)) as first_order_dt
    from orders
    group by user_id
)
select
    first_order_dt as dt,
    count(user_id) as first_buy_users
from t1
group by first_order_dt
order by first_order_dt;

-- 6. 复购用户数（日级）
with t1 as (
    select
        user_id,
        min(date(order_time)) as first_order_dt
    from orders
    group by user_id
)
select
    date(o.order_time) as dt,
    count(distinct o.user_id) as repurchase_users
from t1
join orders o
    on t1.user_id = o.user_id
where date(o.order_time) > t1.first_order_dt
group by date(o.order_time)
order by date(o.order_time);

-- 7. 每个用户最近一次订单
with t1 as (
    select
        user_id,
        order_id,
        order_time,
        row_number() over(partition by user_id order by order_time desc) as rk
    from orders
)
select
    user_id,
    order_id,
    order_time
from t1
where rk = 1
order by user_id;

-- 8. 每个用户金额最高的一笔订单
with t1 as (
    select
        user_id,
        order_id,
        amount,
        row_number() over(partition by user_id order by amount desc) as rk
    from orders
)
select
    user_id,
    order_id,
    amount
from t1
where rk = 1
order by user_id;

-- =====================================================
-- 模块5：商品销售分析
-- 表：order_items, products
-- =====================================================

-- 1. Top10 热销商品
select
    oi.product_id,
    p.category,
    p.price,
    sum(oi.quantity) as sales_qty
from order_items oi
left join products p
    on oi.product_id = p.product_id
group by oi.product_id, p.category, p.price
order by sales_qty desc
limit 10;

-- 2. 各品类销量与销售额
select
    p.category,
    sum(oi.quantity) as sales_qty,
    sum(oi.quantity * p.price) as sales_amount
from order_items oi
left join products p
    on oi.product_id = p.product_id
group by p.category
order by sales_amount desc;

-- 3. 每个品类销量 Top3 商品
with t1 as (
    select
        oi.product_id,
        p.category,
        sum(oi.quantity) as sales_qty
    from order_items oi
    left join products p
        on oi.product_id = p.product_id
    group by oi.product_id, p.category
),
t2 as (
    select
        category,
        product_id,
        sales_qty,
        row_number() over(partition by category order by sales_qty desc) as rk
    from t1
)
select
    category,
    product_id,
    sales_qty,
    rk
from t2
where rk <= 3
order by category, rk;

-- =====================================================
-- 模块6：用户生命周期分析
-- 表：user_behavior
-- =====================================================

-- 1. 连续活跃用户数
with t1 as (
    select
        user_id,
        date(behavior_time) as dt
    from user_behavior
    group by user_id, date(behavior_time)
),
t2 as (
    select
        user_id,
        dt,
        lag(dt) over(partition by user_id order by dt) as last_dt
    from t1
)
select
    dt,
    count(user_id) as continuous_active_users
from t2
where datediff(dt, last_dt) = 1
group by dt
order by dt;

-- 2. 回流用户数
with t1 as (
    select
        user_id,
        date(behavior_time) as dt
    from user_behavior
    group by user_id, date(behavior_time)
),
t2 as (
    select
        user_id,
        dt,
        lag(dt) over(partition by user_id order by dt) as last_dt
    from t1
)
select
    dt,
    count(user_id) as return_users
from t2
where last_dt is not null
  and datediff(dt, last_dt) > 1
group by dt
order by dt;

-- 3. 沉默用户数
with t1 as (
    select
        user_id,
        date(behavior_time) as dt
    from user_behavior
    group by user_id, date(behavior_time)
),
t2 as (
    select
        user_id,
        dt,
        lead(dt) over(partition by user_id order by dt) as next_dt
    from t1
)
select
    dt,
    count(user_id) as silent_users
from t2
where datediff(next_dt, dt) > 3
   or next_dt is null
group by dt
order by dt;

-- =====================================================
-- 模块7：用户价值分析（RFM）
-- 表：orders
-- =====================================================

-- 1. RFM 模型
select
    user_id,
    datediff('2024-03-31', max(date(order_time))) as r,
    count(order_id) as f,
    sum(amount) as m
from orders
group by user_id;

-- 2. 高价值用户数
with t1 as (
    select
        user_id,
        datediff('2024-03-31', max(date(order_time))) as r,
        count(order_id) as f,
        sum(amount) as m
    from orders
    group by user_id
)
select
    count(user_id) as high_value_users
from t1
where f >= 3
  and m >= 500;

-- 3. 高价值用户明细
with t1 as (
    select
        user_id,
        datediff('2024-03-31', max(date(order_time))) as r,
        count(order_id) as f,
        sum(amount) as m
    from orders
    group by user_id
)
select
    user_id,
    r,
    f,
    m
from t1
where f >= 3
  and m >= 500
order by m desc, f desc;

-- =====================================================
-- 模块8：AB Test 分析
-- 表：ab_test
-- =====================================================

-- 1. 各实验组曝光用户数
select
    experiment_group,
    count(distinct case when is_exposed = 1 then user_id end) as exposed_users
from ab_test
group by experiment_group;

-- 2. CTR（点击率）
with t1 as (
    select
        experiment_group,
        count(distinct case when is_exposed = 1 then user_id end) as exposed_users,
        count(distinct case when is_clicked = 1 then user_id end) as clicked_users
    from ab_test
    group by experiment_group
)
select
    experiment_group,
    exposed_users,
    clicked_users,
    1.0 * clicked_users / nullif(exposed_users, 0) as ctr
from t1;

-- 3. CVR（购买转化率）
with t1 as (
    select
        experiment_group,
        count(distinct case when is_exposed = 1 then user_id end) as exposed_users,
        count(distinct case when is_purchased = 1 then user_id end) as purchased_users
    from ab_test
    group by experiment_group
)
select
    experiment_group,
    exposed_users,
    purchased_users,
    1.0 * purchased_users / nullif(exposed_users, 0) as cvr
from t1;

-- 4. ARPU
with t1 as (
    select
        experiment_group,
        count(distinct case when is_exposed = 1 then user_id end) as exposed_users,
        sum(revenue) as total_revenue
    from ab_test
    group by experiment_group
)
select
    experiment_group,
    exposed_users,
    total_revenue,
    1.0 * total_revenue / nullif(exposed_users, 0) as arpu
from t1;

-- =====================================================
-- 模块9：新老用户分群分析
-- 表：orders, user_behavior
-- =====================================================

-- 1. 新老用户 GMV 贡献分析
with first_order as (
    select
        user_id,
        min(date(order_time)) as first_order_dt
    from orders
    group by user_id
)
select
    date(o.order_time) as dt,
    case
        when date(o.order_time) = f.first_order_dt then 'new_user'
        else 'old_user'
    end as user_type,
    count(distinct o.user_id) as users,
    sum(o.amount) as gmv
from orders o
join first_order f
    on o.user_id = f.user_id
group by date(o.order_time), user_type
order by dt, user_type;

-- 2. 新老用户转化率对比
with first_order as (
    select
        user_id,
        min(date(order_time)) as first_order_dt
    from orders
    group by user_id
),
user_tag as (
    select
        b.user_id,
        date(b.behavior_time) as dt,
        b.behavior,
        case
            when date(b.behavior_time) = f.first_order_dt then 'new_user'
            when date(b.behavior_time) > f.first_order_dt then 'old_user'
            else 'new_user'
        end as user_type
    from user_behavior b
    left join first_order f
        on b.user_id = f.user_id
)
select
    user_type,
    count(distinct case when behavior = 'view' then user_id end) as view_users,
    count(distinct case when behavior = 'cart' then user_id end) as cart_users,
    count(distinct case when behavior = 'purchase' then user_id end) as purchase_users,
    1.0 * count(distinct case when behavior = 'cart' then user_id end)
        / nullif(count(distinct case when behavior = 'view' then user_id end), 0) as view_to_cart_rate,
    1.0 * count(distinct case when behavior = 'purchase' then user_id end)
        / nullif(count(distinct case when behavior = 'cart' then user_id end), 0) as cart_to_purchase_rate
from user_tag
group by user_type;