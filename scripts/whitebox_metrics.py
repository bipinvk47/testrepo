#!/usr/bin/env python3
"""Compute white-box + performance-pattern metric snapshots across Python plus JS/TS/C#/Java/Go (stdlib only)."""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, cast


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


CYCLOMATIC_PERFORMANCE_HOTSPOT_THRESHOLD = 15
NESTED_LOOP_DEEP_LEVEL = 3
LARGE_REPEAT_THRESHOLD = 2048


def _callable_tail_name(call: ast.Call) -> tuple[str | None, str | None]:
    fn = call.func
    if isinstance(fn, ast.Name):
        return None, fn.id
    if isinstance(fn, ast.Attribute):
        root: ast.expr = fn.value
        while isinstance(root, ast.Attribute):
            root = root.value
        mod = root.id if isinstance(root, ast.Name) else None
        return mod, fn.attr
    return None, None


def _ast_call_maybe_db_query(call: ast.Call) -> bool:
    _, tail = _callable_tail_name(call)
    if tail and tail in frozenset(
        {
            "execute",
            "executemany",
            "fetchone",
            "fetchmany",
            "fetchall",
            "scalar",
            "first",
            "all",
            "get",
            "filter_by",
            "filter",
            "where",
            "refresh",
            "load",
            "run_sql",
            "statement",
            "invoke",
            "fetch",
        }
    ):
        return True
    try:
        condensed = "".join(ast.unparse(call).lower().split())
    except AttributeError:
        condensed = ""
    needles = (
        "select",
        ".execute(",
        "cursor.execute",
        ".query(",
        ".filter(",
        "joinedload",
        "session.query",
        "db.query",
        "repository.find",
        "repository.get",
        "axios.get",
    )
    return any(n in condensed for n in needles)


def _with_item_is_threading_lock(item: ast.withitem) -> bool:
    ce = item.context_expr
    if not isinstance(ce, ast.Call):
        return False
    fn = ce.func
    if isinstance(fn, ast.Attribute) and fn.attr in ("Lock", "RLock", "Semaphore"):
        return True
    _, nm = _callable_tail_name(ce)
    return nm in ("Lock", "RLock", "Semaphore")


def _binop_maybe_large_repeat(node: ast.BinOp) -> bool:
    if not isinstance(node.op, ast.Mult):
        return False
    for cand in (node.left, node.right):
        if isinstance(cand, ast.Constant) and isinstance(cand.value, (int, float)):
            if abs(int(cand.value)) >= LARGE_REPEAT_THRESHOLD:
                return True
    return False


def _iterable_literals_over_threshold(node: ast.AST, limit: int) -> bool:
    return isinstance(node, ast.List) and len(getattr(node, "elts", ())) >= limit


