"""
Export to Excalidraw JSON format.

Converts a :class:`~diagramatic.core.DiagramSpec` (after layout has
assigned positions) into a valid ``.excalidraw`` JSON file, ready to
render in Obsidian or excalidraw.com.

Also provides the inverse — parsing an existing ``.excalidraw`` file
back into a ``DiagramSpec`` for re-layout or modification.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from diagramatic.core.canvas_models import Canvas, Edge as CanvasEdge, TextNode, Node

from diagramatic.core import (
    DiagramSpec,
    Direction,
    LayoutEdge,
    LayoutNode,
    SemanticColor,
    Shape,
)


# ─── Semantic color palette (matches excalidraw-diagram-skill) ─────

COLOR_PALETTE: dict[SemanticColor, dict[str, str]] = {
    "primary":   {"fill": "#d0ebff", "stroke": "#1971c2"},
    "secondary": {"fill": "#e8daf5", "stroke": "#6741d9"},
    "start":     {"fill": "#fed7aa", "stroke": "#c2410c"},
    "success":   {"fill": "#a7f3d0", "stroke": "#047857"},
    "warning":   {"fill": "#fee2e2", "stroke": "#dc2626"},
    "decision":  {"fill": "#fef3c7", "stroke": "#b45309"},
    "ai":        {"fill": "#ddd6fe", "stroke": "#6d28d9"},
    "disabled":  {"fill": "#dbeafe", "stroke": "#1e40af"},
    "error":     {"fill": "#fecaca", "stroke": "#b91c1c"},
}


def _uid() -> str:
    return uuid.uuid4().hex[:20]


def _el(**kw: Any) -> dict:
    d = {
        "type": "rectangle",
        "version": 1, "versionNonce": 1, "isDeleted": False,
        "fillStyle": "solid", "strokeWidth": 2, "strokeStyle": "solid",
        "roughness": 0, "opacity": 100, "angle": 0,
        "groupIds": [], "frameId": None, "roundness": {"type": 3},
        "seed": 1000, "boundElements": None, "updated": 1,
        "link": None, "locked": False,
    }
    d.update(kw)
    d["id"] = _uid()
    return d


def _shape_element(
    ln: LayoutNode,
    x: float,
    y: float,
) -> dict:
    """Create the shape element for a LayoutNode."""
    palette = COLOR_PALETTE.get(ln.color, COLOR_PALETTE["primary"])

    shape = ln.shape or "rect"
    if shape == "ellipse":
        e = _el(type="ellipse", x=x, y=y, width=ln.width, height=ln.height,
                strokeColor=palette["stroke"], backgroundColor=palette["fill"],
                strokeWidth=2)
    elif shape == "diamond":
        e = _el(type="diamond", x=x, y=y, width=ln.width, height=ln.height,
                strokeColor=palette["stroke"], backgroundColor=palette["fill"],
                strokeWidth=2)
    elif shape == "cylinder":
        # 3-part cylinder: ellipse lid + rectangle body + bottom curve
        cyl_top = 16
        cyl_h = ln.height - cyl_top
        gid = _uid()
        lid = _el(type="ellipse", x=x, y=y, width=ln.width, height=cyl_top,
                  strokeColor=palette["stroke"], backgroundColor=palette["fill"],
                  strokeWidth=2, groupIds=[gid])
        body = _el(type="rectangle", x=x, y=y + cyl_top // 2,
                   width=ln.width, height=cyl_h,
                   strokeColor=palette["stroke"], backgroundColor=palette["fill"],
                   strokeWidth=2, groupIds=[gid], roundness={"type": 3})
        bot = _el(type="ellipse", x=x, y=y + cyl_h + cyl_top // 2 - 2,
                  width=ln.width, height=cyl_top // 2,
                  strokeColor=palette["stroke"], backgroundColor=palette["fill"],
                  strokeWidth=2, groupIds=[gid])
        # Store the group for later reference — we return the body as primary
        # but all three are rendered
        return [lid, body, bot]
    else:
        # rectangle
        e = _el(type="rectangle", x=x, y=y, width=ln.width, height=ln.height,
                strokeColor=palette["stroke"], backgroundColor=palette["fill"],
                strokeWidth=2, roundness={"type": 4})

    return e


def _text_element(
    ln: LayoutNode,
    x: float,
    y: float,
    container_id: str | None = None,
) -> dict:
    """Create a text element centered in the node's box."""
    palette = COLOR_PALETTE.get(ln.color, COLOR_PALETTE["primary"])
    on_dark = palette["stroke"] in ("#047857", "#c2410c", "#dc2626", "#b45309", "#1e40af", "#6d28d9")
    text_color = "#ffffff" if on_dark else "#374151"

    # Estimate text dimensions for the text element itself
    lines = ln.label.split("\n")
    max_chars = max(len(l) for l in lines) if lines else 1
    num_lines = len(lines) if lines else 1
    font_size = 12 if num_lines > 2 else (13 if num_lines > 1 else 14)

    text_w = min(max_chars * font_size * 0.55, ln.width - 20)
    text_h = min(num_lines * font_size * 1.35, ln.height - 16)

    # Center inside the box
    tx = x + (ln.width - text_w) / 2
    ty = y + (ln.height - text_h) / 2

    return _el(type="text", x=tx, y=ty, width=text_w, height=text_h,
               strokeColor=text_color, backgroundColor="transparent",
               text=ln.label, fontSize=font_size, fontFamily=3,
               textAlign="center", verticalAlign="middle",
               containerId=container_id, originalText=ln.label,
               lineHeight=1.25, roundness=None)


