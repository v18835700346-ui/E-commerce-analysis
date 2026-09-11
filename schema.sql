-- MySQL 8.0 schema for the simulated AI assistant growth dataset.

create database if not exists ai_product_growth;
use ai_product_growth;

drop table if exists subscriptions;
drop table if exists events;
drop table if exists ab_assignments;
drop table if exists users;

create table users (
    user_id varchar(16) primary key,
    anonymous_id varchar(16) not null unique,
    register_time datetime not null,
    channel varchar(32) not null,
    device varchar(16) not null,
    city_tier varchar(20) not null,
    referrer_user_id varchar(16) null,
    index idx_users_register_time (register_time),
    index idx_users_channel (channel)
);

create table ab_assignments (
    user_id varchar(16) not null,
    experiment_id varchar(64) not null,
    experiment_group char(1) not null,
    assigned_at datetime not null,
    primary key (user_id, experiment_id),
    constraint fk_ab_user foreign key (user_id) references users(user_id)
);

create table events (
    event_id varchar(20) primary key,
    user_id varchar(16) not null,
    anonymous_id varchar(16) not null,
    session_id varchar(24) not null,
    event_time datetime(3) not null,
    event_name varchar(40) not null,
    feature_type varchar(20) null,
    result_status varchar(16) null,
    latency_ms int null,
    experiment_id varchar(64) null,
    experiment_group char(1) null,
    app_version varchar(16) not null,
    index idx_events_user_time (user_id, event_time),
    index idx_events_name_time (event_name, event_time),
    constraint fk_event_user foreign key (user_id) references users(user_id)
);

create table subscriptions (
    subscription_id varchar(20) primary key,
    user_id varchar(16) not null,
    subscription_time datetime(3) not null,
    plan varchar(20) not null,
    amount decimal(10, 2) not null,
    payment_status varchar(16) not null,
    experiment_group char(1) not null,
    index idx_subscriptions_user_time (user_id, subscription_time),
    constraint fk_subscription_user foreign key (user_id) references users(user_id)
);
