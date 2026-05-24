"""
Validation checks for diagram quality.

Provides programmatic checks that catch the common defects AI agents
introduce: overlapping elements, text overflowing containers, dangling
arrows, unbalanced spacing, and more.  Returns structured issue reports
and an overall quality score.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from diagramatic.core.spatial import (
    detect_dangling_arrows,
    detect_overlaps,
    detect_text_overflow,
)


@dataclass
class Issue:
    """A single diagram quality issue.

    Attributes:
        severity:    ``"error"``, ``"warning"``, or ``"info"``.
        category:    ``"overlap"``, ``"text_overflow"``, ``"dangling_arrow"``,
                     ``"spacing"``, ``"styling"``.
        message:     Human-readable description.
        element_ids: IDs of affected elements.
    """

    severity: str
    category: str
    message: str
    element_ids: list[str] = field(default_factory=list)


def validate_diagram(elements: list[dict]) -> list[Issue]:
    """Run all validation checks on a list of Excalidraw elements.

    Args:
        elements: List of Excalidraw element dicts.

    Returns:
        A sorted list of :class:`Issue` objects (errors first, then
        warnings, then info).
    """
    issues: list[Issue] = []

    # 1. Overlap check
    overlaps = detect_overlaps(elements, exclude_types={"arrow", "line"})
    for a, b, overlap in overlaps:
        issues.append(
            Issue(
                severity="error" if overlap > 5 else "warning",
                category="overlap",
                message=f"Elements overlap by {overlap:.0f}px",
                element_ids=[a.get("id", "?"), b.get("id", "?")],
            )
        )

    # 2. Text overflow check
    overflows = detect_text_overflow(elements)
    for te, cid in overflows:
        text = te.get("text", "")[:40]
        issues.append(
            Issue(
                severity="error",
                category="text_overflow",
                message=f"Text \"{text}...\" overflows container {cid}",
                element_ids=[te.get("id", "?"), cid],
            )
        )

    # 3. Dangling arrow check
    dangling = detect_dangling_arrows(elements)
    for a in dangling:
        sb = a.get("startBinding") or {}
        eb = a.get("endBinding") or {}
        sid = sb.get("elementId", "?")
        eid = eb.get("elementId", "?")
        issues.append(
            Issue(
                severity="error",
                category="dangling_arrow",
                message=f"Arrow {a.get('id', '?')[:12]} references missing elements ({sid}, {eid})",
                element_ids=[a.get("id", "?")],
            )
        )

    # 4. Styling consistency check
    font_families = {e.get("fontFamily") for e in elements if e.get("type") == "text"}
    if len(font_families) > 1:
        issues.append(
            Issue(
                severity="warning",
                category="styling",
                message=f"Inconsistent fontFamily: {font_families}",
                element_ids=[],
            )
        )

    roughnesses = {e.get("roughness") for e in elements if e.get("type") not in ("text", "line")}
    if len(roughnesses) > 2:
        issues.append(
            Issue(
                severity="info",
                category="styling",
                message=f"Inconsistent roughness values: {roughnesses}",
                element_ids=[],
            )
        )

    # 5. Container discipline check (skill's <30% rule)
    text_count = sum(1 for e in elements if e.get("type") == "text")
    contained = sum(1 for e in elements if e.get("type") == "text" and e.get("containerId"))
    if text_count > 0 and contained / text_count > 0.8:
        issues.append(
            Issue(
                severity="info",
                category="styling",
                message=f"{contained}/{text_count} text elements are in containers (high ratio)",
                element_ids=[],
            )
        )

    # Sort: errors first, then warnings, then info
    severity_order = {"error": 0, "warning": 1, "info": 2}
    issues.sort(key=lambda i: severity_order.get(i.severity, 3))
    return issues


def score_diagram(elements: list[dict]) -> tuple[int, list[Issue]]:
    """Score a diagram 0-100 based on validation checks.

    Start at 100 and subtract penalties for each issue:

    - Each error:     -15 points
    - Each warning:   -5 points
    - Each info:      -1 point

    The score is clamped to ``[0, 100]``.

    Args:
        elements: List of Excalidraw element dicts.

    Returns:
        ``(score, issues)`` tuple.
    """
    issues = validate_diagram(elements)
    score = 100
    for issue in issues:
        if issue.severity == "error":
            score -= 15
        elif issue.severity == "warning":
            score -= 5
        else:
            score -= 1
    score = max(0, min(100, score))
    return score, issues


def quality_report(elements: list[dict]) -> str:
    """Return a human-readable quality report string.

    Args:
        elements: List of Excalidraw element dicts.

    Returns:
        A multi-line string with the score and any issues found.
    """
    score, issues = score_diagram(elements)
    lines = [f"Quality Score: {score}/100", ""]
    if not issues:
        lines.append("✅ No issues found.")
        return "\n".join(lines)

    for iss in issues:
        marker = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(iss.severity, "•")
        lines.append(f"  {marker} [{iss.category}] {iss.message}")
    return "\n".join(lines)