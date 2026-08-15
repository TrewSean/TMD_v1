"""Storage. Two implementations of one interface:

  * PostgresStore : the real thing (Supabase). Upserts, never overwrites history.
  * MemoryStore   : for tests and --dry-run. No I/O.

Adapters and calcs never import psycopg. They only see `Store`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import datetime

from tmd.core.models import IngestResult, Observation, Series


class Store(ABC):
    @abstractmethod
    def upsert_series(self, series: Iterable[Series]) -> int: ...

    @abstractmethod
    def upsert_observations(self, obs: Iterable[Observation]) -> int: ...

    @abstractmethod
    def record_run(self, result: IngestResult) -> None: ...

    @abstractmethod
    def latest(self, series_id: str) -> Observation | None: ...

    @abstractmethod
    def history(self, series_id: str, since: datetime | None = None) -> list[Observation]: ...


class MemoryStore(Store):
    def __init__(self) -> None:
        self.series: dict[str, Series] = {}
        self.obs: dict[tuple[str, datetime], Observation] = {}
        self.runs: list[IngestResult] = []

    def upsert_series(self, series: Iterable[Series]) -> int:
        n = 0
        for s in series:
            self.series[s.id] = s
            n += 1
        return n

    def upsert_observations(self, obs: Iterable[Observation]) -> int:
        n = 0
        for o in obs:
            self.obs[(o.series_id, o.ts)] = o
            n += 1
        return n

    def record_run(self, result: IngestResult) -> None:
        self.runs.append(result)

    def latest(self, series_id: str) -> Observation | None:
        rows = [o for (sid, _), o in self.obs.items() if sid == series_id]
        return max(rows, key=lambda o: o.ts) if rows else None

    def history(self, series_id: str, since: datetime | None = None) -> list[Observation]:
        rows = [o for (sid, _), o in self.obs.items() if sid == series_id]
        if since:
            rows = [o for o in rows if o.ts >= since]
        return sorted(rows, key=lambda o: o.ts)


class PostgresStore(Store):
    """Thin psycopg3 implementation. Schema lives in ingest/migrations/*.sql."""

    def __init__(self, dsn: str):
        import psycopg  # imported lazily so tests never need it

        self._psycopg = psycopg
        self.dsn = dsn

    def _conn(self):
        # prepare_threshold=None: works through Supabase's transaction pooler (pgbouncer
        # mode), which does not support server-side prepared statements.
        return self._psycopg.connect(self.dsn, autocommit=False, prepare_threshold=None)

    def upsert_series(self, series: Iterable[Series]) -> int:
        rows = [
            (
                s.id,
                s.name,
                s.unit,
                s.asset_class.value,
                s.country,
                s.frequency.value,
                s.tier.value,
                s.source,
                s.source_ref,
                s.description,
                s.active,
                s.tags,
            )
            for s in series
        ]
        if not rows:
            return 0
        sql = """
            insert into series (id, name, unit, asset_class, country, frequency, tier,
                                source, source_ref, description, active, tags)
            values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            on conflict (id) do update set
                name = excluded.name, unit = excluded.unit, asset_class = excluded.asset_class,
                country = excluded.country, frequency = excluded.frequency, tier = excluded.tier,
                source = excluded.source, source_ref = excluded.source_ref,
                description = excluded.description, active = excluded.active, tags = excluded.tags,
                updated_at = now()
        """
        with self._conn() as conn, conn.cursor() as cur:
            cur.executemany(sql, rows)
            conn.commit()
        return len(rows)

    def upsert_observations(self, obs: Iterable[Observation]) -> int:
        rows = [(o.series_id, o.ts, o.value, o.as_of, o.source_ref, o.meta or None) for o in obs]
        if not rows:
            return 0
        sql = """
            insert into observations (series_id, ts, value, as_of, source_ref, meta)
            values (%s,%s,%s,%s,%s,%s)
            on conflict (series_id, ts) do update set
                value = excluded.value, as_of = excluded.as_of,
                source_ref = excluded.source_ref, meta = excluded.meta
        """
        from psycopg.types.json import Jsonb

        rows = [(a, b, c, d, e, Jsonb(f) if f else None) for (a, b, c, d, e, f) in rows]
        with self._conn() as conn, conn.cursor() as cur:
            cur.executemany(sql, rows)
            conn.commit()
        return len(rows)

    def record_run(self, result: IngestResult) -> None:
        sql = """
            insert into ingest_runs (adapter, started_at, finished_at, status,
                                     rows_fetched, rows_written, error, notes)
            values (%s,%s,%s,%s,%s,%s,%s,%s)
        """
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    result.adapter,
                    result.started_at,
                    result.finished_at,
                    result.status,
                    result.rows_fetched,
                    result.rows_written,
                    result.error,
                    result.notes,
                ),
            )
            conn.commit()

    def latest(self, series_id: str) -> Observation | None:
        sql = """select series_id, ts, value, as_of, coalesce(source_ref,''), coalesce(meta,'{}')
                 from observations where series_id = %s order by ts desc limit 1"""
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, (series_id,))
            r = cur.fetchone()
        if not r:
            return None
        return Observation(
            series_id=r[0], ts=r[1], value=r[2], as_of=r[3], source_ref=r[4], meta=r[5]
        )

    def history(self, series_id: str, since: datetime | None = None) -> list[Observation]:
        sql = """select series_id, ts, value, as_of, coalesce(source_ref,''), coalesce(meta,'{}')
                 from observations where series_id = %s and (%s::timestamptz is null or ts >= %s)
                 order by ts"""
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, (series_id, since, since))
            rows = cur.fetchall()
        return [
            Observation(series_id=r[0], ts=r[1], value=r[2], as_of=r[3], source_ref=r[4], meta=r[5])
            for r in rows
        ]


def make_store(dsn: str | None, dry_run: bool = False) -> Store:
    if dry_run or not dsn:
        return MemoryStore()
    return PostgresStore(dsn)
