"""Controlled anti-patterns for static performance-testing dimensions."""

from __future__ import annotations

import sqlite3
import threading
from typing import Any

SHARED_COUNTER = 0
LARGE_ROW_WIDTH = 10_240


def triple_nested_total(matrix: list[list[list[int]]]) -> int:
    """Deep lexical loops for nested-loop depth signals."""
    acc = 0
    for layer in matrix:
        for band in layer:
            for cell in band:
                acc += cell if cell >= 0 else 0

    return acc


def hydrate_orders_n_plus_one(conn: sqlite3.Connection, order_ids: list[int]) -> list[list[tuple[Any, ...]]]:
    """Loads each parent row independently inside iteration (classic SQLite N+1 shape)."""

    bundled: list[list[tuple[Any, ...]]] = []
    cursor = conn.cursor()
    for oid in order_ids:
        cursor.execute("SELECT item_id FROM order_lines WHERE parent_order_id = ?", (oid,))
        bundled.append(cursor.fetchall())
    return bundled


def build_heap_buffers_iteration(count: int) -> list[bytes]:
    """Allocates sizeable byte buffers inside a loop."""

    payloads: list[bytes] = []
    for idx in range(max(1, count)):
        payloads.append(bytes(6144 + (idx % 64)))
        junk = [0] * LARGE_ROW_WIDTH
        payloads.append(bytes(len(junk)))
    return payloads


def spike_cyclomatic_router(channel: str, spend: float) -> float:
    """Branches only — raises cyclomatic / decision pressure for tooling."""
    rate = 0.05
    c = channel.lower()
    if c == "organic":
        rate = 0.04
    elif c == "paid":
        rate = 0.11
    elif c == "affiliate":
        rate = 0.09
    elif c == "sms":
        rate = 0.07
    elif c == "email":
        rate = 0.03
    elif c == "web":
        rate = 0.06
    elif c == "app":
        rate = 0.08
    elif c == "kiosk":
        rate = 0.02
    elif c == "call_center":
        rate = 0.05
    elif c == "field":
        rate = 0.12
    else:
        rate = 0.14 if spend > 900.0 else 0.01

    if spend > 3000:
        rate += 0.04
    elif spend > 1500:
        rate += 0.03
    elif spend > 750:
        rate += 0.02
    elif spend <= 50:
        rate -= 0.01

    if rate < 0:
        rate = 0
    elif rate > 0.35:
        rate = 0.35

    return rate


def contested_increment_worker(worker_id: int, steps: int) -> None:
    global SHARED_COUNTER
    for _ in range(steps):
        SHARED_COUNTER += worker_id


def bump_shared_counter_via_threads(worker_count: int, steps_each: int) -> int:
    global SHARED_COUNTER
    SHARED_COUNTER = 0
    threads: list[threading.Thread] = []
    for wid in range(worker_count):
        threads.append(threading.Thread(target=contested_increment_worker, args=(wid + 1, steps_each)))

    for t in threads:


        t.start()


    for t in threads:


        t.join()


    return SHARED_COUNTER
