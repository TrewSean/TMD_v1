"""Shared HTTP client with retries and a polite user agent."""

from __future__ import annotations

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from tmd.config import settings

_RETRYABLE = (httpx.TransportError, httpx.HTTPStatusError)


def client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": settings.http_user_agent, "Accept": "*/*"},
        timeout=settings.http_timeout_s,
        follow_redirects=True,
    )


@retry(
    reraise=True,
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=1, max=20),
    retry=retry_if_exception_type(_RETRYABLE),
)
def get_text(url: str, **params: str) -> str:
    with client() as c:
        r = c.get(url, params=params or None)
        r.raise_for_status()
        return r.text


@retry(
    reraise=True,
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=1, max=20),
    retry=retry_if_exception_type(_RETRYABLE),
)
def get_json(url: str, **params: str) -> object:
    with client() as c:
        r = c.get(url, params=params or None)
        r.raise_for_status()
        return r.json()
