"""Apply SQL migrations in ingest/migrations in filename order, once each."""

from __future__ import annotations

from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"


def pending(conn, migrations_dir: Path = MIGRATIONS_DIR) -> list[Path]:
    with conn.cursor() as cur:
        cur.execute(
            "create table if not exists schema_migrations "
            "(version text primary key, applied_at timestamptz not null default now())"
        )
        conn.commit()
        cur.execute("select version from schema_migrations")
        done = {r[0] for r in cur.fetchall()}
    files = sorted(p for p in migrations_dir.glob("*.sql"))
    return [p for p in files if p.stem not in done]


def apply(dsn: str, migrations_dir: Path = MIGRATIONS_DIR) -> list[str]:
    import psycopg

    applied: list[str] = []
    with psycopg.connect(dsn, prepare_threshold=None) as conn:
        for path in pending(conn, migrations_dir):
            sql = path.read_text(encoding="utf-8")
            with conn.cursor() as cur:
                cur.execute(sql)
                cur.execute("insert into schema_migrations (version) values (%s)", (path.stem,))
            conn.commit()
            applied.append(path.stem)
    return applied
