"""Render evaluation reports as self-contained HTML pages.

Uses Jinja2 to render a JSON evaluation report dict into a styled,
interactive HTML file with embedded CSS and JavaScript.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


# ---------------------------------------------------------------------------
# Jinja2 helpers
# ---------------------------------------------------------------------------


def _score_color_class(score: float) -> str:
    """Return a CSS class name for color-coding a 0.0-1.0 score.

    Args:
        score: Numeric score between 0.0 and 1.0.

    Returns:
        CSS class string: ``score-green``, ``score-amber``, or ``score-red``.
    """
    if score >= 0.8:
        return "score-green"
    if score >= 0.6:
        return "score-amber"
    return "score-red"


def _score_bg_class(score: float) -> str:
    """Return a CSS background class for color-coding a 0.0-1.0 score.

    Args:
        score: Numeric score between 0.0 and 1.0.

    Returns:
        CSS class string: ``bg-green``, ``bg-amber``, or ``bg-red``.
    """
    if score >= 0.8:
        return "bg-green"
    if score >= 0.6:
        return "bg-amber"
    return "bg-red"


def _build_jinja_env() -> Environment:
    """Create and configure the Jinja2 template environment.

    Returns:
        Configured Jinja2 Environment with autoescape and helper globals.
    """
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=True,
    )
    env.globals["score_color_class"] = _score_color_class
    env.globals["score_bg_class"] = _score_bg_class
    return env


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_html_report(report_data: dict, output_path: Path) -> Path:
    """Render an evaluation report as a self-contained HTML page.

    Args:
        report_data: The evaluation report dict (loaded from JSON).
        output_path: Where to write the HTML file.

    Returns:
        Path to the written HTML file.

    Raises:
        FileNotFoundError: If the template file is missing.
    """
    env = _build_jinja_env()
    template = env.get_template("report.html")

    html = template.render(report=report_data)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")

    logger.info("HTML report written to %s", output_path)
    return output_path


def render_html_from_json(json_path: Path, output_path: Path | None = None) -> Path:
    """Load a JSON report and render it as HTML.

    Convenience wrapper that reads a JSON evaluation report file and
    passes it to :func:`render_html_report`.

    If *output_path* is ``None``, writes to the same directory as the
    JSON file with a ``.html`` extension.

    Args:
        json_path: Path to the JSON evaluation report.
        output_path: Where to write the HTML file. Defaults to
            ``<json_path>.html`` in the same directory.

    Returns:
        Path to the written HTML file.

    Raises:
        FileNotFoundError: If *json_path* does not exist.
        json.JSONDecodeError: If the JSON file is malformed.
    """
    json_path = Path(json_path)
    if not json_path.is_file():
        msg = f"JSON report not found: {json_path}"
        raise FileNotFoundError(msg)

    report_data = json.loads(json_path.read_text(encoding="utf-8"))

    if output_path is None:
        output_path = json_path.with_suffix(".html")

    return render_html_report(report_data, output_path)
