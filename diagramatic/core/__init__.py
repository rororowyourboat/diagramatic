"""
Extended data models for diagrammatic layout and validation.

Builds on ``canvas_parser.models`` — re-exporting all base types and adding
layout-specific fields for auto-positioning, styling, and quality checks.
"""

from .canvas_models import (
    Canvas,
    Edge,
    FileNode,
    GroupNode,
    LinkNode,
    Node,
    TextNode,
)

# Re-export everything so consumers only need ``from diagramatic.core import ...``
__all__ = [
    "Canvas",
    "Edge",
    "FileNode",
    "GroupNode",
    "LinkNode",
    "Node",
    "TextNode",
    "LayoutNode",
    "DiagramSpec",
    "Direction",
    "Shape",
    "SemanticColor",
]

# ── Layout-specific types ──────────────────────────────────────────

from dataclasses import dataclass, field
from typing import Literal

Direction = Literal["TB", "BT", "LR", "RL"]
Shape = Literal["rect", "ellipse", "diamond", "cylinder"]
SemanticColor = Literal[
    "primary", "secondary", "start", "success", "warning",
    "decision", "ai", "disabled", "error",
]


@dataclass
class LayoutNode:
    """A node tagged with layout and styling metadata.

    Wraps a :class:`Node` with the extra information
    needed for auto-layout and Excalidraw generation.

    Attributes:
        id:             Node identifier (matches ``node.id``).
        label:          Display text.
        layer:          Logical layer / tier (e.g. ``"Frontend"``, ``"Data"``).
        shape:          Visual shape for Excalidraw export.
        color:          Semantic color key.
        width:          Computed content-aware width in pixels.
        height:         Computed content-aware height in pixels.
        x:              X position after layout.
        y:              Y position after layout.
        fixed:          If True, auto-layout will not move this node.
        node:           Optional reference to the original Node.
    """

    id: str
    label: str
    layer: str | None = None
    shape: Shape = "rect"
    color: SemanticColor = "primary"
    width: float = 200
    height: float = 80
    x: float = 0
    y: float = 0
    fixed: bool = False
    node: Node | None = None


@dataclass
class LayoutEdge:
    """A directed edge between layout nodes.

    Attributes:
        id:        Edge identifier.
        from_id:   Source node ID.
        to_id:     Target node ID.
        label:     Optional edge label.
    """

    id: str = ""
    from_id: str = ""
    to_id: str = ""
    label: str | None = None


@dataclass
class DiagramSpec:
    """Complete structured diagram specification — the input to diagramatic.

    This is the primary input format for auto-layout.  Convert YAML / JSON /
    ``.canvas`` files into this, then pass to any layout engine.

    Attributes:
        title:      Diagram title.
        direction:  Layout direction (``"TB"``, ``"LR"``, etc.).
        nodes:      List of :class:`LayoutNode` definitions.
        edges:      List of :class:`LayoutEdge` definitions.
        layers:     Ordered list of layer names (controls rendering order).
    """

    title: str = ""
    direction: Direction = "TB"
    nodes: list[LayoutNode] = field(default_factory=list)
    edges: list[LayoutEdge] = field(default_factory=list)
    layers: list[str] = field(default_factory=list)