def _arrow_element(
    from_x: float, from_y: float,
    to_x: float, to_y: float,
    from_w: float, from_h: float,
    to_w: float, to_h: float,
    color: str = "#495057",
    label: str | None = None,
) -> list[dict]:
    """Create an arrow between two boxes with orthogonal routing."""
    # Compute centers
    fcx = from_x + from_w / 2
    fcy = from_y + from_h / 2
    tcx = to_x + to_w / 2
    tcy = to_y + to_h / 2

    dx = tcx - fcx
    dy = tcy - fcy

    # Choose exit/entry sides based on relative positions
    if abs(dx) > abs(dy):
        # Horizontal dominant — exit right, enter left (or vice versa)
        from_side = "right" if dx > 0 else "left"
        to_side = "left" if dx > 0 else "right"
        if from_side == "right":
            fx, fy = from_x + from_w, fcy
            tx_, ty_ = to_x, tcy
            pts = [[tx_ - fx, ty_ - fy]]
        else:
            fx, fy = from_x, fcy
            tx_, ty_ = to_x + to_w, tcy
            pts = [[tx_ - fx, ty_ - fy]]
    else:
        # Vertical dominant — exit bottom, enter top (or vice versa)
        from_side = "bottom" if dy > 0 else "top"
        to_side = "top" if dy > 0 else "bottom"
        if from_side == "bottom":
            fx, fy = fcx, from_y + from_h
            tx_, ty_ = tcx, to_y
            pts = [[tx_ - fx, ty_ - fy]]
        else:
            fx, fy = fcx, from_y
            tx_, ty_ = tcx, to_y + to_h
            pts = [[tx_ - fx, ty_ - fy]]

    elems = [
        _el(type="arrow", x=fx, y=fy,
            width=abs(tx_ - fx) or 1, height=abs(ty_ - fy) or 1,
            strokeColor=color, backgroundColor="transparent",
            strokeWidth=1.5, roughness=0, roundness={"type": 2},
            points=[[0, 0]] + pts,
            startBinding=None, endBinding=None,
            startArrowhead=None, endArrowhead="arrow")
    ]

    if label:
        mx = fx + (tx_ - fx) / 2 - 30
        my = fy + (ty_ - fy) / 2 - 18
        elems.append(
            _el(type="text", x=mx, y=my, width=60, height=20,
                strokeColor="#868e96", backgroundColor="transparent",
                text=label, fontSize=11, fontFamily=3,
                textAlign="center", verticalAlign="middle",
                containerId=None, originalText=label,
                lineHeight=1.25, roundness=None)
        )

    return elems


