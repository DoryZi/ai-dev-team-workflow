"""Parse CLAUDE.md files and extract actionable coding rules.

Reads a markdown file and identifies coding conventions expressed as
DO/DON'T blocks, section headings, keyword patterns, and size-limit tables.
Returns a structured list of Rule objects suitable for downstream checkers.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public data model
# ---------------------------------------------------------------------------

VALID_CATEGORIES = frozenset(
    {
        "type_hints",
        "docstrings",
        "imports",
        "paths",
        "error_handling",
        "naming",
        "file_size",
        "dry",
        "general",
    }
)

VALID_CHECK_TYPES = frozenset({"static", "llm", "both"})


@dataclass(frozen=True)
class Rule:
    """A single actionable coding rule extracted from a CLAUDE.md file.

    Attributes:
        id: Unique identifier derived from category and description.
        category: One of the VALID_CATEGORIES values.
        description: Human-readable description of the rule.
        check_type: How the rule should be verified (static, llm, or both).
        keywords: AST/text matching keywords relevant to the rule.
        source_section: The markdown heading the rule was extracted from.
        do_example: Optional code example of the correct pattern.
        dont_example: Optional code example of the incorrect pattern.
    """

    id: str
    category: str
    description: str
    check_type: str = "static"
    keywords: tuple[str, ...] = ()
    source_section: str = ""
    do_example: str = ""
    dont_example: str = ""


# ---------------------------------------------------------------------------
# Category detection patterns
# ---------------------------------------------------------------------------

# Maps (regex-pattern, keywords-tuple, check_type) -> category.
# Patterns are matched against section headings and rule text.
_CATEGORY_PATTERNS: list[tuple[re.Pattern[str], str, str, tuple[str, ...]]] = [
    (re.compile(r"type\s*hint", re.IGNORECASE), "type_hints", "static", ("def", "->", ":")),
    (re.compile(r"docstring", re.IGNORECASE), "docstrings", "static", ("def", '"""')),
    (re.compile(r"import", re.IGNORECASE), "imports", "static", ("import", "from")),
    (re.compile(r"pathlib|paths?\b.*use\s+pathlib|use\s+pathlib", re.IGNORECASE), "paths", "static", ("pathlib", "os.path")),
    (
        re.compile(r"error\s*handl|exception|try\s*[/:]|never\s+silent", re.IGNORECASE),
        "error_handling",
        "both",
        ("try", "except", "raise"),
    ),
    (re.compile(r"\bnaming\b|snake.?case|camel.?case|pascal.?case", re.IGNORECASE), "naming", "static", ("def", "class")),
    (
        re.compile(r"file\s*size|max\s*lines|size\s*limit|keep\s*it\s*small", re.IGNORECASE),
        "file_size",
        "static",
        (),
    ),
    (re.compile(r"\bdry\b|don.?t\s+repeat|extract\s+shared|shared\s+logic", re.IGNORECASE), "dry", "both", ()),
    (re.compile(r"logging|logger", re.IGNORECASE), "general", "static", ("logging", "logger")),
    (re.compile(r"secret|api.?key|credential|env\s*var", re.IGNORECASE), "general", "static", ("os.getenv", "env")),
]

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _slugify(text: str) -> str:
    """Turn a heading/description into a short slug for use as a rule id.

    Args:
        text: Free-form text to slugify.

    Returns:
        Lowercase alphanumeric string with underscores.
    """
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug[:60]


def _detect_category(heading: str, body: str = "") -> tuple[str, str, tuple[str, ...]]:
    """Match heading (and optionally body) against known patterns.

    The heading is checked first.  If a match is found there, it wins
    immediately — this prevents code-block content in the body from
    causing a mis-classification.  The body is only consulted when
    the heading alone does not match any known pattern.

    Args:
        heading: Section heading text (highest priority).
        body: Section body text (lower priority, checked as fallback).

    Returns:
        Tuple of (category, check_type, keywords).  Falls back to
        ``("general", "llm", ())`` when no pattern matches.
    """
    for pattern, category, check_type, keywords in _CATEGORY_PATTERNS:
        if pattern.search(heading):
            return category, check_type, keywords
    for pattern, category, check_type, keywords in _CATEGORY_PATTERNS:
        if pattern.search(body):
            return category, check_type, keywords
    return "general", "llm", ()


def _extract_code_blocks(section_text: str) -> tuple[str, str]:
    """Pull the first DO and DON'T code examples from a markdown section.

    Args:
        section_text: Raw markdown text for one section.

    Returns:
        Tuple of (do_example, dont_example) — empty strings when absent.
    """
    do_example = ""
    dont_example = ""

    # Split into segments around **DO:** / **DON'T:** markers
    do_pattern = re.compile(r"\*\*DO:\*\*", re.IGNORECASE)
    dont_pattern = re.compile(r"\*\*DON'?T:\*\*", re.IGNORECASE)

    code_block_re = re.compile(r"```[a-z]*\n(.*?)```", re.DOTALL)

    do_match = do_pattern.search(section_text)
    dont_match = dont_pattern.search(section_text)

    if do_match:
        # Grab text between DO marker and either DON'T marker or end
        start = do_match.end()
        end = dont_match.start() if dont_match and dont_match.start() > start else len(section_text)
        block = code_block_re.search(section_text[start:end])
        if block:
            do_example = block.group(1).strip()

    if dont_match:
        start = dont_match.end()
        block = code_block_re.search(section_text[start:])
        if block:
            dont_example = block.group(1).strip()

    return do_example, dont_example


