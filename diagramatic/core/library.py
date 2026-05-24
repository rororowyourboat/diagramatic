"""
Excalidraw library registry — loads .excalidrawlib files and resolves
named components for use in generated diagrams.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Built-in library paths ─────────────────────────────────────────
# These are the library files you downloaded and placed in the vault/skills
_BUILTIN_LIBS = {
    "arch": "architecture-diagram-components.excalidrawlib",
    "system-design": "system-design.excalidrawlib",
    "viz": "data-viz.excalidrawlib",
    "icons": "awesome-icons.excalidrawlib",
}

# Where to search for .excalidrawlib files
SEARCH_PATHS: list[Path] = []

# Register common locations
for _p in ["/home/rohan/Downloads", Path.home() / "Downloads",
           Path(__file__).resolve().parent.parent / "libraries"]:
    if Path(_p).is_dir():
        SEARCH_PATHS.append(Path(_p))


def register_search_path(path: str | Path) -> None:
    """Add a directory to the library search path."""
    p = Path(path).resolve()
    if p.is_dir() and p not in SEARCH_PATHS:
        SEARCH_PATHS.append(p)


def _find_library_file(name: str) -> Path | None:
    """Find a .excalidrawlib file by short or full name."""
    # Check built-in name mapping
    if name in _BUILTIN_LIBS:
        for sp in SEARCH_PATHS:
            candidate = sp / _BUILTIN_LIBS[name]
            if candidate.exists():
                return candidate

    # Try exact path
    p = Path(name)
    if p.exists():
        return p
    if p.with_suffix(".excalidrawlib").exists():
        return p.with_suffix(".excalidrawlib")

    # Try search paths
    for sp in SEARCH_PATHS:
        candidate = sp / name
        if candidate.exists():
            return candidate
        candidate = sp / f"{name}.excalidrawlib"
        if candidate.exists():
            return candidate

    return None


def _load_library(path: Path) -> list[dict]:
    """Load a .excalidrawlib file and return the list of items."""
    data = json.loads(path.read_text(encoding="utf-8"))
    # Support both key formats
    items = data.get("libraryItems", data.get("library", []))
    return items


def list_library_items(lib_name: str | None = None) -> dict[str, list[str]]:
    """List all available library items, optionally filtered by library.

    Returns:
        ``{library_name: [item_name1, item_name2, ...]}``
    """
    result: dict[str, list[str]] = {}

    def _extract_name(item: Any, idx: int) -> str:
        """Get a human-readable name from a library item."""
        if isinstance(item, dict):
            name = item.get("name", "")
            if name:
                return name
            # Try to extract from text elements
            for el in item.get("elements", []):
                if isinstance(el, dict) and el.get("type") == "text":
                    t = el.get("text", "")
                    if t and len(t) < 60:
                        return t.replace("\\n", " ").strip()
        elif isinstance(item, list):
            for el in item:
                if isinstance(el, dict) and el.get("type") == "text":
                    t = el.get("text", "")
                    if t and len(t) < 60:
                        return t.replace("\\n", " ").strip()
        return f"Item #{idx}"

    if lib_name:
        path = _find_library_file(lib_name)
        if path:
            items = _load_library(path)
            names = [_extract_name(item, i) for i, item in enumerate(items)]
            result[path.stem] = names
    else:
        for short_name, filename in _BUILTIN_LIBS.items():
            for sp in SEARCH_PATHS:
                path = sp / filename
                if path.exists():
                    items = _load_library(path)
                    names = [_extract_name(item, i) for i, item in enumerate(items)]
                    result[short_name] = names
                    break

    return result


def get_library_item(lib_name: str, item_name: str) -> list[dict] | None:
    """Get the Excalidraw elements for a named library item.

    Args:
        lib_name:  Library short name (``"arch"``, ``"system-design"``, etc.)
                   or filename.
        item_name: The component name (``"Docker"``, ``"Load Balancer"``, etc.)

    Returns:
        List of Excalidraw element dicts, or ``None`` if not found.
    """
    path = _find_library_file(lib_name)
    if not path:
        return None

    target = item_name.lower().replace("\\n", " ").replace("\n", " ").strip()

    items = _load_library(path)
    for item in items:
        if isinstance(item, dict):
            name = item.get("name", "")
            if name.lower().replace("\\n", " ").replace("\n", " ").strip() == target:
                return item.get("elements", [])
        elif isinstance(item, list):
            # Raw element list — check text content
            texts = []
            for el in item:
                if isinstance(el, dict) and el.get("type") == "text":
                    t = el.get("text", "")
                    if t:
                        texts.append(t.replace("\\n", " ").replace("\n", " ").strip())
            combined = " ".join(texts).lower()
            if target.replace("-", " ") in combined or target in combined:
                return item

    return None


def resolve_semantic_icon(semantic: str) -> list[dict] | None:
    """Resolve a semantic node type to a library icon.

    Maps common architecture terms to library items.

    Args:
        semantic: A string like ``"docker"``, ``"load-balancer"``,
                  ``"database"``, ``"user"``, ``"server"``, ``"cdn"``, etc.

    Returns:
        List of Excalidraw element dicts, or ``None`` if no match found.
    """
    # Map semantic types to (library_name, item_name)
    mapping: dict[str, tuple[str, str]] = {
        # Architecture components
        "docker": ("arch", "Docker"),
        "slack": ("arch", "Slack"),
        "github": ("arch", "GitHub"),
        "vpc": ("arch", "VPC"),
        "public-subnet": ("arch", "Public subnet"),
        "private-subnet": ("arch", "Private subnet"),
        "user": ("arch", "User"),
        "users": ("arch", "Users"),
        "device": ("arch", "Device"),
        "server": ("arch", "Server"),
        "email": ("arch", "Email"),
        # System design components
        "application-server": ("system-design", "Application server"),
        "load-balancer": ("system-design", "Load Balancer"),
        "message-queue": ("system-design", "Message Q"),
        "cdn": ("system-design", "CDN"),
        "dns": ("system-design", "DNS"),
        "database": ("system-design", "Relational DB"),
        "relational-db": ("system-design", "Relational DB"),
        "document-db": ("system-design", "Document DB"),
        "graph-db": ("system-design", "Graph DB"),
        "object-storage": ("system-design", "Object Storage"),
        "columnar-db": ("system-design", "Columnar DB"),
        "cold-storage": ("system-design", "Cold Storage"),
        "pipeline": ("system-design", "Pipeline"),
        "cloud": ("system-design", "cloud"),
        "mobile": ("system-design", "Mobile"),
        "archive": ("system-design", "Archive"),
        "stack-storage": ("system-design", "Stack Storage"),
        # Icons
        "search": ("icons", "Search"),
        "delete": ("icons", "Delete"),
        "home": ("icons", "Home"),
        "lock": ("icons", "Lock"),
        "calendar": ("icons", "Calendar"),
        "chart": ("icons", "Chart"),
        "notification": ("icons", "Notifications"),
        "location": ("icons", "Location"),
        "tag": ("icons", "Tag"),
        "user-icon": ("icons", "User"),
        "email-icon": ("icons", "email"),
    }

    key = semantic.lower().replace("_", "-").replace(" ", "-")
    if key in mapping:
        lib_name, item_name = mapping[key]
        return get_library_item(lib_name, item_name)

    return None


def embed_library_item(
    elements: list[dict],
    x: float,
    y: float,
    scale: float = 1.0,
) -> list[dict]:
    """Position a library item's elements at (x, y) and optionally scale them.

    Args:
        elements: Raw element dicts from ``get_library_item()``.
        x:        Target X position.
        y:        Target Y position.
        scale:    Scale factor (default 1.0).

    Returns:
        New element dicts with positions offset and IDs regenerated.
    """
    import uuid

    if not elements:
        return []

    # Compute the bounding box of the original elements
    xs = [e.get("x", 0) for e in elements]
    ys = [e.get("y", 0) for e in elements]
    min_x, min_y = min(xs), min(ys)

    placed = []
    for e in elements:
        new_el = dict(e)
        new_el["id"] = uuid.uuid4().hex[:20]
        new_el["x"] = x + (new_el.get("x", 0) - min_x) * scale
        new_el["y"] = y + (new_el.get("y", 0) - min_y) * scale
        if scale != 1.0:
            new_el["width"] = new_el.get("width", 0) * scale
            new_el["height"] = new_el.get("height", 0) * scale
        # Clear bindings that point to old element IDs
        new_el["boundElements"] = None
        new_el.pop("containerId", None)
        if new_el.get("type") == "arrow":
            new_el["startBinding"] = None
            new_el["endBinding"] = None
        placed.append(new_el)

    return placed