"""
CLI entry point for diagramatic.

Usage::

    diagramatic layout <input.yaml>           # Auto-layout to .excalidraw
    diagramatic validate <diagram.excalidraw>  # Quality check
    diagramatic render  <diagram.excalidraw>   # Render to PNG
    diagramatic fix     <diagram.excalidraw>   # Auto-fix issues
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from diagramatic.core import DiagramSpec, LayoutEdge, LayoutNode
from diagramatic.export.excalidraw import parse_excalidraw, to_excalidraw
from diagramatic.layout.dagre import dagre_layout
from diagramatic.layout.grid import grid_layout


def _load_spec(input_path: str) -> DiagramSpec:
    """Load a DiagramSpec from a YAML or JSON file."""
    import yaml

    path = Path(input_path)
    raw = path.read_text(encoding="utf-8")

    if path.suffix in (".yaml", ".yml"):
        data = yaml.safe_load(raw)
    elif path.suffix == ".json":
        data = json.loads(raw)
    else:
        # Try JSON first, then YAML
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = yaml.safe_load(raw)

    # Build LayoutNodes
    nodes = []
    for nd in data.get("nodes", []):
        nodes.append(LayoutNode(
            id=nd.get("id", str(hash(nd.get("label", "")))),
            label=nd.get("label", ""),
            layer=nd.get("layer"),
            shape=nd.get("shape", "rect"),
            color=nd.get("color", "primary"),
            width=nd.get("width", 200),
            height=nd.get("height", 80),
            fixed=nd.get("fixed", False),
        ))

    # Build LayoutEdges
    edges = []
    for ed in data.get("edges", []):
        edges.append(LayoutEdge(
            id=ed.get("id", ""),
            from_id=ed.get("from", ed.get("from_id", "")),
            to_id=ed.get("to", ed.get("to_id", "")),
            label=ed.get("label"),
        ))

    return DiagramSpec(
        title=data.get("title", ""),
        direction=data.get("direction", "TB"),
        nodes=nodes,
        edges=edges,
        layers=data.get("layers", []),
    )


def cmd_layout(args: argparse.Namespace) -> int:
    """Run auto-layout on a specification file."""
    spec = _load_spec(args.input)

    # Auto-size nodes from content if not explicitly sized
    from diagramatic.core.sizing import auto_box_size

    for ln in spec.nodes:
        if not args.no_autosize:
            # Cylinders need extra height for the curved top
            min_h = 90 if ln.shape == "cylinder" else 60
            min_w = 220 if ln.shape == "cylinder" else 160
            # Cylinders use smaller font because they have less internal space
            fs = 11 if ln.shape == "cylinder" else 13
            w, h, _, _ = auto_box_size(ln.label, font_size=fs, min_width=min_w, min_height=min_h)
            ln.width = max(ln.width, w)
            ln.height = max(ln.height, h)

    # Run layout
    layout_fn = dagre_layout if args.layout == "dagre" else grid_layout
    try:
        positioned = layout_fn(spec)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Export
    output_path = args.output or Path(args.input).with_suffix(".excalidraw")
    scene = to_excalidraw(spec, positioned, output_path=str(output_path))

    # Validate
    if args.check:
        from diagramatic.validation import quality_report
        report = quality_report(scene["elements"])
        print(report)
        print()

    print(f"✅ Wrote {output_path} ({len(scene['elements'])} elements)")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate an existing .excalidraw file."""
    data = parse_excalidraw(args.input)
    elements = data.get("elements", [])

    from diagramatic.validation import quality_report
    report = quality_report(elements)
    print(report)
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    """Render an .excalidraw file to PNG using Playwright."""
    try:
        from diagramatic.render.pipeline import render_to_png
    except ImportError:
        print("Error: playwright not installed.", file=sys.stderr)
        print("Install with: cd /home/rohan/.agents/skills/excalidraw-diagram/references && uv sync", file=sys.stderr)
        return 1

    try:
        png_path = render_to_png(Path(args.input), scale=args.scale)
        print(f"✅ Rendered {png_path}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_fix(args: argparse.Namespace) -> int:
    """Auto-fix common issues in an .excalidraw file."""
    data = parse_excalidraw(args.input)
    elements = data.get("elements", [])

    from diagramatic.validation import validate_diagram, score_diagram
    from diagramatic.core.spatial import resolve_overlaps

    # Fix overlaps
    fixed = resolve_overlaps(elements, padding=20)
    data["elements"] = fixed

    # Re-score
    score, issues = score_diagram(fixed)
    print(f"Score after fix: {score}/100")
    if issues:
        for iss in issues:
            print(f"  ⚠ [{iss.category}] {iss.message}")

    # Write
    output_path = args.output or args.input
    Path(output_path).write_text(json.dumps(data, indent=2))
    print(f"✅ Fixed and wrote {output_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="diagramatic — agent-friendly diagram toolkit",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # layout
    p_layout = sub.add_parser("layout", help="Auto-layout a diagram spec to .excalidraw")
    p_layout.add_argument("input", help="Input YAML/JSON specification file")
    p_layout.add_argument("-o", "--output", help="Output .excalidraw path")
    p_layout.add_argument("--layout", choices=["dagre", "grid"], default="dagre",
                          help="Layout engine (default: dagre, falls back to grid)")
    p_layout.add_argument("--no-autosize", action="store_true",
                          help="Skip content-aware auto-sizing")
    p_layout.add_argument("--check", action="store_true",
                          help="Validate the output after generation")

    # validate
    p_val = sub.add_parser("validate", help="Validate an .excalidraw file")
    p_val.add_argument("input", help="Path to .excalidraw file")

    # render
    p_render = sub.add_parser("render", help="Render .excalidraw to PNG")
    p_render.add_argument("input", help="Path to .excalidraw file")
    p_render.add_argument("--scale", "-s", type=int, default=2, help="Scale factor")

    # fix
    p_fix = sub.add_parser("fix", help="Auto-fix common diagram issues")
    p_fix.add_argument("input", help="Path to .excalidraw file")
    p_fix.add_argument("-o", "--output", help="Output path (default: overwrite input)")

    args = parser.parse_args()

    commands = {
        "layout": cmd_layout,
        "validate": cmd_validate,
        "render": cmd_render,
        "fix": cmd_fix,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())