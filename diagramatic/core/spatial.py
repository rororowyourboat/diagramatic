"""
Spatial collision detection and resolution.

Builds on ``spatial_utils.group_children`` for containment queries and adds
overlap detection, overlap resolution (push-apart), and bounding-box utilities
for use in validation and layout fixing.
"""

from __future__ import annotations

from typing import List, Tuple

from .spatial_utils import group_children as _group_children
from .canvas_models import GroupNode, Node

# Re-export from spatial_utils
group_children = _group_children


# ── Bounding-box helpers ───────────────────────────────────────────

BBox = Tuple[float, float, float, float]  # (x, y, x2, y2)


def bbox(x: float, y: float, w: float, h: float) -> BBox:
    """Return the bounding-box ``(x1, y1, x2, y2)`` for a rectangle."""
    return (x, y, x + abs(w), y + abs(h))


def bbox_overlap(a: BBox, b: BBox) -> bool:
    """Return True if two bounding boxes overlap (including touching)."""
    return not (a[2] <= b[0] or a[0] >= b[2] or a[3] <= b[1] or a[1] >= b[3])


def bbox_contains(outer: BBox, inner: BBox) -> bool:
    """Return True if *outer* fully contains *inner*."""
    return (
        outer[0] <= inner[0]
        and outer[1] <= inner[1]
        and outer[2] >= inner[2]
        and outer[3] >= inner[3]
    )


def bounding_box_all(elements: list[dict]) -> BBox:
    """Compute the bounding box across a list of element-like dicts
    with ``x``, ``y``, ``width``, ``height`` keys."""
    xs = [e["x"] for e in elements]
    ys = [e["y"] for e in elements]
    x2s = [e["x"] + abs(e.get("width", 0)) for e in elements]
    y2s = [e["y"] + abs(e.get("height", 0)) for e in elements]
    return (min(xs), min(ys), max(x2s), max(y2s))


# ── Collision detection ────────────────────────────────────────────


def detect_overlaps(
    elements: list[dict],
    *,
    exclude_types: set[str] | None = None,
    padding: float = 0,
) -> list[tuple[dict, dict, float]]:
    """Find all overlapping pairs among *elements*.

    Skips:
    - Elements in ``exclude_types`` (default: none).
    - Elements with ``opacity < 80`` (background/decorative).
    - Elements that share a ``groupIds`` entry (composite shapes).
    - Text elements and their own ``containerId`` parent.

    Args:
        elements:      List of element-like dicts.
        exclude_types: Element types to skip (e.g. ``{"arrow", "line"}``).
        padding:       Minimum separation between elements in pixels.

    Returns:
        List of ``(elem_a, elem_b, overlap_distance)`` tuples.
    """
    exclude = exclude_types or set()
    results: list[tuple[dict, dict, float]] = []
    n = len(elements)

    # Track group siblings so we don't flag composite-part overlaps
    def _same_group(a: dict, b: dict) -> bool:
        return bool(set(a.get("groupIds", [])) & set(b.get("groupIds", [])))

    # Track text → containerId relationships
    text_container: dict[str, str] = {}
    for e in elements:
        if e.get("type") == "text" and e.get("containerId"):
            text_container[e["id"]] = e["containerId"]

    # Skip low-opacity backgrounds
    low_opacity: set[str] = {e["id"] for e in elements if e.get("opacity", 100) < 80}

    for i in range(n):
        a = elements[i]
        if a.get("type") in exclude or a["id"] in low_opacity:
            continue
        box_a = bbox(a["x"], a["y"], a.get("width", 0), a.get("height", 0))

        for j in range(i + 1, n):
            b = elements[j]
            if b.get("type") in exclude or b["id"] in low_opacity:
                continue
            if _same_group(a, b):
                continue
            # Text vs its own container — by design
            if a.get("type") == "text" and text_container.get(a["id"]) == b.get("id"):
                continue
            if b.get("type") == "text" and text_container.get(b["id"]) == a.get("id"):
                continue

            box_b = bbox(b["x"], b["y"], b.get("width", 0), b.get("height", 0))

            if bbox_overlap(box_a, box_b):
                dx = min(box_a[2] - box_b[0], box_b[2] - box_a[0])
                dy = min(box_a[3] - box_b[1], box_b[3] - box_a[1])
                overlap = min(dx, dy)
                if overlap > -padding:
                    results.append((a, b, overlap))

    return results


