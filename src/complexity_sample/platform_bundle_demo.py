"""Small surface for platform demos: one unused import, one used dependency."""

import json  # intentionally unused for static import-count tests
import sys

import requests


def http_ok(url: str, timeout_s: float = 3.0) -> bool:
    try:
        r = requests.get(url, timeout=timeout_s)
        return r.status_code < 600
    except OSError:
        return False


def python_runtime() -> str:
    return sys.version.split()[0]
