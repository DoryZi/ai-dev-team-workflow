"""Tests for CLI functionality."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from evaluator.cli import create_parser, main


class TestCLIArgumentParsing:
    """Test CLI argument parsing functionality."""

    def test_create_parser_returns_argument_parser(self) -> None:
        """Verify create_parser returns a configured ArgumentParser."""
        parser = create_parser()
        assert parser is not None
        # Verify it's an ArgumentParser by checking it has parse_args method
        assert hasattr(parser, 'parse_args')

    def test_parser_accepts_claude_md_file_path(self, tmp_claude_md: Path) -> None:
        """CLI accepts a single CLAUDE.md file path."""
        parser = create_parser()
        args = parser.parse_args([str(tmp_claude_md)])
        assert args.claude_md_files == [tmp_claude_md]

    def test_parser_accepts_multiple_claude_md_files(self, multiple_claude_md_files: list[Path]) -> None:
        """CLI accepts multiple CLAUDE.md file paths."""
        parser = create_parser()
        file_paths = [str(f) for f in multiple_claude_md_files]
        args = parser.parse_args(file_paths)
        assert args.claude_md_files == multiple_claude_md_files

    def test_parser_accepts_problem_set_selection(self, tmp_claude_md: Path, sample_problem_set: list[str]) -> None:
        """CLI accepts problem set selection via --problems option."""
        parser = create_parser()
        problems_arg = ','.join(sample_problem_set)
        args = parser.parse_args([str(tmp_claude_md), '--problems', problems_arg])
        assert args.problems == sample_problem_set

    def test_parser_accepts_single_problem(self, tmp_claude_md: Path) -> None:
        """CLI accepts a single problem selection."""
        parser = create_parser()
        args = parser.parse_args([str(tmp_claude_md), '--problems', 'lru_cache'])
        assert args.problems == ['lru_cache']

    def test_parser_default_problems_is_all(self, tmp_claude_md: Path) -> None:
        """When no --problems specified, defaults to 'all'."""
        parser = create_parser()
        args = parser.parse_args([str(tmp_claude_md)])
        assert args.problems == ['all']

    def test_parser_requires_at_least_one_claude_md_file(self) -> None:
        """Parser requires at least one CLAUDE.md file argument."""
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_parser_validates_claude_md_files_exist(self) -> None:
        """Parser validates that specified CLAUDE.md files exist."""
        parser = create_parser()
        args = parser.parse_args(['/nonexistent/CLAUDE.md'])
        # The parser should parse successfully but validation should happen in main()
        assert args.claude_md_files == [Path('/nonexistent/CLAUDE.md')]

    def test_parser_accepts_output_directory(self, tmp_claude_md: Path, tmp_path: Path) -> None:
        """CLI accepts output directory via --output-dir option."""
        parser = create_parser()
        output_dir = tmp_path / "output"
        args = parser.parse_args([str(tmp_claude_md), '--output-dir', str(output_dir)])
        assert args.output_dir == output_dir

    def test_parser_default_output_directory(self, tmp_claude_md: Path) -> None:
        """When no --output-dir specified, defaults to './evaluations'."""
        parser = create_parser()
        args = parser.parse_args([str(tmp_claude_md)])
        assert args.output_dir == Path('./evaluations')


class TestCLIMainFunction:
    """Test main CLI function."""

    def test_main_with_nonexistent_file_exits_with_error(self) -> None:
        """Main function exits with error when CLAUDE.md file doesn't exist."""
        with pytest.raises(SystemExit) as exc_info:
            main(['/nonexistent/CLAUDE.md'])
        assert exc_info.value.code != 0

    def test_main_with_valid_file_calls_orchestrator(self, tmp_claude_md: Path) -> None:
        """Main function calls orchestrator when given valid file."""
        with patch('evaluator.cli.run_evaluation') as mock_orchestrator:
            mock_orchestrator.return_value = None
            result = main([str(tmp_claude_md)])

            mock_orchestrator.assert_called_once()
            call_args = mock_orchestrator.call_args[0]
            assert call_args[0] == [tmp_claude_md]  # claude_md_files
            assert call_args[1] == ['all']  # problems
            assert call_args[2] == Path('./evaluations')  # output_dir
            assert result == 0

    def test_main_with_multiple_files_calls_orchestrator(self, multiple_claude_md_files: list[Path]) -> None:
        """Main function handles multiple CLAUDE.md files."""
        with patch('evaluator.cli.run_evaluation') as mock_orchestrator:
            mock_orchestrator.return_value = None
            file_paths = [str(f) for f in multiple_claude_md_files]
            result = main(file_paths)

            mock_orchestrator.assert_called_once()
            call_args = mock_orchestrator.call_args[0]
            assert call_args[0] == multiple_claude_md_files
            assert result == 0

    def test_main_with_custom_problems_calls_orchestrator(self, tmp_claude_md: Path) -> None:
        """Main function passes custom problem selection to orchestrator."""
        with patch('evaluator.cli.run_evaluation') as mock_orchestrator:
            mock_orchestrator.return_value = None
            result = main([str(tmp_claude_md), '--problems', 'lru_cache,csv_parser'])

            mock_orchestrator.assert_called_once()
            call_args = mock_orchestrator.call_args[0]
            assert call_args[1] == ['lru_cache', 'csv_parser']
            assert result == 0

    def test_main_handles_orchestrator_exceptions(self, tmp_claude_md: Path) -> None:
        """Main function handles exceptions from orchestrator gracefully."""
        with patch('evaluator.cli.run_evaluation') as mock_orchestrator:
            mock_orchestrator.side_effect = RuntimeError("Evaluation failed")

            with pytest.raises(SystemExit) as exc_info:
                main([str(tmp_claude_md)])
            assert exc_info.value.code != 0

    def test_main_creates_output_directory(self, tmp_claude_md: Path, tmp_path: Path) -> None:
        """Main function creates output directory if it doesn't exist."""
        output_dir = tmp_path / "custom_output"
        assert not output_dir.exists()

        with patch('evaluator.cli.run_evaluation') as mock_orchestrator:
            mock_orchestrator.return_value = None
            main([str(tmp_claude_md), '--output-dir', str(output_dir)])

            assert output_dir.exists()
            assert output_dir.is_dir()


