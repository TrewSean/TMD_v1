"""Command line entry point: `tmd ...`

tmd run <adapter|group> [--dry-run]     run one adapter or a named group
tmd derive [--dry-run]                  compute derived series from what is stored
tmd migrate                             apply pending SQL migrations
tmd catalog                             print the series catalogue
tmd health                              last run per adapter
"""

from __future__ import annotations

import logging
import sys

import typer

from tmd import catalog
from tmd.config import settings
from tmd.core.store import Store, make_store
from tmd.jobs import migrate as _migrate
from tmd.jobs.runner import GROUPS, run_many
from tmd.sources import REGISTRY

app = typer.Typer(add_completion=False, no_args_is_help=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def _resolve(target: str) -> list[str]:
    if target in GROUPS:
        return GROUPS[target]
    if target in REGISTRY:
        return [target]
    typer.echo(f"unknown adapter or group '{target}'.")
    typer.echo(f"  adapters: {sorted(REGISTRY)}")
    typer.echo(f"  groups:   {sorted(GROUPS)}")
    raise typer.Exit(2)


@app.command()
def run(
    target: str,
    dry_run: bool = typer.Option(False, "--dry-run", help="fetch and print, do not write"),
):
    names = _resolve(target)
    store = make_store(settings.database_url, dry_run=dry_run or settings.dry_run)
    results = run_many(names, store)
    if dry_run or settings.dry_run:
        from tmd.core.store import MemoryStore

        assert isinstance(store, MemoryStore)
        for (sid, ts), o in sorted(store.obs.items(), key=lambda kv: (kv[0][0], kv[0][1]))[-60:]:
            typer.echo(f"{sid:32s} {ts:%Y-%m-%d %H:%M}Z  {o.value}")
    bad = [r for r in results if r.status == "error"]
    for r in results:
        typer.echo(
            f"{r.adapter:14s} {r.status:8s} fetched={r.rows_fetched} "
            f"written={r.rows_written} {r.error or ''}"
        )
        for n in r.notes[:5]:
            typer.echo(f"    note: {n[:200]}")
    if bad and len(bad) == len(results):
        raise typer.Exit(1)  # only fail the job if *everything* failed


@app.command()
def derive(
    dry_run: bool = typer.Option(False, "--dry-run", help="compute and print, do not write"),
):
    """Compute implied policy paths from strips already in the store.

    Reads from the database either way, so DATABASE_URL is required: unlike `run`, this
    command has no external source to fall back on. `--dry-run` reads the real data and
    throws the answer away.
    """
    if not settings.database_url:
        typer.echo("DATABASE_URL not set; derive reads the stored strips")
        raise typer.Exit(2)
    from tmd.core.store import MemoryStore, PostgresStore
    from tmd.jobs.derive import run_all

    source = PostgresStore(settings.database_url)
    sink: Store = MemoryStore() if (dry_run or settings.dry_run) else source
    results = run_all(source, sink)

    if isinstance(sink, MemoryStore):
        for (sid, ts), o in sorted(sink.obs.items(), key=lambda kv: (kv[0][0], kv[0][1])):
            flag = " WEAK" if o.meta.get("weak") == "true" else ""
            typer.echo(
                f"{sid:24s} {ts:%Y-%m-%d}  {o.value:>6}  "
                f"{o.meta.get('meeting_date', ''):10s} "
                f"step={o.meta.get('step_bp', ''):>6}bp "
                f"cum={o.meta.get('change_from_current_bp', ''):>6}bp{flag}"
            )
    for r in results:
        typer.echo(
            f"{r.adapter:12s} {r.status:8s} nodes={r.rows_fetched} "
            f"written={r.rows_written} {r.error or ''}"
        )
        for n in r.notes[:5]:
            typer.echo(f"    note: {n[:200]}")
    if all(r.status == "error" for r in results):
        raise typer.Exit(1)


@app.command()
def migrate():
    if not settings.database_url:
        typer.echo("DATABASE_URL not set")
        raise typer.Exit(2)
    applied = _migrate.apply(settings.database_url)
    typer.echo("applied: " + (", ".join(applied) if applied else "nothing (up to date)"))


@app.command(name="catalog")
def catalog_cmd():
    for s in catalog.load():
        flag = "" if s.active else " (inactive)"
        typer.echo(
            f"{s.id:28s} {s.source:12s} {s.tier:10s} {s.frequency:9s} {s.unit:12s} {s.name}{flag}"
        )


@app.command()
def health():
    if not settings.database_url:
        typer.echo("DATABASE_URL not set")
        raise typer.Exit(2)
    import psycopg

    with psycopg.connect(settings.database_url) as conn, conn.cursor() as cur:
        cur.execute(
            "select adapter, status, finished_at, rows_written, error "
            "from adapter_health order by adapter"
        )
        for a, st, fin, n, err in cur.fetchall():
            typer.echo(f"{a:14s} {st:8s} {fin:%Y-%m-%d %H:%M}Z rows={n} {err or ''}")


def main() -> None:
    try:
        app()
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
