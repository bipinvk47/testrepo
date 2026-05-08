#!/usr/bin/env python3
"""Compute white-box metric snapshots for src/complexity_sample (no third-party deps)."""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path


def _git_branch(root: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return "unknown"


class _CyclomaticVisitor(ast.NodeVisitor):
    """Radon-style cyclomatic complexity (+1 per decision path)."""

    def __init__(self) -> None:
        self.complexity = 1

    def visit_If(self, node: ast.If) -> None:
        # Each `if` / `elif` is a separate If node in the AST chain.
        self.complexity += 1
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> None:
        self.complexity += len(node.handlers)
        self.generic_visit(node)

    def visit_Match(self, node: ast.Match) -> None:
        self.complexity += len(node.cases)
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        self.complexity += len(node.values) - 1
        self.generic_visit(node)

    def visit_Comprehension(self, node: ast.comprehension) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        self.complexity += len(node.items)
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> None:
        self.complexity += 1
        self.generic_visit(node)


class _NestingVisitor(ast.NodeVisitor):
    """Max lexical nesting of control structures."""

    _BLOCK = (
        ast.If,
        ast.For,
        ast.While,
        ast.With,
        ast.Try,
        ast.Match,
        ast.AsyncFor,
        ast.AsyncWith,
    )

    def __init__(self) -> None:
        self._depth = 0
        self.max_depth = 0

    def generic_visit(self, node: ast.AST) -> None:
        push = isinstance(node, self._BLOCK)
        if push:
            self._depth += 1
            self.max_depth = max(self.max_depth, self._depth)
        super().generic_visit(node)
        if push:
            self._depth -= 1


def _cyclomatic(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    v = _CyclomaticVisitor()
    for stmt in fn.body:
        v.visit(stmt)
    return v.complexity


def _max_nesting(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    v = _NestingVisitor()
    for stmt in fn.body:
        v.visit(stmt)
    return v.max_depth


def _halstead_estimates(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[int, int]:
    """Rough operator / operand counts from AST leaves inside function body."""

    class V(ast.NodeVisitor):
        def __init__(self) -> None:
            self.operators = 0
            self.operands = 0

        def visit_BoolOp(self, node: ast.BoolOp) -> None:
            self.operators += len(node.values) - 1
            self.generic_visit(node)

        def visit_BinOp(self, node: ast.BinOp) -> None:
            self.operators += 1
            self.generic_visit(node)

        def visit_UnaryOp(self, node: ast.UnaryOp) -> None:
            self.operators += 1
            self.generic_visit(node)

        def visit_Compare(self, node: ast.Compare) -> None:
            self.operators += len(node.ops)
            self.generic_visit(node)

        def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
            self.operators += 1
            self.generic_visit(node)

        def visit_Call(self, node: ast.Call) -> None:
            self.operators += 1
            self.generic_visit(node)

        def visit_Subscript(self, node: ast.Subscript) -> None:
            self.operators += 1
            self.generic_visit(node)

        def visit_Attribute(self, node: ast.Attribute) -> None:
            self.operands += 1

        def visit_Name(self, node: ast.Name) -> None:
            if isinstance(node.ctx, ast.Load):
                self.operands += 1

        def visit_Constant(self, node: ast.Constant) -> None:
            self.operands += 1

    v = V()
    for stmt in fn.body:
        v.visit(stmt)
    return v.operators, v.operands


@dataclass
class FileStats:
    path: str
    physical_lines: int = 0
    logical_lines: int = 0
    comment_lines: int = 0
    functions: list[dict] = field(default_factory=list)


def _line_stats(source: str) -> tuple[int, int, int]:
    physical = len(source.splitlines())
    logical = 0
    comments = 0
    for line in source.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            comments += 1
            continue
        if "#" in line:
            pre, _post = line.split("#", 1)
            if pre.strip():
                logical += 1
            else:
                comments += 1
        else:
            logical += 1
    return physical, logical, comments


def _analyze_file(path: Path, root: Path) -> FileStats:
    raw = path.read_text(encoding="utf-8")
    physical, logical, comment_lines = _line_stats(raw)
    tree = ast.parse(raw)
    try:
        rel = str(path.relative_to(root).as_posix())
    except ValueError:
        rel = str(path.as_posix())

    stats = FileStats(path=rel, physical_lines=physical, logical_lines=logical, comment_lines=comment_lines)
    funs: list[ast.FunctionDef | ast.AsyncFunctionDef] = []

    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            funs.append(node)
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                    funs.append(item)

    for fn in funs:
        cyc = _cyclomatic(fn)
        nest = _max_nesting(fn)
        n1, n2 = _halstead_estimates(fn)
        n = n1 + n2
        volume = float(n * __import__("math").log2(max(2.0, float(n))))
        stats.functions.append(
            {
                "name": fn.name,
                "cyclomatic_complexity": cyc,
                "max_nesting_depth": nest,
                "halstead_operators_est": n1,
                "halstead_operands_est": n2,
                "halstead_volume_est": round(volume, 2),
            }
        )
    return stats


def _duplicate_line_score(files: list[Path]) -> float:
    line_map: dict[str, list[str]] = defaultdict(list)
    for fp in files:
        for i, line in enumerate(fp.read_text(encoding="utf-8").splitlines(), 1):
            key = re.sub(r"\s+", " ", line.strip())
            if len(key) < 12 or key.startswith("#"):
                continue
            line_map[key].append(f"{fp.name}:{i}")
    dup_lines = sum(1 for _ln, locs in line_map.items() if len(locs) > 1)
    total_keyed = len(line_map)
    if total_keyed == 0:
        return 0.0
    return round(100.0 * dup_lines / total_keyed, 2)


def analyze_package(pkg: Path, root: Path) -> dict:
    py_files = sorted(pkg.rglob("*.py"))
    file_stats = [_analyze_file(p, root) for p in py_files]

    all_funcs = [f for fs in file_stats for f in fs.functions]
    cyclos = [f["cyclomatic_complexity"] for f in all_funcs]
    nestings = [f["max_nesting_depth"] for f in all_funcs]
    vols = [f["halstead_volume_est"] for f in all_funcs]

    loc_physical = sum(fs.physical_lines for fs in file_stats)
    loc_logical = sum(fs.logical_lines for fs in file_stats)
    comments = sum(fs.comment_lines for fs in file_stats)

    dup_score = _duplicate_line_score(py_files)
    decision_sum = sum(c - 1 for c in cyclos)
    avg_cyc = round(sum(cyclos) / len(cyclos), 2) if cyclos else 0.0
    max_cyc = max(cyclos) if cyclos else 0
    avg_nest = round(sum(nestings) / len(nestings), 2) if nestings else 0.0
    max_nest = max(nestings) if nestings else 0

    halstead_avg_vol = round(sum(vols) / len(vols), 2) if vols else 0.0
    halstead_total_vol = round(sum(vols), 2)

    comment_density = round(comments / max(1, loc_physical), 4)

    readability_proxy = 0.0
    if cyclos:
        readability_proxy = round(max(0, min(100, 100 - (max_cyc * 1.2 + max_nest * 4))), 2)

    decision_per_100_loc = round((decision_sum / max(1, loc_logical)) * 100, 2)

    return {
        "lines_of_code_physical": loc_physical,
        "lines_of_code_logical": loc_logical,
        "comment_line_count": comments,
        "comment_density": comment_density,
        "function_count": len(all_funcs),
        "file_count": len(py_files),
        "avg_cyclomatic_complexity": avg_cyc,
        "max_cyclomatic_complexity": max_cyc,
        "sum_cyclomatic_complexity": sum(cyclos),
        "total_decision_points": decision_sum,
        "avg_max_nesting_per_function": avg_nest,
        "max_nesting_depth": max_nest,
        "halstead_avg_volume_est": halstead_avg_vol,
        "halstead_total_volume_est": halstead_total_vol,
        "duplicate_line_cluster_score": dup_score,
        "readability_proxy_score": readability_proxy,
        "decision_points_per_100_loc": decision_per_100_loc,
        "by_file": [
            {
                "path": fs.path,
                "physical_lines": fs.physical_lines,
                "logical_lines": fs.logical_lines,
                "function_count": len(fs.functions),
                "functions": fs.functions,
            }
            for fs in file_stats
        ],
    }


def load_profile(root: Path) -> dict:
    path = root / "metrics" / "profile.json"
    if not path.is_file():
        return {"metric_keys": list(_ALL_METRIC_KEYS)}
    data = json.loads(path.read_text(encoding="utf-8"))
    keys = data.get("metric_keys")
    if not keys:
        data["metric_keys"] = list(_ALL_METRIC_KEYS)
    return data


_ALL_METRIC_KEYS = (
    "lines_of_code_physical",
    "lines_of_code_logical",
    "comment_line_count",
    "comment_density",
    "function_count",
    "file_count",
    "avg_cyclomatic_complexity",
    "max_cyclomatic_complexity",
    "sum_cyclomatic_complexity",
    "total_decision_points",
    "avg_max_nesting_per_function",
    "max_nesting_depth",
    "halstead_avg_volume_est",
    "halstead_total_volume_est",
    "duplicate_line_cluster_score",
    "readability_proxy_score",
    "decision_points_per_100_loc",
)


def main() -> None:
    ap = argparse.ArgumentParser(description="White-box metrics snapshot")
    ap.add_argument("--root", type=Path, default=Path("."), help="Repo root")
    ap.add_argument("--pkg", type=Path, default=Path("src/complexity_sample"))
    ap.add_argument("-o", "--out", type=Path, default=None, help="Write JSON file")
    args = ap.parse_args()

    root = args.root.resolve()
    pkg = (root / args.pkg).resolve()
    if not pkg.is_dir():
        raise SystemExit(f"Package not found: {pkg}")

    profile = load_profile(root)
    metric_keys = profile.get("metric_keys") or list(_ALL_METRIC_KEYS)

    branch = profile.get("branch_label") or _git_branch(root)
    full = analyze_package(pkg, root)
    scores = {k: full[k] for k in metric_keys if k in full}

    report = {
        "schema_version": 1,
        "git_branch": branch,
        "package": str(args.pkg.as_posix()),
        "metric_profile": profile.get("metric_profile", "default"),
        "metric_focus": profile.get("metric_focus", []),
        "included_metrics": list(scores.keys()),
        "scores": scores,
        "notes": profile.get("notes", []),
    }

    text = json.dumps(report, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
