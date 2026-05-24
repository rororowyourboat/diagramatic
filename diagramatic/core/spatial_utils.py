"""
Spatial utilities for bounding-box containment.

The JSON Canvas spec lays out nodes on an infinite 2-D plane using
``(x, y, width, height)`` coordinates.  :class:`GroupNode` acts as a visual
container, but the spec does not explicitly track parent–child relationships
— they must be inferred from geometry.

This module provides :func:`group_children`, which performs that spatial
query once so that every converter (Mermaid, D2, …) can share the same
result without re-implementing the collision logic.
"""

from .canvas_models import GroupNode, Node


def group_children(groups: list[GroupNode], nodes: list[Node]) -> dict[str, list[Node]]:
    """Determine which nodes are spatially contained within each group.

    A node is considered a child of a group when it is **fully enclosed**
    within the group's bounding box (i.e. all four corners lie inside).

    Args:
        groups: The :class:`GroupNode` instances to test against.
        nodes:  The candidate child nodes (should exclude ``GroupNode``
                instances to avoid groups containing themselves).

    Returns:
        A dict mapping each ``group.id`` to the list of *nodes* that fall
        inside that group's bounding box.

    Example::

        children_map = group_children(group_nodes, other_nodes)
        for gid, kids in children_map.items():
            print(f"Group {gid} contains {len(kids)} nodes")
    """
    result: dict[str, list[Node]] = {}
    for g in groups:
        g_right = g.x + g.width
        g_bottom = g.y + g.height
        result[g.id] = [
            n
            for n in nodes
            if n.x >= g.x and n.x + n.width <= g_right and n.y >= g.y and n.y + n.height <= g_bottom
        ]
    return result
