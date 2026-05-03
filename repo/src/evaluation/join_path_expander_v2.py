"""join_path_expander_v2 — FK-graph shortest-path expansion.

Given anchor tables (e.g. retrieval result), expand the working set
with intermediate tables required to connect them via FK paths. The
intent: never lose a join because retrieval missed a bridge table.

Implementation is pure-Python BFS so we don't pull a graph dependency.
For SF DB sizes (5-30 tables) BFS is plenty fast.
"""
from __future__ import annotations

from collections import deque
from typing import Iterable


def _build_adjacency(ir) -> dict[str, list[tuple[str, str, str, str]]]:
    """name -> list of (neighbour, src_col, dst_col, neighbour_col)."""
    adj: dict[str, list[tuple[str, str, str, str]]] = {}
    for e in ir.fk_edges:
        adj.setdefault(e.from_table, []).append(
            (e.to_table, e.from_column, e.to_column, e.to_column))
        adj.setdefault(e.to_table, []).append(
            (e.from_table, e.to_column, e.from_column, e.from_column))
    return adj


def shortest_path(ir, src: str, dst: str, *, max_hops: int = 5) -> list[str] | None:
    """BFS shortest path of table names from src to dst (inclusive)."""
    if src == dst: return [src]
    adj = _build_adjacency(ir)
    if src not in adj: return None
    seen = {src: None}
    q = deque([src])
    while q:
        cur = q.popleft()
        if len(_reconstruct(seen, cur)) - 1 > max_hops: continue
        for (nb, *_rest) in adj.get(cur, []):
            if nb in seen: continue
            seen[nb] = cur
            if nb == dst: return _reconstruct(seen, nb)
            q.append(nb)
    return None


def _reconstruct(seen: dict[str, str | None], node: str) -> list[str]:
    out = [node]
    cur = seen.get(node)
    while cur is not None:
        out.append(cur); cur = seen.get(cur)
    out.reverse()
    return out


def expand_anchors(ir, anchor_tables: Iterable[str], *,
                   max_extra: int = 4, max_hops: int = 4) -> tuple[list[str], list[list[str]]]:
    """Add bridge tables connecting all pairs of anchors via shortest path.

    Returns (expanded_set, list_of_paths_used). Caps the number of
    extra tables added so we don't re-introduce the full schema.
    """
    anchors = sorted({t.lower() for t in anchor_tables})
    if len(anchors) <= 1:
        return anchors, []
    extras: list[str] = []
    paths_used: list[list[str]] = []
    for i, a in enumerate(anchors):
        for b in anchors[i+1:]:
            p = shortest_path(ir, a, b, max_hops=max_hops)
            if p is None: continue
            paths_used.append(p)
            for t in p:
                if t not in anchors and t not in extras:
                    extras.append(t)
                if len(extras) >= max_extra: break
            if len(extras) >= max_extra: break
        if len(extras) >= max_extra: break
    return anchors + extras, paths_used


def fk_neighbours(ir, table: str, *, max_hops: int = 1) -> list[str]:
    """Return tables within `max_hops` from `table` over FK edges."""
    adj = _build_adjacency(ir)
    visited = {table.lower(): 0}
    q = deque([(table.lower(), 0)])
    while q:
        cur, d = q.popleft()
        if d >= max_hops: continue
        for (nb, *_rest) in adj.get(cur, []):
            if nb not in visited:
                visited[nb] = d + 1; q.append((nb, d + 1))
    visited.pop(table.lower(), None)
    return sorted(visited.keys())
