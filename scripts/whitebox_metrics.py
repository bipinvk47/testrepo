#!/usr/bin/env python3
"""Compute white-box metric snapshots for six-language samples (Python, JS, TS, C#, Java, Go; no third-party deps)."""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


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


def _js_line_stats(source: str) -> tuple[int, int, int]:
    physical = len(source.splitlines())
    without_blocks = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    logical = 0
    comments = 0
    for line in without_blocks.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("//"):
            comments += 1
            continue
        if "//" in line:
            pre, _post = line.split("//", 1)
            if pre.strip():
                logical += 1
            else:
                comments += 1
        else:
            logical += 1
    return physical, logical, comments


def _skip_balanced_paren(s: str, open_idx: int) -> int:
    if open_idx < 0 or open_idx >= len(s) or s[open_idx] != "(":
        return -1
    depth = 0
    i = open_idx
    while i < len(s):
        if s[i] == "(":
            depth += 1
        elif s[i] == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _find_matching_brace(s: str, brace_open_idx: int) -> int:
    depth = 0
    i = brace_open_idx
    while i < len(s):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


_JS_FUNC_HEAD = re.compile(
    r"\b(?:export\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(",
    re.MULTILINE,
)

_JVM_CLR_METHOD = re.compile(
    r"\bpublic\s+static\s+[\w.]+\s+(\w+)\s*\(",
    re.MULTILINE,
)

_GO_FUNC_HEAD = re.compile(r"\bfunc\s+([A-Za-z_][\w]*)\s*\(", re.MULTILINE)


def _iter_js_function_bodies(source: str) -> list[tuple[str, str]]:
    bodies: list[tuple[str, str]] = []
    for m in _JS_FUNC_HEAD.finditer(source):
        name = m.group(1)
        open_paren = source.find("(", m.start())
        close_paren = _skip_balanced_paren(source, open_paren)
        if close_paren < 0:
            continue
        i = close_paren + 1
        while i < len(source) and source[i] in " \t\r\n":
            i += 1
        if i >= len(source) or source[i] != "{":
            continue
        close_brace = _find_matching_brace(source, i)
        if close_brace < 0:
            continue
        bodies.append((name, source[i + 1 : close_brace]))
    return bodies


def _iter_public_static_method_bodies(source: str) -> list[tuple[str, str]]:
    bodies: list[tuple[str, str]] = []
    for m in _JVM_CLR_METHOD.finditer(source):
        name = m.group(1)
        open_paren = source.find("(", m.start())
        close_paren = _skip_balanced_paren(source, open_paren)
        if close_paren < 0:
            continue
        i = close_paren + 1
        while i < len(source) and source[i] in " \t\r\n":
            i += 1
        if i >= len(source) or source[i] != "{":
            continue
        close_brace = _find_matching_brace(source, i)
        if close_brace < 0:
            continue
        bodies.append((name, source[i + 1 : close_brace]))
    return bodies


def _iter_go_function_bodies(source: str) -> list[tuple[str, str]]:
    bodies: list[tuple[str, str]] = []
    for m in _GO_FUNC_HEAD.finditer(source):
        name = m.group(1)
        open_paren = source.find("(", m.start())
        close_paren = _skip_balanced_paren(source, open_paren)
        if close_paren < 0:
            continue
        i = close_paren + 1
        while i < len(source) and source[i] in " \t\r\n":
            i += 1
        if i >= len(source) or source[i] != "{":
            continue
        close_brace = _find_matching_brace(source, i)
        if close_brace < 0:
            continue
        bodies.append((name, source[i + 1 : close_brace]))
    return bodies


def _halstead_estimates_js(body: str) -> tuple[int, int]:
    operators = len(re.findall(r"\+\+|--|&&|\|\||[+\-*/%=<>!?:]+", body))
    identifiers = len(re.findall(r"\b[A-Za-z_$][\w$]*\b", body))
    numeric = len(re.findall(r"\b\d+\.?\d*\b", body))
    operands = identifiers + numeric
    return operators, operands


