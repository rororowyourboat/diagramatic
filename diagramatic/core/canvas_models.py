"""
Data models for the JSON Canvas specification.

This module defines Python dataclasses that mirror the
`JSON Canvas spec <https://jsoncanvas.org/spec/1.0/>`_.  Every model uses
``kw_only=True`` so fields are always passed as keyword arguments, which
keeps construction explicit and forward-compatible.

Hierarchy::

    Node (base — has id, type, x, y, width, height)
    ├── TextNode   — inline markdown / plain text
    ├── FileNode   — reference to a file on disk
    ├── LinkNode   — external URL
    └── GroupNode  — spatial container for other nodes

    Edge           — directed or undirected connection between two Nodes
    Canvas         — top-level container holding nodes + edges
"""

from dataclasses import dataclass, field
from typing import Literal


@dataclass(kw_only=True)
class Node:
    """Base canvas element with spatial coordinates.

    All node types extend this class with additional type-specific fields.

    Attributes:
        id:     Unique identifier (hex string assigned by Obsidian).
        type:   Discriminator — ``"text"``, ``"file"``, ``"link"``, ``"group"``.
        x:      Horizontal pixel offset of the top-left corner.
        y:      Vertical pixel offset of the top-left corner.
        width:  Width in pixels.
        height: Height in pixels.
        color:  Optional colour index string (e.g. ``"1"`` through ``"6"``).
    """

    id: str
    type: str
    x: int
    y: int
    width: int
    height: int
    color: str | None = None


@dataclass(kw_only=True)
class TextNode(Node):
    """A node containing inline text or markdown.

    Attributes:
        text: The raw text / markdown content of the node.
    """

    text: str = ""


@dataclass(kw_only=True)
class FileNode(Node):
    """A node referencing a file on disk.

    Attributes:
        file:    Relative path to the file from the vault root.
        subpath: Optional sub-section within the file (e.g. a heading).
    """

    file: str = ""
    subpath: str | None = None


@dataclass(kw_only=True)
class LinkNode(Node):
    """A node pointing to an external URL.

    Attributes:
        url: The full URL.
    """

    url: str = ""


@dataclass(kw_only=True)
class GroupNode(Node):
    """A spatial container that visually groups other nodes.

    Group membership is determined at conversion time by checking whether
    child nodes fall inside the group's bounding box (see ``_spatial.py``).

    Attributes:
        label:           Display label for the group.
        background:      Optional background image path.
        backgroundStyle: How the background image is rendered.
    """

    label: str | None = None
    background: str | None = None
    backgroundStyle: Literal["cover", "ratio", "repeat"] | None = None


@dataclass(kw_only=True)
class Edge:
    """A connection between two nodes.

    Attributes:
        id:       Unique identifier.
        fromNode: ID of the source node.
        toNode:   ID of the target node.
        fromSide: Which side of the source node the edge departs from.
        fromEnd:  Arrow style at the source end (``"none"`` or ``"arrow"``).
        toSide:   Which side of the target node the edge arrives at.
        toEnd:    Arrow style at the target end (``"none"`` or ``"arrow"``).
        color:    Optional colour index string.
        label:    Optional text label shown on the edge.
    """

    id: str
    fromNode: str
    toNode: str
    fromSide: Literal["top", "right", "bottom", "left"] | None = None
    fromEnd: Literal["none", "arrow"] | None = "none"
    toSide: Literal["top", "right", "bottom", "left"] | None = None
    toEnd: Literal["none", "arrow"] | None = "arrow"
    color: str | None = None
    label: str | None = None


@dataclass(kw_only=True)
class Canvas:
    """Top-level container for a parsed JSON Canvas document.

    Attributes:
        nodes: All nodes in the canvas (may be any ``Node`` subclass).
        edges: All edges connecting nodes.
    """

    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
