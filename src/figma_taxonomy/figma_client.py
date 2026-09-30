"""Figma REST API client with file-version caching."""

from __future__ import annotations

import hashlib
import json
import os
import re
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
            "Get a Personal Access Token from Figma > Settings > Access Tokens."
        )
    return token


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
            "and the token owner's access to the file."
        )
    if response.status_code == 404:
        raise RuntimeError("Figma file not found. Check the file key or branch URL and file access.")
    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After", "the indicated reset interval")
        raise RuntimeError(
            f"Figma rate limit reached. Retry after {retry_after} seconds; "
            "limits depend on your seat and the file's plan."
        )
    response.raise_for_status()


def _cache_path(file_key: str, version: str) -> Path:
    key = hashlib.sha256(f"{file_key}:{version}".encode()).hexdigest()[:16]
    return CACHE_DIR / f"{file_key}_{key}.json"


def _read_cache(file_key: str, version: str) -> dict | None:
    path = _cache_path(file_key, version)
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def _write_cache(file_key: str, version: str, data: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(file_key, version)
    with open(path, "w") as f:
        json.dump(data, f)


def fetch_file(url_or_key: str, no_cache: bool = False) -> dict:
    """Fetch a Figma file tree.

    Args:
        url_or_key: Figma file URL or raw file key
        no_cache: If True, skip cache and always fetch from API

    Returns:
        Parsed JSON response from Figma GET /v1/files/:key
    """
    file_key = _parse_file_key(url_or_key)
    token = _get_token()

    headers = {"X-FIGMA-TOKEN": token}

    if not no_cache:
        with httpx.Client() as client:
            meta_resp = client.get(
                f"{FIGMA_API_BASE}/files/{file_key}",
                headers=headers,
                params={"depth": 1},
            )
            _check_response(meta_resp)
            meta = meta_resp.json()
            version = meta.get("version", "")

            cached = _read_cache(file_key, version)
            if cached is not None:
                return cached

    with httpx.Client(timeout=60.0) as client:
        resp = client.get(
            f"{FIGMA_API_BASE}/files/{file_key}",
            headers=headers,
        )
        _check_response(resp)
        data = resp.json()

    version = data.get("version", "unknown")
    if not no_cache:
        _write_cache(file_key, version, data)

    return data


def load_fixture(path: Path) -> dict:
    """Load a Figma API response from a local JSON file."""
    with open(path) as f:
        return json.load(f)
