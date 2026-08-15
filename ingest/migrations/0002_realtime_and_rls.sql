-- 0002: Supabase specifics. Safe to run on plain Postgres too (guards below).
--
-- 1. Row Level Security: the website uses the public "anon" key, so anon must be
--    able to READ but never WRITE. Ingest jobs use the DATABASE_URL (postgres role)
--    and bypass RLS.
-- 2. Realtime: publish observations so the browser can subscribe to new rows.

do $$
begin
    if exists (select 1 from pg_roles where rolname = 'anon') then
        execute 'alter table series enable row level security';
        execute 'alter table observations enable row level security';
        execute 'alter table ingest_runs enable row level security';

        execute 'drop policy if exists series_read on series';
        execute 'create policy series_read on series for select to anon, authenticated using (true)';
        execute 'drop policy if exists observations_read on observations';
        execute 'create policy observations_read on observations for select to anon, authenticated using (true)';
        execute 'drop policy if exists ingest_runs_read on ingest_runs';
        execute 'create policy ingest_runs_read on ingest_runs for select to anon, authenticated using (true)';

        execute 'grant usage on schema public to anon, authenticated';
        execute 'grant select on series, observations, ingest_runs, latest_observations, adapter_health to anon, authenticated';
    end if;

    if exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
        if not exists (
            select 1 from pg_publication_tables
            where pubname = 'supabase_realtime' and tablename = 'observations'
        ) then
            execute 'alter publication supabase_realtime add table observations';
        end if;
    end if;
end $$;