class _PythonPerfVisitor(ast.NodeVisitor):
    """Heuristic counters aligned with perf-testing dimensions (loops, queries, allocations, concurrency)."""

    def __init__(self, global_names: frozenset[str]) -> None:
        super().__init__()
        self._global_decl = global_names
        self.loop_depth = 0
        self.max_nested_loop_depth = 0
        self.nested_loop_deep_site_count = 0
        self.n_plus_one_signals = 0
        self.large_alloc_in_loop = 0
        self.thread_spawn_count = 0
        self._lock_ctx = 0
        self.racy_global_ops = 0

    def visit_With(self, node: ast.With) -> None:
        delta = sum(1 for it in node.items if _with_item_is_threading_lock(it))
        self._lock_ctx += delta
        self.generic_visit(node)
        self._lock_ctx -= delta

    def visit_For(self, node: ast.For) -> None:
        self._enter_loop(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self._enter_loop(node)

    def visit_While(self, node: ast.While) -> None:
        self._enter_loop(node)

    def _enter_loop(self, node: ast.AST) -> None:
        if self.loop_depth >= NESTED_LOOP_DEEP_LEVEL - 1:
            self.nested_loop_deep_site_count += 1
        self.loop_depth += 1
        self.max_nested_loop_depth = max(self.max_nested_loop_depth, self.loop_depth)
        self.generic_visit(node)
        self.loop_depth -= 1

    def visit_Call(self, node: ast.Call) -> None:
        _, tail = _callable_tail_name(node)
        if tail == "Thread":
            self.thread_spawn_count += 1
        if self.loop_depth >= 1 and self._lock_ctx == 0:
            if _ast_call_maybe_db_query(node):
                self.n_plus_one_signals += 1
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id in ("bytes", "bytearray"):
                self.large_alloc_in_loop += 1
            elif any(isinstance(a, ast.Starred) for a in node.args):
                self.large_alloc_in_loop += 1
            elif isinstance(fn, ast.Name) and fn.id == "list" and len(node.args) >= 1:
                if _iterable_literals_over_threshold(node.args[0], 500):
                    self.large_alloc_in_loop += 1
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        if self.loop_depth >= 1 and self._lock_ctx == 0 and _binop_maybe_large_repeat(node):
            self.large_alloc_in_loop += 1
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        if (
            self.loop_depth >= 1
            and self._lock_ctx == 0
            and isinstance(node.value, ast.BinOp)
            and _binop_maybe_large_repeat(cast(ast.BinOp, node.value))
        ):
            self.large_alloc_in_loop += 1
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        tgt = node.target
        name: str | None = None
        if isinstance(tgt, ast.Name):
            name = tgt.id
        if name and name in self._global_decl and self._lock_ctx == 0:
            self.racy_global_ops += 1
        self.generic_visit(node)


def _function_global_declarations(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> frozenset[str]:
    out: list[str] = []
    for stmt in fn.body:
        if isinstance(stmt, ast.Global):
            out.extend(stmt.names)
    return frozenset(out)


def _python_function_perf_snapshot(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, int]:
    globals_decl = _function_global_declarations(fn)
    visitor = _PythonPerfVisitor(globals_decl)
    for stmt in fn.body:
        visitor.visit(stmt)
    risk = 0
    if visitor.thread_spawn_count > 0:
        if visitor.racy_global_ops > 0:
            risk = visitor.thread_spawn_count + visitor.racy_global_ops
        else:
            risk = visitor.thread_spawn_count
    elif visitor.racy_global_ops > 0:
        risk = visitor.racy_global_ops
    return {
        "max_nested_loop_depth_in_function": visitor.max_nested_loop_depth,
        "nested_loop_deep_site_count_fn": visitor.nested_loop_deep_site_count,
        "n_plus_one_query_pattern_count_fn": visitor.n_plus_one_signals,
        "large_allocation_in_loop_count_fn": visitor.large_alloc_in_loop,
        "race_condition_risk_count_fn": risk,
    }


def _heuristic_perf_from_text(body: str) -> dict[str, int]:
    """Best-effort pattern counts for languages without AST wiring in this script."""
    lowered = body.lower()
    has_loop = bool(re.search(r"\b(for|foreach|while)\b", lowered))
    n_plus_one = 0
    large_alloc_loop = 0
    races = 0
    triple_loops = 0
    if has_loop and re.search(
        r"\b(execute|fetchone|fetchall|select\b|cursor\.|\bquery\b|\.where\b|sequelize|\baxios\b)",
        lowered,
        re.MULTILINE,
    ):
        n_plus_one += 1

    blocks = []
    brace = 0
    for ch in body:
        if ch == "{":
            brace += 1
        elif ch == "}":
            brace = max(0, brace - 1)
        blocks.append(brace)
    # crude: count `for` keywords at brace depth >= 2
    for m in re.finditer(r"\b(?:for|while)\b", lowered):
        pos = m.start()
        if pos < len(blocks) and blocks[pos] >= 2:
            triple_loops += 1
    if has_loop and re.search(r"(new\s+byte[\[\]]|make\(\[\]|malloc|strings\.repeat|array\(|alloc\()", lowered):
        large_alloc_loop += 1
    if re.search(r"\b(?:go\s+func|thread\s*\(|pthread_create|asyncio\.create_task)\b", lowered):
        if re.search(r"\s(\+\+|\+=|\.push\(|\.append\()", lowered):
            races += 1
    max_br_depth = max(blocks) if blocks else 0
    return {
        "max_nested_loop_depth_in_function_heuristic": min(max_br_depth + triple_loops // 6, 32),
        "nested_loop_deep_site_count_heuristic_fn": triple_loops,
        "n_plus_one_query_pattern_count_heuristic_fn": n_plus_one,
        "large_allocation_in_loop_count_heuristic_fn": large_alloc_loop,
        "race_condition_risk_count_heuristic_fn": races,
    }


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
    r"\b(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(",
    re.MULTILINE,
)

_JVM_CLR_METHOD = re.compile(
    r"\bpublic\s+static\s+[\w.]+\s+(\w+)\s*\(",
    re.MULTILINE,
)

_GO_FUNC_HEAD = re.compile(r"\bfunc\s+([A-Za-z_][\w]*)\s*\(", re.MULTILINE)


def _skip_balanced_square_bracket(s: str, open_idx: int) -> int:
    if open_idx < 0 or open_idx >= len(s) or s[open_idx] != "[":
        return -1
    depth = 0
    i = open_idx
    while i < len(s):
        if s[i] == "[":
            depth += 1
        elif s[i] == "]":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1



def _advance_past_optional_return_type_find_body_brace(
    source: str, close_paren_idx: int
) -> int:
    """After closing `)` of parameters, skip annotation/return type and return index of `{` opening the body."""
    n = len(source)

    def skip_ws(idx: int) -> int:
        while idx < n and source[idx] in " \t\r\n":
            idx += 1
        return idx

    i = skip_ws(close_paren_idx + 1)
    if i < n and source[i] == "{":
        return i
    if i < n and source[i] == ":":
        return _ts_return_type_then_body_brace(source, skip_ws(i + 1))
    return _go_return_then_body_brace(source, skip_ws(i))


def _ts_return_type_then_body_brace(source: str, start: int) -> int:
    """Parse TypeScript return type annotation until `{` opens the statement body."""

    def skip_ws(idx: int) -> int:
        nloc = len(source)
        while idx < nloc and source[idx] in " \t\r\n":
            idx += 1
        return idx

    def skip_comments(idx: int) -> int:
        nloc = len(source)
        while idx < nloc:
            idx = skip_ws(idx)
            if idx + 1 < nloc and source[idx : idx + 2] == "//":
                idx = source.find("\n", idx + 2)
                if idx < 0:
                    return nloc
                continue
            if idx + 1 < nloc and source[idx : idx + 2] == "/*":
                end = source.find("*/", idx + 2)
                idx = end + 2 if end >= 0 else nloc
                continue
            break
        return idx

    def skip_string_literal(idx: int) -> int:
        nloc = len(source)
        q = source[idx]
        idx += 1
        while idx < nloc:
            if source[idx] == "\\":
                idx += min(2, nloc - idx)
                continue
            if source[idx] == q:
                return idx + 1
            idx += 1
        return idx

    n = len(source)
    i = start
    parens = brackets = angles = bruces = 0

    while i < n:
        i = skip_comments(i)
        if i >= n:
            break
        c = source[i]

        if c in "'\"":
            i = skip_string_literal(i)
            continue
        if c == "`":
            i += 1
            while i < n:
                if source[i] == "\\":
                    i += min(2, n - i)
                    continue
                if source[i] == "`":
                    i += 1
                    break
                if source[i] == "${":
                    i += 2
                    continue

                i += 1

            continue

        if bruces == parens == brackets == angles == 0 and c == "{":
            return i
        if c == "(":
            parens += 1
            i += 1
            continue
        if c == ")":
            parens = max(0, parens - 1)
            i += 1
            continue
        if c == "[":
            brackets += 1
            i += 1
            continue
        if c == "]":
            brackets = max(0, brackets - 1)
            i += 1
            continue
        if c == "{":
            bruces += 1
            i += 1
            continue
        if c == "}":
            bruces = max(0, bruces - 1)
            i += 1
            continue
        # Generics `<Foo>` vs comparison `x < y` — treat `<` before alpha / `[` etc as angle.
        if c == "<":
            lookahead = skip_ws(i + 1)
            if lookahead < n and (
                source[lookahead].isalpha()
                or source[lookahead] in "_$"
                or source[lookahead] in "[\"'"
            ):
                angles += 1

            elif lookahead < n and source[lookahead] == "{" and bruces > 0:
                angles += 1
            elif angles > 0:
                angles += 1
            elif i + 1 < n and source[i + 1] not in "=":
                angles += 1
            else:
                i += 1
                continue

            i += 1

            continue
        if c == ">":
            if angles > 0:
                angles -= 1


            i += 1




            continue

        # Type keywords / punctuation

        # Default: consume one logical character chunk (identifier or operator-ish)
        if c.isalpha() or c == "_":
            i += 1
            while i < n and (source[i].isalnum() or source[i] in "_$"):
                i += 1
            continue
        i += 1



    return -1




def _go_return_then_body_brace(source: str, start: int) -> int:
    """Skip Go-style return types before `{`."""




    def skip_ws(idx: int) -> int:


        while idx < len(source) and source[idx] in " \t\r\n":
            idx += 1




        return idx




    i = skip_ws(start)
    while i < len(source):
        i = skip_ws(i)
        if i >= len(source):


            break


        if source[i] == "{":




            return i


        if source[i] == "(":
            j = _skip_balanced_paren(source, i)
            if j < 0:
                return -1
            i = j + 1
            continue
        if source[i] == "[":
            j = _skip_balanced_square_bracket(source, i)


            if j < 0:
                return -1
            i = j + 1
            continue
        if source[i] in "*&":
            i += 1
            continue
        if source[i].isalpha() or source[i] == "_":
            i += 1
            while i < len(source) and (source[i].isalnum() or source[i] == "_"):
                i += 1
            continue
        i += 1




    return -1




def _iter_js_function_bodies(source: str) -> list[tuple[str, str]]:
    bodies: list[tuple[str, str]] = []
    for m in _JS_FUNC_HEAD.finditer(source):
        name = m.group(1)
        open_paren = source.find("(", m.start())
        close_paren = _skip_balanced_paren(source, open_paren)
        if close_paren < 0:
            continue
        brace_open = _advance_past_optional_return_type_find_body_brace(source, close_paren)
        if brace_open < 0:
            continue
        close_brace = _find_matching_brace(source, brace_open)
        if close_brace < 0:


            continue
        bodies.append((name, source[brace_open + 1 : close_brace]))

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
        brace_open = _advance_past_optional_return_type_find_body_brace(source, close_paren)
        if brace_open < 0:
            continue
        close_brace = _find_matching_brace(source, brace_open)
        if close_brace < 0:
            continue
        bodies.append((name, source[brace_open + 1 : close_brace]))
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
        perf = _python_function_perf_snapshot(fn)
        stats.functions.append(
            {
                "name": fn.name,
                "cyclomatic_complexity": cyc,
                "max_nesting_depth": nest,
                "halstead_operators_est": n1,
                "halstead_operands_est": n2,
                "halstead_volume_est": round(volume, 2),
                **perf,
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
        hz = _heuristic_perf_from_text(body)
        stats.functions.append(
            {
                "name": name,
                "cyclomatic_complexity": cyc,
                "max_nesting_depth": nest,
                "halstead_operators_est": n1,
                "halstead_operands_est": n2,
                "halstead_volume_est": round(volume, 2),
                **hz,
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
        hz = _heuristic_perf_from_text(body)
        stats.functions.append(
            {
                "name": name,
                "cyclomatic_complexity": cyc,
                "max_nesting_depth": nest,
                "halstead_operators_est": n1,
                "halstead_operands_est": n2,
                "halstead_volume_est": round(volume, 2),
                **hz,
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
        hz = _heuristic_perf_from_text(body)
        stats.functions.append(
            {
                "name": name,
                "cyclomatic_complexity": cyc,
                "max_nesting_depth": nest,
                "halstead_operators_est": n1,
                "halstead_operands_est": n2,
                "halstead_volume_est": round(volume, 2),
                **hz,
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

    per_fn_nested_peak: list[int] = []
    for fn in all_funcs:
        cand = []
        k1 = fn.get("max_nested_loop_depth_in_function")
        k2 = fn.get("max_nested_loop_depth_in_function_heuristic")
        if isinstance(k1, int) and k1 > 0:
            cand.append(k1)
        if isinstance(k2, int) and k2 > 0:
            cand.append(k2)
        if cand:
            per_fn_nested_peak.append(max(cand))

    max_nested_loop_depth = max(per_fn_nested_peak) if per_fn_nested_peak else 0

    nested_loop_deep_site_total = sum(
        int(fn.get("nested_loop_deep_site_count_fn", 0) or 0)
        + int(fn.get("nested_loop_deep_site_count_heuristic_fn", 0) or 0)
        for fn in all_funcs
    )
    n_plus_one_query_pattern_count = sum(
        int(fn.get("n_plus_one_query_pattern_count_fn", 0) or 0)
        + int(fn.get("n_plus_one_query_pattern_count_heuristic_fn", 0) or 0)
        for fn in all_funcs
    )
    large_allocation_in_loop_count = sum(
        int(fn.get("large_allocation_in_loop_count_fn", 0) or 0)
        + int(fn.get("large_allocation_in_loop_count_heuristic_fn", 0) or 0)
        for fn in all_funcs
    )
    race_condition_risk_count = sum(
        int(fn.get("race_condition_risk_count_fn", 0) or 0)
        + int(fn.get("race_condition_risk_count_heuristic_fn", 0) or 0)
        for fn in all_funcs
    )
    cyclomatic_performance_hotspot_count = sum(
        1 for fn in all_funcs if int(fn["cyclomatic_complexity"]) >= CYCLOMATIC_PERFORMANCE_HOTSPOT_THRESHOLD
    )

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
        "max_nested_loop_depth": max_nested_loop_depth,
        "nested_loop_deep_site_total": nested_loop_deep_site_total,
        "cyclomatic_performance_hotspot_count": cyclomatic_performance_hotspot_count,
        "n_plus_one_query_pattern_count": n_plus_one_query_pattern_count,
        "large_allocation_in_loop_count": large_allocation_in_loop_count,
        "race_condition_risk_count": race_condition_risk_count,
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
    *,
    include_benchmark_fixture: bool = False,
) -> tuple[dict, dict[str, list[Path]]]:
    combined: list[FileStats] = []
    dup_targets: list[Path] = []
    by_lang: dict[str, list[Path]] = {}

    perf_lab_root = root / "src" / "performance_risk_lab"
    py_candidates: list[Path] = []
    if py_pkg.is_dir():
        py_candidates.extend(sorted(py_pkg.rglob("*.py")))
    if perf_lab_root.is_dir():
        py_candidates.extend(sorted(perf_lab_root.rglob("*.py")))
    if include_benchmark_fixture:
        bx = root / "fixtures" / "benchmark-subject"
        if bx.is_dir():
            py_candidates.extend(sorted(bx.rglob("*.py")))
    py_files = sorted(dict.fromkeys(py_candidates))
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
    "cyclomatic_performance_hotspot_count",
    "max_nested_loop_depth",
    "nested_loop_deep_site_total",
    "n_plus_one_query_pattern_count",
    "large_allocation_in_loop_count",
    "race_condition_risk_count",
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
    ap.add_argument(
        "--with-benchmark-fixture",
        action="store_true",
        help="Include Python sources under fixtures/benchmark-subject/ (clone Django via scripts/clone_performance_fixture.ps1/.sh)",
    )
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
    bx_root = root / "fixtures" / "benchmark-subject"
    benchmark_loaded = bool(
        args.with_benchmark_fixture and bx_root.is_dir() and any(bx_root.rglob("*.py"))
    )
    if args.with_benchmark_fixture and bx_root.is_dir() and not benchmark_loaded:
        print(
            "warning: --with-benchmark-fixture set but no *.py under fixtures/benchmark-subject/. "
            "Run scripts/clone_performance_fixture.ps1 (Windows) or scripts/clone_performance_fixture.sh.",
            flush=True,
        )
    if args.with_benchmark_fixture and not bx_root.is_dir():
        print(
            "warning: fixtures/benchmark-subject/ does not exist yet. Clone with scripts/clone_performance_fixture.ps1 or .sh.",
            flush=True,
        )

    full, by_lang_files = analyze_repo(
        root,
        py_pkg,
        javascript_pkg,
        include_benchmark_fixture=args.with_benchmark_fixture,
    )
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
    perf_lab = root / "src" / "performance_risk_lab"
    if perf_lab.is_dir():
        pkgs["python_performance_risk_lab"] = _rel_posix(perf_lab, root)
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
    if benchmark_loaded:
        pkgs["benchmark_fixture"] = _rel_posix(bx_root, root)

    report = {
        "schema_version": 3,
        "benchmark_fixture_requested": bool(args.with_benchmark_fixture),
        "benchmark_fixture_loaded": benchmark_loaded,
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
