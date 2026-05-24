# diagramatic

Agent-friendly diagram toolkit — auto-layout, validation, Excalidraw export, and reusable library icons/components.

## What it does

- **Auto-layout** (dagre or pure-Python grid)
- **Validate** diagrams (overlaps, text overflow, dangling arrows)
- **Render** to PNG for visual checks
- **Use Excalidraw libraries** for architecture components and icons
- **Export** to `.excalidraw`

## Quick start

```bash
diagramatic layout examples/video-streaming.yaml -o diagram.excalidraw --check
diagramatic validate diagram.excalidraw
diagramatic render diagram.excalidraw
diagramatic fix diagram.excalidraw
```

## Libraries

```bash
diagramatic libraries
# or
 diagramatic libraries -l arch
```

Available built-in libraries (loaded from your Downloads folder):

- `arch` — architecture-diagram-components
- `system-design` — system-design
- `viz` — data-viz
- `icons` — awesome-icons

## Example

See `examples/video-streaming.yaml` for a Twitch-like architecture spec with semantic icons.
