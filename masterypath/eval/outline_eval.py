"""Offline outline-quality evaluation (ADR-018 / spec 09).

Deterministic metrics need no model. The "semantic" KP precision/recall uses a
token-overlap proxy (no embeddings) so the CLI runs offline; swap in an embedder
later without changing the case format.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

_TOKEN = re.compile(r"[\w\u4e00-\u9fff]+")
_MATCH_THRESHOLD = 0.8
_COUNT_BOUNDS = (1, 60)


def _tokens(name: str) -> set[str]:
    return set(_TOKEN.findall(str(name or "").casefold()))


def _similar(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _kp_names(modules: list[dict[str, Any]]) -> list[str]:
    return [
        str(kp.get("name") or "")
        for module in modules
        for kp in (module.get("knowledge_points") or [])
    ]


def _acyclic(modules: list[dict[str, Any]]) -> bool:
    graph: dict[str, list[str]] = {}
    for module in modules:
        for kp in module.get("knowledge_points") or []:
            graph[str(kp.get("name"))] = [str(p) for p in (kp.get("prerequisites") or [])]
    state: dict[str, int] = {}

    def visit(node: str) -> bool:
        if state.get(node) == 1:
            return False
        if state.get(node) == 2:
            return True
        state[node] = 1
        for neighbour in graph.get(node, []):
            if neighbour in graph and not visit(neighbour):
                return False
        state[node] = 2
        return True

    return all(visit(node) for node in graph)


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    reference = _kp_names(case.get("reference_modules") or [])
    generated = _kp_names(case.get("generated_modules") or case.get("reference_modules") or [])
    matched = 0
    used: set[int] = set()
    for name in generated:
        for index, ref in enumerate(reference):
            if index in used:
                continue
            if _similar(name, ref) >= _MATCH_THRESHOLD:
                used.add(index)
                matched += 1
                break
    precision = matched / len(generated) if generated else 1.0
    recall = matched / len(reference) if reference else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    count = len(generated)
    return {
        "id": case.get("id", ""),
        "kp_precision": precision,
        "kp_recall": recall,
        "kp_f1": f1,
        "count_in_bounds": _COUNT_BOUNDS[0] <= count <= _COUNT_BOUNDS[1],
        "acyclic": _acyclic(case.get("generated_modules") or case.get("reference_modules") or []),
    }


def evaluate_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    per_case = [evaluate_case(case) for case in cases]
    if not per_case:
        return {"cases": [], "mean_kp_f1": 0.0, "all_acyclic": True, "all_in_bounds": True}
    mean = lambda key: sum(case[key] for case in per_case) / len(per_case)  # noqa: E731
    return {
        "cases": per_case,
        "mean_kp_precision": mean("kp_precision"),
        "mean_kp_recall": mean("kp_recall"),
        "mean_kp_f1": mean("kp_f1"),
        "all_acyclic": all(case["acyclic"] for case in per_case),
        "all_in_bounds": all(case["count_in_bounds"] for case in per_case),
    }


def load_cases(path: str | Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


__all__ = ["evaluate_case", "evaluate_cases", "load_cases"]