# ── Collision resolution ──────────────────────────────────────────


def resolve_overlaps(
    elements: list[dict],
    *,
    exclude_types: set[str] | None = None,
    padding: float = 20,
    max_iterations: int = 10,
) -> list[dict]:
    """Push overlapping elements apart iteratively.

    Mutates and returns the *elements* list in place.

    Args:
        elements:       List of element-like dicts with ``x``, ``y``.
        exclude_types:  Types to skip.
        padding:        Target minimum separation.
        max_iterations: How many push-apart passes to run.

    Returns:
        The same *elements* list (mutated in place).
    """
    exclude = exclude_types or set()
    low_opacity: set[str] = {e["id"] for e in elements if e.get("opacity", 100) < 80}

    for _ in range(max_iterations):
        pairs = detect_overlaps(elements, exclude_types=exclude, padding=padding)
        if not pairs:
            break

        for a, b, _ in pairs:
            if a.get("type") in exclude or b.get("type") in exclude:
                continue
            if a["id"] in low_opacity or b["id"] in low_opacity:
                continue
            ax = a["x"] + a.get("width", 0) / 2
            ay = a["y"] + a.get("height", 0) / 2
            bx = b["x"] + b.get("width", 0) / 2
            by = b["y"] + b.get("height", 0) / 2

            dx = bx - ax
            dy = by - ay
            dist = max((dx * dx + dy * dy) ** 0.5, 1)

            push = padding / dist
            a["x"] -= dx * push * 0.5
            a["y"] -= dy * push * 0.5
            b["x"] += dx * push * 0.5
            b["y"] += dy * push * 0.5

    return elements


# ── Text overflow detection ───────────────────────────────────────


def detect_text_overflow(elements: list[dict]) -> list[tuple[dict, str]]:
    """Find text elements whose text extends beyond their container.

    Only checks text elements that have a ``containerId`` — i.e. text
    bound to a shape.

    Returns:
        List of ``(text_element, container_id)`` pairs where text overflows.
    """
    from .sizing import fit_text_to_box

    containers = {e["id"]: e for e in elements
                  if e.get("type") in ("rectangle", "ellipse", "diamond")}
    results: list[tuple[dict, str]] = []

    for te in elements:
        if te.get("type") != "text":
            continue
        cid = te.get("containerId")
        if not cid or cid not in containers:
            continue
        c = containers[cid]
        fits = fit_text_to_box(
            te.get("text", ""),
            c.get("width", 0),
            c.get("height", 0),
            font_size=te.get("fontSize", 14),
        )
        if not fits:
            results.append((te, cid))

    return results


# ── Dangling arrow detection ──────────────────────────────────────


def detect_dangling_arrows(elements: list[dict]) -> list[dict]:
    """Find arrows whose source/target elements don't exist.

    Checks ``startBinding.elementId`` and ``endBinding.elementId``
    against all non-arrow/line element IDs.

    Returns:
        List of arrow elements with dangling references.
    """
    shape_ids = {
        e["id"]
        for e in elements
        if e.get("type") not in ("arrow", "line", "text")
    }
    arrows = [e for e in elements if e.get("type") == "arrow"]
    dangling: list[dict] = []

    for a in arrows:
        sb = a.get("startBinding") or {}
        eb = a.get("endBinding") or {}
        sid = sb.get("elementId")
        eid = eb.get("elementId")
        if (sid and sid not in shape_ids) or (eid and eid not in shape_ids):
            dangling.append(a)

    return dangling