def _extract_size_limits(section_text: str) -> list[tuple[str, int]]:
    """Find markdown tables with scope/max-lines pairs.

    Args:
        section_text: Raw markdown text to search for tables.

    Returns:
        List of (scope_name, max_lines) tuples found.
    """
    results: list[tuple[str, int]] = []
    row_re = re.compile(r"\|\s*(\w[\w\s]*?)\s*\|\s*(\d+)\s*\|")
    for match in row_re.finditer(section_text):
        scope = match.group(1).strip()
        # Skip header-separator rows
        if scope.replace("-", "") == "":
            continue
        # Skip column headers like "Scope"
        if scope.lower() in {"scope", "rule", "detail"}:
            continue
        try:
            limit = int(match.group(2))
            results.append((scope, limit))
        except ValueError:
            continue
    return results


def _split_sections(content: str) -> list[tuple[str, str]]:
    """Split markdown content into (heading, body) pairs.

    Uses ``##`` and ``###`` headings as section delimiters.

    Args:
        content: Full markdown document text.

    Returns:
        List of (heading_text, section_body) tuples.
    """
    heading_re = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)
    matches = list(heading_re.finditer(content))

    if not matches:
        return []

    sections: list[tuple[str, str]] = []
    for i, match in enumerate(matches):
        heading = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[start:end].strip()
        sections.append((heading, body))

    return sections


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_claude_md(path: Path) -> list[Rule]:
    """Parse a CLAUDE.md file and extract actionable coding rules.

    Scans markdown sections for rule indicators such as DO/DON'T blocks,
    keyword headings, and size-limit tables.  Each detected rule is
    returned as a structured ``Rule`` object.

    Args:
        path: Filesystem path to the CLAUDE.md file.

    Returns:
        List of extracted Rule objects, ordered by appearance.

    Raises:
        FileNotFoundError: If *path* does not exist.
        PermissionError: If *path* cannot be read.
    """
    content = path.read_text(encoding="utf-8")
    return parse_claude_md_text(content)


def parse_claude_md_text(content: str) -> list[Rule]:
    """Parse CLAUDE.md content from a string and extract actionable coding rules.

    This is the text-based variant of :func:`parse_claude_md` — useful when
    the markdown content is already in memory.

    Args:
        content: Raw markdown text of a CLAUDE.md file.

    Returns:
        List of extracted Rule objects, ordered by appearance.
    """
    if not content or not content.strip():
        return []

    sections = _split_sections(content)
    if not sections:
        return []

    rules: list[Rule] = []
    seen_ids: set[str] = set()

    for heading, body in sections:
        combined_text = f"{heading}\n{body}"
        category, check_type, keywords = _detect_category(heading, body)

        # Only create a rule when we have a DO/DON'T block, a recognised
        # non-general category, or a size-limit table.
        has_do_dont = bool(
            re.search(r"\*\*DO:?\*\*", combined_text, re.IGNORECASE)
            or re.search(r"\*\*DON'?T:?\*\*", combined_text, re.IGNORECASE)
        )

        size_limits = _extract_size_limits(body)
        is_recognised = category != "general"

        if not has_do_dont and not is_recognised and not size_limits:
            continue

        # Build description from heading, stripping trailing em-dashes etc.
        description = re.sub(r"\s*[—–-]+\s*", " — ", heading).strip()

        do_example, dont_example = _extract_code_blocks(body)

        # For file-size sections, emit one rule per scope row
        if size_limits and category == "file_size":
            for scope, limit in size_limits:
                rule_desc = f"{scope} max {limit} lines"
                rule_id = _slugify(f"file_size_{scope}")
                if rule_id in seen_ids:
                    rule_id = f"{rule_id}_{limit}"
                seen_ids.add(rule_id)
                rules.append(
                    Rule(
                        id=rule_id,
                        category="file_size",
                        description=rule_desc,
                        check_type="static",
                        keywords=(scope.lower(),),
                        source_section=heading,
                    )
                )
            continue

        rule_id = _slugify(f"{category}_{description}")
        if rule_id in seen_ids:
            rule_id = f"{rule_id}_{len(rules)}"
        seen_ids.add(rule_id)

        rules.append(
            Rule(
                id=rule_id,
                category=category,
                description=description,
                check_type=check_type,
                keywords=keywords,
                source_section=heading,
                do_example=do_example,
                dont_example=dont_example,
            )
        )

    logger.info("Parsed %d rules from CLAUDE.md", len(rules))
    return rules
