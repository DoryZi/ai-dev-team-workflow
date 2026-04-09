"""Tests for the CSV Parser problem."""
from __future__ import annotations

from pathlib import Path

import pytest

from solution import parse_csv, parse_csv_file


class TestParseCsvBasic:
    """Tests for basic CSV parsing."""

    def test_simple_csv(self) -> None:
        content = "name,age,city\nAlice,30,NYC\nBob,25,LA"
        rows = parse_csv(content)
        assert len(rows) == 2
        assert rows[0] == {"name": "Alice", "age": 30, "city": "NYC"}
        assert rows[1] == {"name": "Bob", "age": 25, "city": "LA"}

    def test_header_only_returns_empty_list(self) -> None:
        content = "name,age,city"
        rows = parse_csv(content)
        assert rows == []

    def test_single_column(self) -> None:
        content = "value\n42\nhello"
        rows = parse_csv(content)
        assert rows == [{"value": 42}, {"value": "hello"}]


class TestParseCsvTypeCoercion:
    """Tests for type coercion."""

    def test_integer_coercion(self) -> None:
        content = "val\n42\n-3\n0"
        rows = parse_csv(content)
        assert rows[0]["val"] == 42
        assert rows[1]["val"] == -3
        assert rows[2]["val"] == 0
        assert all(isinstance(r["val"], int) for r in rows)

    def test_float_coercion(self) -> None:
        content = "val\n3.14\n-0.5\n0.0"
        rows = parse_csv(content)
        assert rows[0]["val"] == pytest.approx(3.14)
        assert rows[1]["val"] == pytest.approx(-0.5)
        assert all(isinstance(r["val"], float) for r in rows)

    def test_boolean_coercion(self) -> None:
        content = "val\ntrue\nfalse\nTrue\nFALSE"
        rows = parse_csv(content)
        assert rows[0]["val"] is True
        assert rows[1]["val"] is False
        assert rows[2]["val"] is True
        assert rows[3]["val"] is False

    def test_string_fallback(self) -> None:
        content = "val\nhello\nworld"
        rows = parse_csv(content)
        assert rows[0]["val"] == "hello"
        assert isinstance(rows[0]["val"], str)

    def test_empty_field_stays_empty_string(self) -> None:
        content = "a,b\n1,"
        rows = parse_csv(content)
        assert rows[0]["b"] == ""

    def test_mixed_types_in_column(self) -> None:
        content = "val\n42\nhello\n3.14\ntrue"
        rows = parse_csv(content)
        assert rows[0]["val"] == 42
        assert rows[1]["val"] == "hello"
        assert rows[2]["val"] == pytest.approx(3.14)
        assert rows[3]["val"] is True


class TestParseCsvWhitespace:
    """Tests for whitespace handling."""

    def test_strips_header_whitespace(self) -> None:
        content = " name , age \nAlice,30"
        rows = parse_csv(content)
        assert "name" in rows[0]
        assert "age" in rows[0]

    def test_strips_value_whitespace(self) -> None:
        content = "val\n  hello  "
        rows = parse_csv(content)
        assert rows[0]["val"] == "hello"

    def test_skips_blank_lines(self) -> None:
        content = "name,age\n\nAlice,30\n\nBob,25\n"
        rows = parse_csv(content)
        assert len(rows) == 2


class TestParseCsvValidation:
    """Tests for error handling and validation."""

    def test_empty_content_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            parse_csv("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            parse_csv("   \n\n  ")

    def test_row_field_count_mismatch_raises(self) -> None:
        content = "a,b,c\n1,2"
        with pytest.raises(ValueError):
            parse_csv(content)

    def test_row_too_many_fields_raises(self) -> None:
        content = "a,b\n1,2,3"
        with pytest.raises(ValueError):
            parse_csv(content)

    def test_duplicate_headers_raises(self) -> None:
        content = "name,age,name\nAlice,30,Bob"
        with pytest.raises(ValueError, match="[Dd]uplicate"):
            parse_csv(content)


class TestParseCsvFile:
    """Tests for file-based parsing."""

    def test_parse_valid_file(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("name,age\nAlice,30\n")
        rows = parse_csv_file(str(csv_file))
        assert len(rows) == 1
        assert rows[0] == {"name": "Alice", "age": 30}

    def test_file_not_found_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            parse_csv_file("/nonexistent/path/to/file.csv")