class TestCLIEntryPoint:
    """Test CLI entry point functionality."""

    def test_cli_entry_point_exists(self) -> None:
        """Verify CLI entry point is properly configured."""
        # This tests that the module can be imported and has a main function
        try:
            from evaluator.cli import main
            assert callable(main)
        except ImportError:
            pytest.fail("CLI module should be importable")

    def test_cli_executable_via_python_module(self, tmp_claude_md: Path) -> None:
        """CLI can be executed via python -m evaluator."""
        # Mock the run_evaluation to avoid actual execution
        with patch('evaluator.cli.run_evaluation'):
            # Test that we can call the module (this will be implemented in the CLI)
            result = subprocess.run([
                sys.executable, '-c',
                f'from evaluator.cli import main; main(["{tmp_claude_md}"])'
            ], capture_output=True, text=True)
            # Should not crash on import/execution
            assert result.returncode == 0


class TestCLIValidation:
    """Test CLI input validation."""

    def test_cli_validates_claude_md_file_extension(self) -> None:
        """CLI validates that files have .md extension."""
        with pytest.raises(SystemExit):
            main(['config.txt'])

    def test_cli_accepts_markdown_files(self, tmp_path: Path) -> None:
        """CLI accepts files with .md extension."""
        md_file = tmp_path / "test.md"
        md_file.write_text("# Test file")

        with patch('evaluator.cli.run_evaluation') as mock_orchestrator:
            mock_orchestrator.return_value = None
            result = main([str(md_file)])
            assert result == 0

    def test_cli_validates_problems_are_valid_identifiers(self, tmp_claude_md: Path) -> None:
        """CLI validates that problem names are valid identifiers."""
        with pytest.raises(SystemExit):
            main([str(tmp_claude_md), '--problems', 'invalid-problem-name!'])

    def test_cli_accepts_valid_problem_identifiers(self, tmp_claude_md: Path) -> None:
        """CLI accepts valid problem identifiers."""
        with patch('evaluator.cli.run_evaluation') as mock_orchestrator:
            mock_orchestrator.return_value = None
            result = main([str(tmp_claude_md), '--problems', 'lru_cache,task_manager'])
            assert result == 0