"""Yahoo Finance via the yfinance library. Tier: aggregator (delayed, unofficial).

Used for indices, FX, commodity and rates futures, and CBOE yield indices where no
free primary feed exists. Expect 10 to 20 minute delays and occasional breakage when
Yahoo changes things; that is why every series here is tier=aggregator and why the
site shows the as_of timestamp on every tile.

Two modes:
  * intraday snapshot (default): one Observation per ticker, ts = last quote time.
  * daily history (`fetch(since=...)` with since older than 2 days): daily closes,
    ts = that day's session close, so we can backfill history.

source_ref on the catalogue = the Yahoo ticker.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from tmd.core.adapter import AdapterError, SourceAdapter
from tmd.core.models import Observation

log = logging.getLogger(__name__)


def observations_from_frame(closes, ref_to_id: dict[str, str]) -> list[Observation]:
    """`closes` is a pandas DataFrame indexed by timestamp with one column per ticker."""
    fetched = datetime.now(UTC)
    out: list[Observation] = []
    for ticker, sid in ref_to_id.items():
        if ticker not in closes.columns:
            continue
        col = closes[ticker].dropna()
        for ts, val in col.items():
            ts_py = ts.to_pydatetime()
            if ts_py.tzinfo is None:
                ts_py = ts_py.replace(tzinfo=UTC)
            out.append(
                Observation(
                    series_id=sid,
                    ts=ts_py,
                    value=Decimal(str(float(val))),
                    as_of=fetched,
                    source_ref=ticker,
                )
            )
    return out


class YFinanceQuotes(SourceAdapter):
    name = "yfinance"

    def fetch(self, since: datetime | None = None) -> list[Observation]:
        import yfinance as yf  # lazy: heavy import, and tests never need it

        ref_to_id = {s.source_ref: s.id for s in self.series}
        tickers = list(ref_to_id)
        now = datetime.now(UTC)
        history_mode = since is not None and (now - since) > timedelta(days=2)

        if history_mode:
            df = yf.download(
                tickers,
                start=since.date().isoformat(),
                interval="1d",
                progress=False,
                auto_adjust=False,
                group_by="column",
                threads=True,
            )
            if df is None or df.empty:
                raise AdapterError("yfinance returned an empty frame")
            closes = df["Close"] if "Close" in df else df
            return observations_from_frame(closes, ref_to_id)

        # Snapshot mode: last price + its timestamp per ticker.
        out: list[Observation] = []
        fetched = now
        failures: list[str] = []
        for t in tickers:
            try:
                fi = yf.Ticker(t).fast_info
                price = (
                    fi.get("last_price") if hasattr(fi, "get") else getattr(fi, "last_price", None)
                )
                if price is None:
                    failures.append(t)
                    continue
                # fast_info has no reliable quote timestamp; use 1m history's last bar if present.
                hist = yf.Ticker(t).history(period="1d", interval="1m")
                if hist is not None and not hist.empty:
                    ts = hist.index[-1].to_pydatetime()
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=UTC)
                    price = float(hist["Close"].iloc[-1])
                else:
                    ts = fetched
                out.append(
                    Observation(
                        series_id=ref_to_id[t],
                        ts=ts,
                        value=Decimal(str(float(price))),
                        as_of=fetched,
                        source_ref=t,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("yfinance %s failed: %s", t, exc)
                failures.append(t)
        if not out:
            raise AdapterError(f"yfinance: every ticker failed ({failures})")
        return out
