"""Figma REST API client with file-version caching."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
import time
import warnings
from pathlib import Path
from urllib.parse import urlparse

import httpx

FIGMA_API_BASE = "https://api.figma.com/v1"
CACHE_DIR = Path(".figma-taxonomy-cache")


def _get_token() -> str:
    token = os.environ.get("FIGMA_TOKEN", "")
    if not token:
        raise RuntimeError(
            "FIGMA_TOKEN environment variable is required. "
            "Supply a personal, REST API plan, or OAuth access token and set FIGMA_TOKEN_TYPE."
        )
    return token


def _auth_headers() -> dict[str, str]:
    kind = os.environ.get("FIGMA_TOKEN_TYPE", "pat").lower()
    if kind not in {"pat", "plan", "oauth"}:
        raise ValueError("FIGMA_TOKEN_TYPE must be pat, plan, or oauth.")
    if kind == "oauth":
        token = os.environ.get("FIGMA_TOKEN")
        if not token:
            from figma_taxonomy.oauth import access_token
            token = access_token()
        return {"Authorization": f"Bearer {token}"}
    token = _get_token()
    return {"X-FIGMA-TOKEN": token}


def _parse_file_key(url_or_key: str) -> str:
    if re.fullmatch(r"[a-zA-Z0-9]+", url_or_key):
        return url_or_key
    parsed = urlparse(url_or_key)
    if parsed.scheme == "https" and parsed.netloc in {"figma.com", "www.figma.com"}:
        match = re.match(
            r"^/(?:file|design)/([a-zA-Z0-9]+)(?:/branch/([a-zA-Z0-9]+))?(?:/|$)",
            parsed.path,
        )
        if match:
            return match.group(2) or match.group(1)
    raise ValueError("Provide a Figma https://www.figma.com/design/... URL or alphanumeric file key.")


def _check_response(response: httpx.Response) -> None:
    if response.status_code in {401, 403}:
        raise RuntimeError(
            "Figma denied access. Check FIGMA_TOKEN expiry, file_content:read scope, "
            "token type, and file access/resource allowlist. For managed OAuth, run 'figma-taxonomy auth login' again."
        )
    if response.status_code == 404:
        raise RuntimeError("Figma file not found. Check the file key or branch URL and file access.")
    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After", "the indicated reset interval")
        raise RuntimeError(
            f"Figma rate limit reached. Retry after {retry_after} seconds; "
            "limits depend on your seat and the file's plan."
        )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"Figma request failed with HTTP {response.status_code}; retry later or check the file key.") from exc


def _cache_path(file_key: str, version: str) -> Path:
    key = hashlib.sha256(f"{file_key}:{version}".encode()).hexdigest()[:16]
    return CACHE_DIR / f"{file_key}_{key}.json"


def _read_cache(file_key: str, version: str) -> dict | None:
    path = _cache_path(file_key, version)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _atomic_json(path: Path, data: dict) -> None:
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temp_path = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False)
        temp_path.replace(path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _write_cache(file_key: str, version: str, data: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _atomic_json(_cache_path(file_key, version), data)
    _atomic_json(_cache_path(file_key, "latest-v2"), {"version": version, "fetched_at": time.time()})


def _cached_file(file_key: str, cache_ttl: float, offline: bool) -> dict | None:
    index = _read_cache(file_key, "latest-v2")
    if not isinstance(index, dict) or not isinstance(index.get("version"), str):
        return None
    stamp = index.get("fetched_at")
    if not isinstance(stamp, (int, float)) or not math.isfinite(stamp):
        return None
    age = time.time() - stamp
    if not offline and not (0 <= age < cache_ttl):
        return None
    data = _read_cache(file_key, index["version"])
    return data if isinstance(data, dict) and isinstance(data.get("document"), dict) else None


def _get_with_retries(client: httpx.Client, url: str, headers: dict) -> httpx.Response:
    """At most three GET attempts and ten total seconds of retry waiting."""
    waited = 0.0
    for attempt in range(3):
        response = None
        try:
            response = client.get(url, headers=headers)
        except httpx.TransportError as exc:
            if attempt == 2:
                raise RuntimeError("Figma connection failed after 3 attempts; check your connection and retry.") from exc
        delay = float(2 ** attempt)
        if response is not None:
            if response.status_code not in {429, 500, 502, 503, 504} or attempt == 2:
                return response
            retry_after = response.headers.get("Retry-After")
            if retry_after is not None:
                try:
                    delay = max(0, int(retry_after))
                except ValueError:
                    # Unknown/reset-date headers must not cause an early retry.
                    return response
        if waited + delay > 10:
            return response
        time.sleep(delay)
        waited += delay
    raise AssertionError("unreachable")


def fetch_file(
    url_or_key: str, no_cache: bool = False, *, cache_ttl: float = 300, offline: bool = False,
) -> dict:
    """Fetch a Figma file tree.

    Args:
        url_or_key: Figma file URL or raw file key
        no_cache: If True, disable cache reads and writes.
        cache_ttl: Maximum cached age in seconds; zero always fetches fresh data.
        offline: Use any valid indexed cache without credentials or requests.

    Returns:
        Parsed JSON response from Figma GET /v1/files/:key
    """
    file_key = _parse_file_key(url_or_key)
    if no_cache and offline:
        raise ValueError("offline and no_cache cannot be combined.")
    if not isinstance(cache_ttl, (int, float)) or not math.isfinite(cache_ttl) or cache_ttl < 0:
        raise ValueError("cache_ttl must be a finite non-negative number of seconds.")
    if not no_cache:
        cached = _cached_file(file_key, cache_ttl, offline)
        if cached is not None:
            return cached
    if offline:
        raise RuntimeError("No valid offline cache for this file; fetch it online first or use a fixture.")
    headers = _auth_headers()

    with httpx.Client(timeout=60.0) as client:
        resp = _get_with_retries(client, f"{FIGMA_API_BASE}/files/{file_key}", headers)
        if resp.status_code == 401 and os.environ.get("FIGMA_TOKEN_TYPE", "pat").lower() == "oauth" and not os.environ.get("FIGMA_TOKEN"):
            from figma_taxonomy.oauth import access_token
            refreshed = access_token(force_refresh=True, rejected_token=headers["Authorization"][7:])
            resp = _get_with_retries(client, f"{FIGMA_API_BASE}/files/{file_key}", {"Authorization": f"Bearer {refreshed}"})
        _check_response(resp)
        try:
            data = resp.json()
        except ValueError as exc:
            raise RuntimeError("Figma returned invalid JSON; retry later.") from exc
    if not isinstance(data, dict) or not isinstance(data.get("document"), dict):
        raise RuntimeError("Figma response has no valid document; no cache was written.")

    version = data.get("version", "unknown")
    if not no_cache:
        try:
            _write_cache(file_key, str(version), data)
        except OSError:
            warnings.warn("Figma response loaded but cache could not be written; check directory permissions.", stacklevel=2)

    return data


def load_fixture(path: Path) -> dict:
    """Load a Figma API response from a local JSON file."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)