def to_excalidraw(
    spec: DiagramSpec,
    positioned_nodes: list[LayoutNode],
    output_path: str | Path | None = None,
) -> dict:
    """Generate a complete ``.excalidraw`` JSON document.

    Args:
        spec:              The diagram specification.
        positioned_nodes:  Nodes with positions from a layout engine.
        output_path:       Optional file path to write the JSON to.

    Returns:
        The Excalidraw JSON dict (writable to ``.excalidraw`` files).
    """
    elements: list[dict] = []

    # Build node map for quick lookup
    node_map = {n.id: n for n in positioned_nodes}

    # Shape ID mapping for arrow binding
    shape_ids: dict[str, list[str]] = {}

    # 1. Add layer background elements if layers are defined
    if spec.layers:
        layer_nodes: dict[str, list[LayoutNode]] = {}
        for n in positioned_nodes:
            layer_nodes.setdefault(n.layer or "_default", []).append(n)

        for layer_name in spec.layers:
            nodes_in_layer = layer_nodes.get(layer_name, [])
            if not nodes_in_layer:
                continue
            xs = [n.x for n in nodes_in_layer]
            ys = [n.y for n in nodes_in_layer]
            x2s = [n.x + n.width for n in nodes_in_layer]
            y2s = [n.y + n.height for n in nodes_in_layer]
            min_x, min_y = min(xs), min(ys)
            max_x2, max_y2 = max(x2s), max(y2s)

            bg = _el(type="rectangle",
                     x=min_x - 20, y=min_y - 25,
                     width=max_x2 - min_x + 40,
                     height=max_y2 - min_y + 45,
                     strokeColor="#dee2e6", backgroundColor="#f8f9fa",
                     strokeWidth=0.5,
                     roundness={"type": 3})
            bg["opacity"] = 30
            elements.append(bg)

            # Layer label
            lbl = _el(type="text", x=min_x, y=min_y - 22,
                      width=300, height=18,
                      strokeColor="#adb5bd", backgroundColor="transparent",
                      text=f"──  {layer_name}  ──",
                      fontSize=12, fontFamily=3,
                      textAlign="left", verticalAlign="top",
                      containerId=None, originalText=f"──  {layer_name}  ──",
                      lineHeight=1.25, roundness=None)
            elements.append(lbl)

    # 2. Add shape elements
    for ln in positioned_nodes:
        shape_el = _shape_element(ln, ln.x, ln.y)
        if isinstance(shape_el, list):
            # Cylinder — returns multiple elements
            shape_ids[ln.id] = [e["id"] for e in shape_el]
            elements.extend(shape_el)
            # Text goes inside the body (2nd element)
            container = shape_el[1]["id"]
        else:
            shape_ids[ln.id] = [shape_el["id"]]
            elements.append(shape_el)
            container = shape_el["id"]

        # Text
        te = _text_element(ln, ln.x, ln.y, container)
        elements.append(te)

        # Bind
        for sid in shape_ids[ln.id]:
            shape_el_obj = next(e for e in elements if e["id"] == sid)
            if shape_el_obj.get("boundElements") is None:
                shape_el_obj["boundElements"] = []
            shape_el_obj["boundElements"].append({"id": te["id"], "type": "text"})

    # 3. Add edges
    for le in spec.edges:
        from_ln = node_map.get(le.from_id)
        to_ln = node_map.get(le.to_id)
        if not from_ln or not to_ln:
            continue

        fids = shape_ids.get(le.from_id, [])
        tids = shape_ids.get(le.to_id, [])
        if not fids or not tids:
            continue

        # Use first shape ID for each (primary shape)
        from_sid = fids[0] if len(fids) == 1 or ln.shape != "cylinder" else fids[1]
        to_sid = tids[0] if len(tids) == 1 or ln.shape != "cylinder" else tids[1]

        arrow_elems = _arrow_element(
            from_ln.x, from_ln.y, to_ln.x, to_ln.y,
            from_ln.width, from_ln.height,
            to_ln.width, to_ln.height,
            label=le.label,
        )
        elements.extend(arrow_elems)

    # 4. Build scene
    scene = {
        "type": "excalidraw",
        "version": 2,
        "source": "https://excalidraw.com",
        "elements": elements,
        "appState": {
            "gridSize": 20,
            "viewBackgroundColor": "#ffffff",
        },
        "files": {},
    }

    # 5. Optionally write to disk
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(scene, indent=2))

    return scene


def parse_excalidraw(file_path: str | Path) -> dict:
    """Parse an existing ``.excalidraw`` file.

    Returns the raw JSON data.  Use together with
    :func:`diagramatic.validation.validate_diagram` to check quality.

    Args:
        file_path: Path to an ``.excalidraw`` file.

    Returns:
        The parsed Excalidraw JSON dict.
    """
    return json.loads(Path(file_path).read_text(encoding="utf-8"))