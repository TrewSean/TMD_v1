# ingest (`tmd`)

Python package that pulls market data, validates it, and writes it to Postgres.

- `src/tmd/catalog/series.yaml`  what numbers exist (the catalogue)
- `src/tmd/core/`                 models, adapter interface, store, validation, http
- `src/tmd/sources/`              one adapter per data source
- `src/tmd/calcs/`                pure calculations
- `src/tmd/jobs/`                 runner, CLI, migrations runner
- `migrations/`                   SQL, append-only
- `tests/`                        unit tests with recorded fixtures (no network)

See root `CLAUDE.md` for the rules and `PLAN.md` for tasks.
