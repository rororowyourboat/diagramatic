"""
Render .excalidraw to PNG via Playwright.

Adapted from coleam00's excalidraw-diagram-skill render pipeline.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

RENDER_SCRIPT_DIR = Path(__file__).resolve().parent.parent.parent / "references"

_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { background: #ffffff; overflow: hidden; }
    #root { display: inline-block; }
    #root svg { display: block; }
  </style>
</head>
<body>
  <div id="root"></div>
  <script type="module">
    import { exportToSvg } from "https://esm.sh/@excalidraw/excalidraw@0.18.0";
    window.renderDiagram = async function(jsonData) {
      try {
        const data = typeof jsonData === "string" ? JSON.parse(jsonData) : jsonData;
        const svg = await exportToSvg({
          elements: data.elements || [],
          appState: { ...(data.appState || {}), exportBackground: true },
          files: data.files || {}
        });
        document.getElementById("root").appendChild(svg);
        window.__renderComplete = true;
        return { success: true };
      } catch (err) {
        window.__renderComplete = true;
        return { success: false, error: err.message };
      }
    };
    window.__moduleReady = true;
  </script>
</body>
</html>
"""


def render_to_png(
    excalidraw_path: Path,
    output_path: Optional[Path] = None,
    scale: int = 2,
) -> Path:
    """Render an ``.excalidraw`` file to PNG.

    Requires Playwright::

        pip install playwright
        playwright install chromium

    Args:
        excalidraw_path: Path to the ``.excalidraw`` file.
        output_path:     Output PNG path (default: same name with ``.png``).
        scale:           Device scale factor (default 2 for HiDPI).

    Returns:
        Path to the rendered PNG file.
    """
    from playwright.sync_api import sync_playwright

    if output_path is None:
        output_path = excalidraw_path.with_suffix(".png")

    data = json.loads(excalidraw_path.read_text(encoding="utf-8"))
    elements = [e for e in data.get("elements", []) if not e.get("isDeleted")]

    # Compute viewport from bounding box
    min_x = min((e.get("x", 0) for e in elements), default=0)
    min_y = min((e.get("y", 0) for e in elements), default=0)
    max_x = max((e.get("x", 0) + abs(e.get("width", 0)) for e in elements), default=800)
    max_y = max((e.get("y", 0) + abs(e.get("height", 0)) for e in elements), default=600)

    padding = 80
    vp_w = min(int(max_x - min_x + padding * 2), 1920)
    vp_h = max(int(max_y - min_y + padding * 2), 600)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": vp_w, "height": vp_h},
                                device_scale_factor=scale)
        page.set_content(_TEMPLATE)
        page.wait_for_function("window.__moduleReady === true", timeout=30000)

        result = page.evaluate(f"window.renderDiagram({json.dumps(data)})")
        if not result or not result.get("success"):
            error = result.get("error", "unknown") if result else "null"
            raise RuntimeError(f"Render failed: {error}")

        page.wait_for_function("window.__renderComplete === true", timeout=15000)
        svg_el = page.query_selector("#root svg")
        if svg_el is None:
            raise RuntimeError("No SVG element found after render")
        svg_el.screenshot(path=str(output_path))
        browser.close()

    return output_path