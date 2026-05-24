"""
diagramatic — Agent-friendly diagram toolkit.

Auto-layout, validation, and export for Excalidraw + JSON Canvas.
Built for AI agents that need to generate correct diagrams every time.
"""

from .core import (
    Canvas, DiagramSpec, Direction, Edge,
    LayoutEdge, LayoutNode, Node, SemanticColor, Shape,
)

__all__ = [
    "DiagramSpec",
    "LayoutNode",
    "LayoutEdge",
    "Direction",
    "Shape",
    "SemanticColor",
    "Node",
    "Edge",
    "Canvas",
]

__version__ = "0.1.0"