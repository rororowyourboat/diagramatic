"""
Content-aware text sizing for monospace and proportional fonts.

Exact text dimensions depend on font, font-size, and platform.  For Excalidraw
diagrams with ``fontFamily: 3`` (monospace), character widths are perfectly
predictable, so we can compute container sizes that *always* fit the text.
"""

from __future__ import annotations

from typing import Tuple

# Monospace font (fontFamily=3) — every character is the same width
# Proportional fallback uses average character width

# Measured for Excalidraw on Chromium at various fontSizes:
#   char_width ≈ fontSize * 0.55
#   line_height ≈ fontSize * 1.35

_MONO_CHAR_RATIO = 0.55
_LINE_HEIGHT_RATIO = 1.35


def measure_text(
    text: str,
    font_size: float = 14,
    *,
    monospace: bool = True,
) -> Tuple[float, float]:
    """Compute the rendered width and height of *text* at *font_size*.

    Supports multi-line text (``\\n`` separated).  Returns the pixel
    dimensions that the text will occupy when rendered.

    Args:
        text:      The text content (may contain ``\\n``).
        font_size: Font size in pixels.
        monospace: If True, uses monospace width (fontFamily=3).
                   Otherwise, uses a proportional fallback.

    Returns:
        ``(width_px, height_px)`` tuple.
    """
    lines = text.split("\n")
    if not lines or (len(lines) == 1 and not lines[0]):
        lines = [""]

    num_lines = len(lines)

    if monospace:
        char_width = font_size * _MONO_CHAR_RATIO
    else:
        # Approximate average for proportional fonts
        char_width = font_size * 0.5

    max_chars = max(len(l) for l in lines)
    width = max_chars * char_width
    height = num_lines * font_size * _LINE_HEIGHT_RATIO

    return width, height


def auto_box_size(
    text: str,
    font_size: float = 14,
    *,
    padding_x: float = 16,
    padding_y: float = 12,
    monospace: bool = True,
    min_width: float = 120,
    min_height: float = 50,
) -> Tuple[float, float, float, float]:
    """Compute a container box that fits *text* with padding.

    Returns ``(box_width, box_height, text_x_offset, text_y_offset)`` — the
    outer box dimensions and the offset at which to place the text element
    so it is centered inside the box.

    Args:
        text:       The text content.
        font_size:  Font size in pixels.
        padding_x:  Horizontal padding inside the box.
        padding_y:  Vertical padding inside the box.
        monospace:  If True, uses monospace character widths.
        min_width:  Minimum box width.
        min_height: Minimum box height.

    Returns:
        ``(box_w, box_h, text_x, text_y)`` — the container dimensions and
        the top-left coordinate of the text element relative to the container.
    """
    text_w, text_h = measure_text(text, font_size, monospace=monospace)
    box_w = max(text_w + padding_x * 2, min_width)
    box_h = max(text_h + padding_y * 2, min_height)

    # Center text in the box
    text_x = (box_w - text_w) / 2
    text_y = (box_h - text_h) / 2

    return box_w, box_h, text_x, text_y


def fit_text_to_box(
    text: str,
    box_width: float,
    box_height: float,
    font_size: float = 14,
    *,
    padding_x: float = 16,
    padding_y: float = 12,
    monospace: bool = True,
) -> bool:
    """Check whether *text* fits inside *box_width* × *box_height*.

    Args:
        text:        The text content.
        box_width:   Available container width.
        box_height:  Available container height.
        font_size:   Font size in pixels.
        padding_x:   Horizontal padding required.
        padding_y:   Vertical padding required.
        monospace:   If True, uses monospace widths.

    Returns:
        True if the text fits, False if it overflows.
    """
    text_w, text_h = measure_text(text, font_size, monospace=monospace)
    return (text_w + padding_x * 2 <= box_width) and (
        text_h + padding_y * 2 <= box_height
    )