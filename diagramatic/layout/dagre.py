"""
Dagre auto-layout via Node.js subprocess bridge.

Calls ``dagre`` through a one-shot Node.js process that reads node/edge
definitions from stdin and writes positioned output to stdout.  This
keeps all the complex graph-layout math in dagre while the entire rest
of diagramatic stays in Python.

Requires Node.js and ``dagre`` to be installed::

    npm install dagre
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

from diagramatic.core import DiagramSpec, Direction, LayoutNode

# ── Template for the one-shot Node.js script ──────────────────────

_DAGRE_SCRIPT = r"""
const dagre = require('dagre');
const input = JSON.parse(require('fs').readFileSync('/dev/stdin', 'utf-8'));

const g = new dagre.graphlib.Graph();
g.setGraph({
  rankdir: input.direction || 'TB',
  nodesep: input.nodesep || 80,
  ranksep: input.ranksep || 120,
  edgesep: input.edgesep || 20,
  marginx: input.margin || 40,
  marginy: input.margin || 40,
});
g.setDefaultEdgeLabel(function() { return {}; });

for (const n of input.nodes) {
  // Clamp to minimum dagre size
  const w = Math.max(n.width || 100, 40);
  const h = Math.max(n.height || 50, 30);
  g.setNode(n.id, { width: w, height: h, originalWidth: w, originalHeight: h });
}

for (const e of input.edges) {
  g.setEdge(e.from_id, e.to_id, { label: e.label || '' });
}

dagre.layout(g);

const result = [];
for (const n of input.nodes) {
  const pos = g.node(n.id);
  if (pos) {
    // dagre gives center coordinates; convert to top-left for Excalidraw
    const w = pos.originalWidth || n.width || 100;
    const h = pos.originalHeight || n.height || 50;
    result.push({
      id: n.id,
      x: pos.x - w / 2,
      y: pos.y - h / 2,
      width: w,
      height: h,
    });
  }
}
console.log(JSON.stringify(result));
"""


def _check_dagre_available() -> bool:
    """Check whether dagre is installed and importable by Node.js."""
    try:
        result = subprocess.run(
            ["node", "-e", "require('dagre'); console.log('ok')"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0 and "ok" in result.stdout
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def dagre_layout(
    spec: DiagramSpec,
    *,
    nodesep: float = 80,
    ranksep: float = 120,
    edgesep: float = 20,
    margin: float = 40,
    require_installed: bool = False,
) -> list[LayoutNode]:
    """Run dagre layout via Node.js subprocess.

    Args:
        spec:               The diagram specification.
        nodesep:            Minimum separation between nodes in the same rank.
        ranksep:            Minimum separation between ranks (layers).
        edgesep:            Minimum separation between edges.
        margin:             Canvas margin in pixels.
        require_installed:  If True, raises ``RuntimeError`` when dagre is
                            not available.  If False, falls back to grid layout.

    Returns:
        List of :class:`LayoutNode` with positions set.

    Raises:
        RuntimeError: If ``require_installed=True`` and dagre/Node.js is
                      not found, or if the dagre process fails.
    """
    if not _check_dagre_available():
        if require_installed:
            raise RuntimeError(
                "dagre is not available. Install it with: npm install dagre"
            )
        # Fall back to grid layout
        from .grid import grid_layout
        return grid_layout(spec, layer_gap=ranksep, node_gap=nodesep)

    # Build input
    dagre_nodes = []
    for ln in spec.nodes:
        dagre_nodes.append({
            "id": ln.id,
            "width": ln.width,
            "height": ln.height,
        })

    dagre_edges = []
    for le in spec.edges:
        dagre_edges.append({
            "from_id": le.from_id,
            "to_id": le.to_id,
            "label": le.label,
        })

    input_data = json.dumps({
        "nodes": dagre_nodes,
        "edges": dagre_edges,
        "direction": spec.direction,
        "nodesep": nodesep,
        "ranksep": ranksep,
        "edgesep": edgesep,
        "margin": margin,
    })

    try:
        result = subprocess.run(
            ["node", "-e", _DAGRE_SCRIPT],
            input=input_data,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        raise RuntimeError("Node.js is not installed or not in PATH")
    except subprocess.TimeoutExpired:
        raise RuntimeError("dagre layout timed out after 30s")

    if result.returncode != 0:
        raise RuntimeError(f"dagre process failed: {result.stderr}")

    try:
        positions = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"dagre returned invalid JSON: {result.stdout[:200]}")

    # Merge positions back into LayoutNodes
    pos_map = {p["id"]: p for p in positions}
    output: list[LayoutNode] = []
    for ln in spec.nodes:
        pos = pos_map.get(ln.id, {})
        output.append(
            LayoutNode(
                id=ln.id,
                label=ln.label,
                layer=ln.layer,
                shape=ln.shape,
                color=ln.color,
                width=pos.get("width", ln.width),
                height=pos.get("height", ln.height),
                x=pos.get("x", 0),
                y=pos.get("y", 0),
                fixed=ln.fixed,
                node=ln.node,
            )
        )

    return output