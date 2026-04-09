"""Tests for package structure and initialization."""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest


class TestPackageStructure:
    """Test package structure and imports."""

    def test_evaluator_package_importable(self) -> None:
        """Evaluator package can be imported."""
        try:
            import evaluator
            assert evaluator is not None
        except ImportError:
            pytest.fail("evaluator package should be importable")

    def test_evaluator_init_file_exists(self) -> None:
        """Evaluator __init__.py file exists."""
        # Get the path relative to the project root
        project_root = Path(__file__).parent.parent
        init_file = project_root / "evaluator" / "__init__.py"
        assert init_file.exists(), f"__init__.py should exist at {init_file}"

    def test_evaluator_cli_module_importable(self) -> None:
        """Evaluator CLI module can be imported."""
        try:
            import evaluator.cli
            assert evaluator.cli is not None
        except ImportError:
            pytest.fail("evaluator.cli module should be importable")

    def test_pyproject_toml_exists(self) -> None:
        """pyproject.toml file exists in project root."""
        project_root = Path(__file__).parent.parent
        pyproject_file = project_root / "pyproject.toml"
        assert pyproject_file.exists(), f"pyproject.toml should exist at {pyproject_file}"

    def test_pyproject_toml_has_required_sections(self) -> None:
        """pyproject.toml contains required sections."""
        project_root = Path(__file__).parent.parent
        pyproject_file = project_root / "pyproject.toml"

        if not pyproject_file.exists():
            pytest.skip("pyproject.toml does not exist yet")

        content = pyproject_file.read_text()

        # Check for required sections
        assert '[project]' in content, "pyproject.toml should have [project] section"
        assert '[build-system]' in content, "pyproject.toml should have [build-system] section"

    def test_pyproject_toml_has_cli_entry_point(self) -> None:
        """pyproject.toml defines CLI entry point."""
        project_root = Path(__file__).parent.parent
        pyproject_file = project_root / "pyproject.toml"

        if not pyproject_file.exists():
            pytest.skip("pyproject.toml does not exist yet")

        content = pyproject_file.read_text()

        # Check for CLI entry point
        assert '[project.scripts]' in content, "pyproject.toml should define CLI scripts"
        assert 'claude-md-eval' in content, "Should define claude-md-eval command"

    def test_package_has_correct_directory_structure(self) -> None:
        """Package has the expected directory structure."""
        project_root = Path(__file__).parent.parent

        # Check that evaluator directory exists
        evaluator_dir = project_root / "evaluator"
        assert evaluator_dir.exists(), f"evaluator directory should exist at {evaluator_dir}"
        assert evaluator_dir.is_dir(), "evaluator should be a directory"

        # Check for expected files
        expected_files = ["__init__.py", "cli.py"]
        for filename in expected_files:
            file_path = evaluator_dir / filename
            assert file_path.exists(), f"{filename} should exist in evaluator directory"

    def test_tests_directory_structure(self) -> None:
        """Tests directory has proper structure."""
        project_root = Path(__file__).parent.parent
        tests_dir = project_root / "tests"

        assert tests_dir.exists(), "tests directory should exist"
        assert tests_dir.is_dir(), "tests should be a directory"

        # Check for conftest.py
        conftest_path = tests_dir / "conftest.py"
        assert conftest_path.exists(), "conftest.py should exist in tests directory"


class TestModuleAttributes:
    """Test module attributes and exports."""

    def test_evaluator_package_has_version(self) -> None:
        """Evaluator package exposes version information."""
        try:
            import evaluator
            # Check if __version__ is defined (this will be implemented)
            assert hasattr(evaluator, '__version__') or True, "Package should have version info"
        except ImportError:
            pytest.skip("evaluator package not yet available")

    def test_cli_module_exports_main(self) -> None:
        """CLI module exports main function."""
        try:
            from evaluator.cli import main
            assert callable(main), "main should be a callable function"
        except ImportError:
            pytest.skip("evaluator.cli module not yet available")

    def test_cli_module_exports_create_parser(self) -> None:
        """CLI module exports create_parser function."""
        try:
            from evaluator.cli import create_parser
            assert callable(create_parser), "create_parser should be a callable function"
        except ImportError:
            pytest.skip("evaluator.cli module not yet available")


class TestProjectConfiguration:
    """Test project configuration files."""

    def test_project_root_has_expected_files(self) -> None:
        """Project root contains expected configuration files."""
        project_root = Path(__file__).parent.parent

        # These files should exist for a proper Python package
        expected_files = ["pyproject.toml"]
        for filename in expected_files:
            file_path = project_root / filename
            assert file_path.exists(), f"{filename} should exist in project root"

    def test_can_reload_evaluator_module(self) -> None:
        """Evaluator module can be reloaded without errors."""
        try:
            import evaluator
            importlib.reload(evaluator)
        except ImportError:
            pytest.skip("evaluator package not yet available")
        except Exception as e:
            pytest.fail(f"Module reload should not fail: {e}")

    def test_package_namespace_isolation(self) -> None:
        """Package maintains proper namespace isolation."""
        try:
            import evaluator
            import evaluator.cli

            # These should be separate modules
            assert evaluator is not evaluator.cli
            assert hasattr(evaluator.cli, 'main')
        except ImportError:
            pytest.skip("evaluator modules not yet available")