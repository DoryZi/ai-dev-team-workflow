"""Reference solution for the CSV Parser problem."""
from __future__ import annotations

from pathlib import Path

# Type alias for coerced CSV values
CsvValue = str | int | float | bool


def _coerce_value(raw: str) -> CsvValue:
    """Coerce a raw string value to the most specific type.

    Applies coercion in order: int, float, bool, then string.

    Args:
        raw: The raw string value from the CSV field.

    Returns:
        The coerced value as int, float, bool, or str.
    """
    stripped = raw.strip()

    # Empty values remain as empty strings
    if not stripped:
        return ""

    # Try integer
    try:
        return int(stripped)
    except ValueError:
        pass

    # Try float
    try:
        return float(stripped)
    except ValueError:
        pass

    # Try boolean
    if stripped.lower() == "true":
        return True
    if stripped.lower() == "false":
        return False

    # Default to stripped string
    return stripped


def parse_csv(content: str) -> list[dict[str, CsvValue]]:
    """Parse CSV content string into a list of row dictionaries.

    The first line is treated as the header row. Each subsequent line
    becomes a dictionary mapping header names to coerced values.

    Type coercion rules (applied in order):
    1. If the value is a valid integer (e.g., "42", "-3"), coerce to int.
    2. If the value is a valid float (e.g., "3.14", "-0.5"), coerce to float.
    3. If the value is "true" or "false" (case-insensitive), coerce to bool.
    4. Otherwise, keep as a stripped string.

    Empty fields (whitespace-only or empty string) remain as empty strings.

    Args:
        content: The raw CSV string to parse.

    Returns:
        List of dictionaries, one per data row.

    Raises:
        ValueError: If the content is empty or contains only whitespace.
        ValueError: If any data row has a different number of fields than the header.
        ValueError: If there are duplicate header names.
    """
    if not content or not content.strip():
        raise ValueError("CSV content is empty")

    lines = content.strip().splitlines()

    # Filter out blank lines, but track original line numbers for error messages
    non_empty_lines: list[tuple[int, str]] = []
    for i, line in enumerate(lines, start=1):
        if line.strip():
            non_empty_lines.append((i, line))

    if not non_empty_lines:
        raise ValueError("CSV content is empty")

    # Parse header
    _, header_line = non_empty_lines[0]
    headers = [h.strip() for h in header_line.split(",")]

    # Validate no duplicate headers
    seen: set[str] = set()
    for header in headers:
        if header in seen:
            raise ValueError(f"Duplicate header name: {header}")
        seen.add(header)

    # Parse data rows
    rows: list[dict[str, CsvValue]] = []
    for line_num, line in non_empty_lines[1:]:
        fields = line.split(",")

        if len(fields) != len(headers):
            raise ValueError(
                f"Row at line {line_num} has {len(fields)} fields, "
                f"expected {len(headers)}"
            )

        row = {header: _coerce_value(field) for header, field in zip(headers, fields)}
        rows.append(row)

    return rows


def parse_csv_file(file_path: str) -> list[dict[str, CsvValue]]:
    """Parse a CSV file from disk.

    Args:
        file_path: Path to the CSV file.

    Returns:
        Parsed rows as a list of dictionaries.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the CSV content is invalid.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"CSV file not found: {file_path}")

    content = path.read_text(encoding="utf-8")
    return parse_csv(content)
