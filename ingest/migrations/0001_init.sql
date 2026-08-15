-- 0001_init: core tables. Applied by `tmd migrate` (see tmd/jobs/migrate.py).
-- Rules: migrations are append-only. Never edit an applied migration; add a new file.

create table if not exists schema_migrations (
    version     text primary key,
    applied_at  timestamptz not null default now()
);

-- What numbers exist. Mirrors catalog/series.yaml; the loader upserts it on every run.
create table if not exists series (
    id           text primary key,
    name         text not null,
    unit         text not null,
    asset_class  text not null,
    country      char(2) not null,
    frequency    text not null,
    tier         text not null,
    source       text not null,
    source_ref   text not null default '',
    description  text not null default '',
    active       boolean not null default true,
    tags         text[] not null default '{}',
    created_at   timestamptz not null default now(),
    updated_at   timestamptz not null default now()
);

-- Every value we have ever pulled. Append-only in spirit; upsert on (series_id, ts)
-- so a re-run of the same day corrects rather than duplicates.
create table if not exists observations (
    series_id   text not null references series(id),
    ts          timestamptz not null,   -- the time the value is FOR
    value       numeric not null,
    as_of       timestamptz not null,   -- when we fetched it
    source_ref  text,
    meta        jsonb,
    primary key (series_id, ts)
);
create index if not exists observations_ts_idx on observations (ts desc);
create index if not exists observations_series_asof_idx on observations (series_id, as_of desc);

-- One row per adapter run. This is the monitoring table: the site can show
-- "last successful update" per source from here.
create table if not exists ingest_runs (
    id            bigint generated always as identity primary key,
    adapter       text not null,
    started_at    timestamptz not null,
    finished_at   timestamptz not null,
    status        text not null check (status in ('ok','partial','error')),
    rows_fetched  integer not null default 0,
    rows_written  integer not null default 0,
    error         text,
    notes         text[] not null default '{}'
);
create index if not exists ingest_runs_adapter_idx on ingest_runs (adapter, finished_at desc);

-- Convenience view: latest value per series, joined to its metadata.
-- The website reads this for every tile.
create or replace view latest_observations as
select distinct on (o.series_id)
    o.series_id, s.name, s.unit, s.asset_class, s.country, s.frequency, s.tier, s.source, s.tags,
    o.ts, o.value, o.as_of
from observations o
join series s on s.id = o.series_id
where s.active
order by o.series_id, o.ts desc;

-- Convenience view: health per adapter.
create or replace view adapter_health as
select distinct on (adapter)
    adapter, status, finished_at, rows_written, error
from ingest_runs
order by adapter, finished_at desc;