def _c_family_cyclomatic(body: str) -> int:
    decisions = 0
    decisions += len(re.findall(r"\bif\s*\(", body))
    decisions += len(re.findall(r"\belse\s+if\s*\(", body))
    decisions += len(re.findall(r"\bwhile\s*\(", body))
    decisions += len(re.findall(r"\bfor\s*\(", body))
    decisions += len(re.findall(r"\bforeach\s*\(", body))
    decisions += len(re.findall(r"\bcatch\s*\(", body))
    decisions += len(re.findall(r"\bcase\s+[^:]+:", body))
    decisions += len(re.findall(r"\?", body))
    decisions += len(re.findall(r"&&", body))
    decisions += len(re.findall(r"\|\|", body))
    return 1 + decisions


def _go_cyclomatic(body: str) -> int:
    decisions = 0
    decisions += len(re.findall(r"\bif\b", body))
    decisions += len(re.findall(r"\bfor\b", body))
    decisions += len(re.findall(r"\bswitch\b", body))
    decisions += len(re.findall(r"\bcase\s+", body))
    decisions += len(re.findall(r"&&", body))
    decisions += len(re.findall(r"\|\|", body))
    return 1 + decisions


def _js_max_brace_nesting(body: str) -> int:
    depth = 0
    max_d = 0
    for c in body:
        if c == "{":
            depth += 1
            max_d = max(max_d, depth)
        elif c == "}":
            depth = max(0, depth - 1)
    return max_d


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


def _analyze_js_like_file(path: Path, root: Path) -> FileStats:
    raw = path.read_text(encoding="utf-8")
    physical, logical, comment_lines = _js_line_stats(raw)
    try:
        rel = str(path.relative_to(root).as_posix())
    except ValueError:
        rel = str(path.as_posix())

    stats = FileStats(
        path=rel,
        physical_lines=physical,
        logical_lines=logical,
        comment_lines=comment_lines,
    )
    for name, body in _iter_js_function_bodies(raw):
        cyc = _c_family_cyclomatic(body)
        nest = _js_max_brace_nesting(body)
        n1, n2 = _halstead_estimates_js(body)
        n = n1 + n2
        volume = float(n * __import__("math").log2(max(2.0, float(n))))
        stats.functions.append(
            {
                "name": name,
                "cyclomatic_complexity": cyc,
                "max_nesting_depth": nest,
                "halstead_operators_est": n1,
                "halstead_operands_est": n2,
                "halstead_volume_est": round(volume, 2),
            }
        )
    return stats


def _analyze_ts_file(path: Path, root: Path) -> FileStats:
    return _analyze_js_like_file(path, root)


def _analyze_java_csharp_file(path: Path, root: Path) -> FileStats:
    raw = path.read_text(encoding="utf-8")
    physical, logical, comment_lines = _js_line_stats(raw)
    try:
        rel = str(path.relative_to(root).as_posix())
    except ValueError:
        rel = str(path.as_posix())

    stats = FileStats(
        path=rel,
        physical_lines=physical,
        logical_lines=logical,
        comment_lines=comment_lines,
    )
    for name, body in _iter_public_static_method_bodies(raw):
        cyc = _c_family_cyclomatic(body)
        nest = _js_max_brace_nesting(body)
        n1, n2 = _halstead_estimates_js(body)
        n = n1 + n2
        volume = float(n * __import__("math").log2(max(2.0, float(n))))
        stats.functions.append(
            {
                "name": name,
                "cyclomatic_complexity": cyc,
                "max_nesting_depth": nest,
                "halstead_operators_est": n1,
                "halstead_operands_est": n2,
                "halstead_volume_est": round(volume, 2),
            }
        )
    return stats


def _analyze_go_file(path: Path, root: Path) -> FileStats:
    raw = path.read_text(encoding="utf-8")
    physical, logical, comment_lines = _js_line_stats(raw)
    try:
        rel = str(path.relative_to(root).as_posix())
    except ValueError:
        rel = str(path.as_posix())

    stats = FileStats(
        path=rel,
        physical_lines=physical,
        logical_lines=logical,
        comment_lines=comment_lines,
    )
    for name, body in _iter_go_function_bodies(raw):
        cyc = _go_cyclomatic(body)
        nest = _js_max_brace_nesting(body)
        n1, n2 = _halstead_estimates_js(body)
        n = n1 + n2
        volume = float(n * __import__("math").log2(max(2.0, float(n))))
        stats.functions.append(
            {
                "name": name,
                "cyclomatic_complexity": cyc,
                "max_nesting_depth": nest,
                "halstead_operators_est": n1,
                "halstead_operands_est": n2,
                "halstead_volume_est": round(volume, 2),
            }
        )
    return stats


