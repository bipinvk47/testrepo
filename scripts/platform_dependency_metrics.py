#!/usr/bin/env python3
"""Emit a single JSON report for platform testing: bundle/install size, build time, deps, imports, cycles."""

from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import subprocess
import sys
import time
import zipfile
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd or REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def _tarjan_circular_sccs(edges: dict[str, set[str]]) -> list[list[str]]:
    """Strongly connected components that denote cycles (size > 1 or a self-edge)."""
    nodes = set(edges) | {v for vs in edges.values() for v in vs}
    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    sccs: list[list[str]] = []

    def strongconnect(v: str) -> None:
        nonlocal index
        indices[v] = index
        lowlink[v] = index
        index += 1
        stack.append(v)
        on_stack.add(v)
        for w in edges.get(v, ()):
            if w not in indices:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in on_stack:
                lowlink[v] = min(lowlink[v], indices[w])
        if lowlink[v] == indices[v]:
            comp: list[str] = []
            while True:
                w = stack.pop()
                on_stack.remove(w)
                comp.append(w)
                if w == v:
                    break
            sccs.append(comp)

    for v in sorted(nodes):
        if v not in indices:
            strongconnect(v)

    circular: list[list[str]] = []
    for comp in sccs:
        if len(comp) > 1:
            circular.append(sorted(comp))
        elif comp and comp[0] in edges.get(comp[0], ()):
            circular.append(comp)
    return circular


def _module_name(path: Path, src_root: Path) -> str:
    rel = path.relative_to(src_root).with_suffix("")
    return ".".join(rel.parts)


def _internal_modules(src_root: Path) -> set[str]:
    mods: set[str] = set()
    for path in src_root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        mods.add(_module_name(path, src_root))
    return mods


def _import_targets_from_node(node: ast.ImportFrom | ast.Import, internal: set[str], current_mod: str) -> set[str]:
    targets: set[str] = set()
    if isinstance(node, ast.Import):
        for alias in node.names:
            name = alias.name or ""
            if not name:
                continue
            if name in internal:
                targets.add(name)
        return targets

    if not isinstance(node, ast.ImportFrom):
        return targets

    if node.level:
        parts = current_mod.split(".")
        if node.level > len(parts):
            return targets
        base_parts = parts[: len(parts) - node.level]
        if node.module:
            base = ".".join(base_parts + node.module.split("."))
        else:
            base = ".".join(base_parts)
        if not node.names:
            return targets
        if base and base in internal:
            targets.add(base)
        for alias in node.names:
            if not alias.name or alias.name == "*":
                continue
            cand = f"{base}.{alias.name}" if base else alias.name
            if cand in internal:
                targets.add(cand)
        return targets

    base = node.module or ""
    if not base:
        return targets

    if base in internal:
        targets.add(base)

    for alias in node.names:
        if not alias.name or alias.name == "*":
            continue
        cand = f"{base}.{alias.name}"
        if cand in internal:
            targets.add(cand)
    return targets


def _internal_import_graph(src_root: Path) -> dict[str, set[str]]:
    internal = _internal_modules(src_root)
    edges: dict[str, set[str]] = defaultdict(set)
    for path in src_root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        mod = _module_name(path, src_root)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for t in _import_targets_from_node(node, internal, mod):
                    if t != mod:
                        edges[mod].add(t)
    return dict(edges)


def _count_internal_cycles(edges: dict[str, set[str]], internal: set[str]) -> int:
    sub: dict[str, set[str]] = {m: {t for t in ts if t in internal} for m, ts in edges.items() if m in internal}
    return len(_tarjan_circular_sccs(sub))


def _count_unused_imports_ruff(root: Path) -> int:
    exe = shutil.which("ruff")
    if not exe:
        return -1
    proc = _run([exe, "check", str(root), "--select", "F401", "--output-format", "json"], cwd=root)
    if proc.returncode not in (0, 1):
        return -1
    try:
        data = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return -1
    return len(data) if isinstance(data, list) else 0


def _deptry_unused_dependency_count(root: Path) -> int:
    exe = shutil.which("deptry")
    if not exe:
        return -1
    proc = _run([exe, str(root)], cwd=root)
    text = (proc.stdout or "") + (proc.stderr or "")
    plain = re.sub(r"\x1b\[[0-9;]*m", "", text)
    return len(re.findall(r"\bDEP002\b", plain))


def _wheel_bundle_bytes(root: Path) -> tuple[int, str]:
    dist = root / "dist"
    if dist.exists():
        shutil.rmtree(dist)
    proc = _run([sys.executable, "-m", "build", "--wheel"], cwd=root)
    if proc.returncode != 0:
        return (0, (proc.stderr or proc.stdout or "build failed")[:500])
    wheels = list(dist.glob("*.whl"))
    if not wheels:
        return (0, "no wheel produced")
    w = max(wheels, key=lambda p: p.stat().st_mtime)
    return (w.stat().st_size, str(w.relative_to(root)))


def _zip_uncompressed_size(wheel_path: Path) -> int:
    total = 0
    with zipfile.ZipFile(wheel_path, "r") as zf:
        for z in zf.infolist():
            total += z.file_size
    return total


def main() -> int:
    ap = argparse.ArgumentParser(description="Platform dependency / performance metrics (Python).")
    ap.add_argument("--root", type=Path, default=REPO_ROOT, help="Repository root (default: auto)")
    ap.add_argument("--out", type=Path, default=None, help="Write JSON path (default: metrics/platform_dependency_report.json)")
    args = ap.parse_args()
    root: Path = args.root.resolve()
    out_path = args.out or (root / "metrics" / "platform_dependency_report.json")
    src = root / "src"

    categories = {
        "performance_testing": {
            "dependency_analysis": {
                "bundle_size_analysis": True,
                "unused_dependency_detection": True,
                "unused_import_count": True,
                "build_performance": True,
                "dependency_graph_analysis": True,
            }
        }
    }

    build_start = time.perf_counter()
    wheel_bytes, wheel_rel = _wheel_bundle_bytes(root)
    build_seconds = round(time.perf_counter() - build_start, 3)
    uncompressed = 0
    if wheel_bytes and wheel_rel and not wheel_rel.startswith("build failed") and (root / wheel_rel).is_file():
        uncompressed = _zip_uncompressed_size(root / wheel_rel)

    internal: set[str] = set()
    edges: dict[str, set[str]] = {}
    cycle_count = 0
    if src.is_dir():
        internal = _internal_modules(src)
        edges = _internal_import_graph(src)
        cycle_count = _count_internal_cycles(edges, internal)

    unused_imp = _count_unused_imports_ruff(root)
    unused_dep = _deptry_unused_dependency_count(root)

    report = {
        "schema": "platform_dependency_metrics/v1",
        "language": "python",
        "repo_root": str(root),
        "metrics": {
            "bundle_size_analysis": {
                "bundle_size_bytes": wheel_bytes,
                "wheel_uncompressed_bytes": uncompressed,
                "wheel_artifact": wheel_rel if wheel_bytes else None,
            },
            "unused_dependency_detection": {
                "unused_dependency_count": unused_dep,
            },
            "unused_import_count": {
                "unused_import_count": unused_imp,
            },
            "build_performance": {
                "build_duration_seconds": build_seconds,
                "build_kind": "pep517_wheel",
            },
            "dependency_graph_analysis": {
                "circular_dependency_count": cycle_count,
                "internal_module_edge_count": sum(len(v) for v in edges.values()),
            },
        },
        "categories": categories,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
