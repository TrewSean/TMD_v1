"""Alpaca websocket -> Postgres, as an always-on process.

What it does
------------
* Loads the `alpaca` series from the shared catalogue (same list the REST adapter uses).
* Opens Alpaca's stock data stream (feed from ALPACA_FEED, default iex) and subscribes to
  1-minute bars for every symbol.
* Each bar becomes an Observation via tmd.sources.alpaca.bar_to_observation and is
  upserted in small batches (BATCH_MAX rows or BATCH_SECONDS, whichever first).
* Every HEARTBEAT_SECONDS it writes an ingest_runs row (adapter="alpaca_stream") with the
  rows written since the last heartbeat, so the site can show "stream alive".
* Reconnects with backoff on any error. Off market hours the socket is quiet; that's fine.

No AI, no arithmetic. Config via environment: DATABASE_URL, ALPACA_API_KEY,
ALPACA_API_SECRET, ALPACA_FEED (iex|delayed_sip|sip), TMD_WORKER_HEARTBEAT (s).
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from datetime import UTC, datetime

from tmd import catalog
from tmd.config import settings
from tmd.core.models import IngestResult, Observation
from tmd.core.store import Store, make_store
from tmd.core.validate import validate_observations
from tmd.sources.alpaca import bar_to_observation

log = logging.getLogger("tmd.worker")
ADAPTER = "alpaca_stream"
BATCH_MAX = 50
BATCH_SECONDS = 5.0
HEARTBEAT_SECONDS = float(os.environ.get("TMD_WORKER_HEARTBEAT", "300"))
RECONNECT_MIN, RECONNECT_MAX = 2.0, 120.0


class Batcher:
    """Collects observations and flushes to the store; also counts for the heartbeat."""

    def __init__(self, store: Store, series_by_id: dict):
        self.store = store
        self.series_by_id = series_by_id
        self.buf: list[Observation] = []
        self.written_since_hb = 0
        self.rejected_since_hb: list[str] = []
        self.last_flush = datetime.now(UTC)

    def add(self, obs: Observation) -> None:
        self.buf.append(obs)

    def due(self) -> bool:
        age = (datetime.now(UTC) - self.last_flush).total_seconds()
        return len(self.buf) >= BATCH_MAX or (self.buf and age >= BATCH_SECONDS)

    def flush(self) -> int:
        if not self.buf:
            return 0
        good, problems = validate_observations(self.buf, self.series_by_id)
        self.buf.clear()
        self.rejected_since_hb.extend(problems)
        n = self.store.upsert_observations(good) if good else 0
        self.written_since_hb += n
        self.last_flush = datetime.now(UTC)
        return n

    def heartbeat(self, status: str = "ok", error: str | None = None) -> None:
        now = datetime.now(UTC)
        self.store.record_run(
            IngestResult(
                adapter=ADAPTER,
                started_at=now,
                finished_at=now,
                status=status if not error else "error",
                rows_fetched=self.written_since_hb + len(self.rejected_since_hb),
                rows_written=self.written_since_hb,
                error=error,
                notes=self.rejected_since_hb[:20],
            )
        )
        self.written_since_hb = 0
        self.rejected_since_hb = []


async def run_stream(store: Store, stop: asyncio.Event) -> None:
    from alpaca.data.enums import DataFeed
    from alpaca.data.live import StockDataStream

    series = catalog.by_source().get("alpaca", [])
    if not series:
        raise RuntimeError("no active 'alpaca' series in catalogue")
    store.upsert_series(series)
    ref_to_id = {s.source_ref: s.id for s in series}
    by_id = {s.id: s for s in series}
    batcher = Batcher(store, by_id)
    feed = DataFeed(settings.alpaca_feed.lower())

    async def on_bar(bar) -> None:
        sid = ref_to_id.get(bar.symbol)
        if sid is None:
            return
        batcher.add(bar_to_observation(bar, sid, bar.symbol))
        if batcher.due():
            await asyncio.to_thread(batcher.flush)

    async def housekeeping() -> None:
        last_hb = datetime.now(UTC)
        while not stop.is_set():
            await asyncio.sleep(1.0)
            if batcher.due():
                await asyncio.to_thread(batcher.flush)
            if (datetime.now(UTC) - last_hb).total_seconds() >= HEARTBEAT_SECONDS:
                await asyncio.to_thread(batcher.heartbeat)
                last_hb = datetime.now(UTC)
                log.info("heartbeat written")

    backoff = RECONNECT_MIN
    hk = asyncio.create_task(housekeeping())
    try:
        while not stop.is_set():
            stream = StockDataStream(settings.alpaca_key, settings.alpaca_secret, feed=feed)
            stream.subscribe_bars(on_bar, *ref_to_id.keys())
            log.info("connecting to Alpaca %s feed for %d symbols", feed.value, len(ref_to_id))
            try:
                # _run_forever is the coroutine behind stream.run(); run() would block the loop
                await stream._run_forever()  # noqa: SLF001
                backoff = RECONNECT_MIN
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                log.warning("stream error: %s; reconnecting in %.0fs", exc, backoff)
                await asyncio.to_thread(batcher.heartbeat, "error", f"{type(exc).__name__}: {exc}")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, RECONNECT_MAX)
            finally:
                try:
                    await stream.close()
                except Exception:  # noqa: BLE001
                    pass
    finally:
        hk.cancel()
        await asyncio.to_thread(batcher.flush)
        await asyncio.to_thread(batcher.heartbeat)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    if not settings.alpaca_key or not settings.alpaca_secret:
        raise SystemExit("ALPACA_API_KEY / ALPACA_API_SECRET not set")
    if not settings.database_url:
        raise SystemExit("DATABASE_URL not set")
    store = make_store(settings.database_url)
    stop = asyncio.Event()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:  # Windows
            pass
    try:
        loop.run_until_complete(run_stream(store, stop))
    finally:
        loop.close()


if __name__ == "__main__":
    main()
