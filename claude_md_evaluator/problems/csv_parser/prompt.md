# CSV Parser

## Task

Implement a CSV parser that reads CSV content from a string, performs type coercion, and validates the structure.

## Requirements

Create a file named `solution.py` containing the following functions:

```python
def parse_csv(content: str) -> list[dict[str, str | int | float | bool]]:
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
        List of dictionaries, one per data row. Keys are header names
        (stripped of whitespace), values are coerced to the appropriate type.

    Raises:
        ValueError: If the content is empty or contains only whitespace.
        ValueError: If any data row has a different number of fields than the header.
        ValueError: If there are duplicate header names.
    """


def parse_csv_file(file_path: str) -> list[dict[str, str | int | float | bool]]:
    """Parse a CSV file from disk.

    Args:
        file_path: Path to the CSV file.

    Returns:
        Parsed rows as a list of dictionaries.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the CSV content is invalid.
    """
```

## Constraints

- Do NOT use the `csv` module from the standard library. Parse manually by splitting on commas and newlines.
- Handle leading/trailing whitespace in headers and values by stripping them.
- Lines that are empty or contain only whitespace should be skipped (not treated as data rows).
- Header names should be stripped of whitespace.

## Edge Cases

- CSV with only a header row and no data rows (returns empty list).
- Values with extra whitespace around them.
- Mixed types in a single column.
- Boolean values with varying case ("True", "FALSE", "true").
- Negative numbers and zero.
- Rows with too many or too few fields compared to the header.