def _analyze_js_file(path: Path, root: Path) -> FileStats:
    return _analyze_js_like_file(path, root)


def _duplicate_line_score(files: list[Path]) -> float:
    line_map: dict[str, list[str]] = defaultdict(list)
    for fp in files:
        for i, line in enumerate(fp.read_text(encoding="utf-8").splitlines(), 1):
            key = re.sub(r"\s+", " ", line.strip())
            if len(key) < 12 or key.startswith("#") or key.startswith("//") or key.startswith("*"):
                continue
            line_map[key].append(f"{fp.name}:{i}")
    dup_lines = sum(1 for _ln, locs in line_map.items() if len(locs) > 1)
    total_keyed = len(line_map)
    if total_keyed == 0:
        return 0.0
    return round(100.0 * dup_lines / total_keyed, 2)


def _aggregate_metrics(file_stats: list[FileStats], dup_targets: list[Path]) -> dict:
    all_funcs = [f for fs in file_stats for f in fs.functions]
    cyclos = [f["cyclomatic_complexity"] for f in all_funcs]
    nestings = [f["max_nesting_depth"] for f in all_funcs]
    vols = [f["halstead_volume_est"] for f in all_funcs]

    loc_physical = sum(fs.physical_lines for fs in file_stats)
    loc_logical = sum(fs.logical_lines for fs in file_stats)
    comments = sum(fs.comment_lines for fs in file_stats)

    py_js_files = sorted(dup_targets)
    dup_score = _duplicate_line_score(py_js_files) if py_js_files else 0.0
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

    file_count = len({fs.path for fs in file_stats})

    return {
        "lines_of_code_physical": loc_physical,
        "lines_of_code_logical": loc_logical,
        "comment_line_count": comments,
        "comment_density": comment_density,
        "function_count": len(all_funcs),
        "file_count": file_count,
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


def analyze_package(pkg: Path, root: Path) -> dict:
    py_files = sorted(pkg.rglob("*.py"))
    file_stats = [_analyze_file(p, root) for p in py_files]
    return _aggregate_metrics(file_stats, py_files)


def analyze_repo(
    root: Path,
    py_pkg: Path,
    javascript_pkg: Path | None,
) -> tuple[dict, dict[str, list[Path]]]:
    combined: list[FileStats] = []
    dup_targets: list[Path] = []
    by_lang: dict[str, list[Path]] = {}

    py_files = sorted(py_pkg.rglob("*.py")) if py_pkg.is_dir() else []
    if py_files:
        by_lang["python"] = py_files
        dup_targets.extend(py_files)
        combined.extend(_analyze_file(p, root) for p in py_files)

    lang_specs: list[tuple[str, Path, str, Callable[[Path, Path], FileStats]]] = []
    if javascript_pkg is not None and javascript_pkg.is_dir():
        lang_specs.append(("javascript", javascript_pkg, "*.js", _analyze_js_like_file))
    ts_root = root / "src" / "complexity_sample_ts"
    if ts_root.is_dir():
        lang_specs.append(("typescript", ts_root, "*.ts", _analyze_ts_file))
    cs_root = root / "src" / "complexity_sample_cs"
    if cs_root.is_dir():
        lang_specs.append(("csharp", cs_root, "*.cs", _analyze_java_csharp_file))
    java_root = root / "src" / "complexity_sample_java"
    if java_root.is_dir():
        lang_specs.append(("java", java_root, "*.java", _analyze_java_csharp_file))
    go_root = root / "src" / "complexity_sample_go"
    if go_root.is_dir():
        lang_specs.append(("go", go_root, "*.go", _analyze_go_file))

    for label, base, pattern, analyzer in lang_specs:
        paths = sorted(base.rglob(pattern))
        if not paths:
            continue
        by_lang[label] = paths
        dup_targets.extend(paths)
        combined.extend(analyzer(p, root) for p in paths)

    full = _aggregate_metrics(combined, dup_targets)
    return full, by_lang


def load_profile(root: Path) -> dict:
    path = root / "metrics" / "profile.json"
    if not path.is_file():
        return {"metric_keys": list(_ALL_METRIC_KEYS)}
    data = json.loads(path.read_text(encoding="utf-8"))
    keys = data.get("metric_keys")
    if not keys:
        data["metric_keys"] = list(_ALL_METRIC_KEYS)
    return data


def _rel_posix(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root).as_posix())
    except ValueError:
        return str(path.as_posix())


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
    ap.add_argument(
        "--js-pkg",
        type=Path,
        default=None,
        help="Optional JavaScript package dir (default: src/complexity_sample_js when it exists)",
    )
    ap.add_argument("-o", "--out", type=Path, default=None, help="Write JSON file")
    args = ap.parse_args()

    root = args.root.resolve()
    py_pkg = (root / args.pkg).resolve()
    if not py_pkg.is_dir():
        raise SystemExit(f"Package not found: {py_pkg}")

    if args.js_pkg is None:
        js_cand = (root / "src" / "complexity_sample_js").resolve()
        javascript_pkg = js_cand if js_cand.is_dir() else None
    else:
        javascript_pkg = (root / args.js_pkg).resolve()
        if not javascript_pkg.is_dir():
            raise SystemExit(f"JavaScript package not found: {javascript_pkg}")

    profile = load_profile(root)
    metric_keys = profile.get("metric_keys") or list(_ALL_METRIC_KEYS)

    branch = profile.get("branch_label") or _git_branch(root)
    full, by_lang_files = analyze_repo(root, py_pkg, javascript_pkg)
    scores = {k: v for k, v in full.items() if k != "by_file"}

    by_language: dict[str, dict] = {}
    for label, paths in sorted(by_lang_files.items()):
        if not paths:
            continue
        if label == "python":
            part = _aggregate_metrics([_analyze_file(p, root) for p in paths], paths)
        elif label == "javascript":
            part = _aggregate_metrics([_analyze_js_like_file(p, root) for p in paths], paths)
        elif label == "typescript":
            part = _aggregate_metrics([_analyze_ts_file(p, root) for p in paths], paths)
        elif label in ("csharp", "java"):
            part = _aggregate_metrics([_analyze_java_csharp_file(p, root) for p in paths], paths)
        elif label == "go":
            part = _aggregate_metrics([_analyze_go_file(p, root) for p in paths], paths)
        else:
            continue
        by_language[label] = {k: v for k, v in part.items() if k != "by_file"}

    pkgs: dict[str, str] = {"python": _rel_posix(py_pkg, root)}
    if javascript_pkg is not None:
        pkgs["javascript"] = _rel_posix(javascript_pkg, root)
    ts_root = root / "src" / "complexity_sample_ts"
    if ts_root.is_dir():
        pkgs["typescript"] = _rel_posix(ts_root, root)
    cs_root = root / "src" / "complexity_sample_cs"
    if cs_root.is_dir():
        pkgs["csharp"] = _rel_posix(cs_root, root)
    java_root = root / "src" / "complexity_sample_java"
    if java_root.is_dir():
        pkgs["java"] = _rel_posix(java_root, root)
    go_root = root / "src" / "complexity_sample_go"
    if go_root.is_dir():
        pkgs["go"] = _rel_posix(go_root, root)

    report = {
        "schema_version": 3,
        "languages": sorted(by_lang_files.keys()),
        "git_branch": branch,
        "packages": pkgs,
        "package": str(args.pkg.as_posix()),
        "metric_profile": profile.get("metric_profile", "default"),
        "metric_focus": profile.get("metric_focus", []),
        "profile_metric_keys": metric_keys,
        "included_metrics": sorted(scores.keys()),
        "scores": dict(sorted(scores.items())),
        "by_language": by_language,
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
