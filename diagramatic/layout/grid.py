"""
Content-aware grid layout engine.

Places nodes on a row/column grid where each grid cell is sized to fit
the largest node in that row/column.  No external dependencies — pure
Python layout that always produces correct, non-overlapping positions.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from diagramatic.core import DiagramSpec, LayoutNode, Direction


def grid_layout(
    spec: DiagramSpec,
    *,
    layer_gap: float = 80,
    node_gap: float = 50,
    padding: float = 40,
) -> list[LayoutNode]:
    """Place nodes on a layer-aware grid.

    Each unique ``layer`` string gets its own row (or column, depending
    on direction).  Within each layer, nodes are evenly spaced.  All
    cells are sized to fit the largest node in that row/column.

    Args:
        spec:        The diagram specification.
        layer_gap:   Vertical (TB) or horizontal (LR) gap between layers.
        node_gap:    Gap between nodes within the same layer.
        padding:     Initial offset from the canvas edge.

    Returns:
        A new list of :class:`LayoutNode` with ``x``, ``y`` set.
    """
    direction = spec.direction
    is_horizontal = direction in ("LR", "RL")

    # Group nodes by layer
    layers: Dict[str, list[LayoutNode]] = {}
    for node in spec.nodes:
        layer_name = node.layer or "_default"
        layers.setdefault(layer_name, []).append(node)

    # Use spec.layers for ordering, fall back to insertion order
    ordered_layers = spec.layers or list(layers.keys())
    if "_default" in layers and "_default" not in ordered_layers:
        ordered_layers.append("_default")

    positioned: list[LayoutNode] = []

    if is_horizontal:
        x = padding
        for layer_name in ordered_layers:
            layer_nodes = layers.get(layer_name, [])
            if not layer_nodes:
                continue

            # Compute column width from widest node
            col_width = max(n.width for n in layer_nodes)
            total_height = sum(n.height for n in layer_nodes) + node_gap * (len(layer_nodes) - 1)
            y_start = padding

            if direction == "RL":
                # Right-to-left: reverse x direction (handled later)
                pass

            # Place nodes stacked vertically within this layer
            y = y_start
            for node in layer_nodes:
                # Create a copy with position set
                pn = LayoutNode(
                    id=node.id,
                    label=node.label,
                    layer=node.layer,
                    shape=node.shape,
                    color=node.color,
                    width=node.width,
                    height=node.height,
                    x=x,
                    y=y,
                    fixed=node.fixed,
                    node=node.node,
                )
                positioned.append(pn)
                y += node.height + node_gap

            x += col_width + layer_gap
    else:
        # TB or BT — layers are rows
        y = padding
        for layer_name in ordered_layers:
            layer_nodes = layers.get(layer_name, [])
            if not layer_nodes:
                continue

            # Compute row height from tallest node
            row_height = max(n.height for n in layer_nodes)
            total_width = sum(n.width for n in layer_nodes) + node_gap * (len(layer_nodes) - 1)
            x_start = padding

            if direction == "BT":
                # Bottom-to-top: will reverse after
                pass

            # Place nodes laid out horizontally within this row
            x = x_start
            for node in layer_nodes:
                pn = LayoutNode(
                    id=node.id,
                    label=node.label,
                    layer=node.layer,
                    shape=node.shape,
                    color=node.color,
                    width=node.width,
                    height=node.height,
                    x=x,
                    y=y,
                    fixed=node.fixed,
                    node=node.node,
                )
                positioned.append(pn)
                x += node.width + node_gap

            y += row_height + layer_gap

    # Handle reverse directions (RL, BT) by flipping coordinates
    if direction == "RL" and positioned:
        max_x = max(n.x + n.width for n in positioned)
        for n in positioned:
            n.x = max_x - n.x - n.width

    if direction == "BT" and positioned:
        max_y = max(n.y + n.height for n in positioned)
        for n in positioned:
            n.y = max_y - n.y - n.height

    return positioned