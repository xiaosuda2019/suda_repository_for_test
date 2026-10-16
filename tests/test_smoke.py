"""Smoke tests for this repository.

The repo currently holds no application code, so these tests verify only the
baseline facts the CI workflow promises: a supported Python version and a
present README. Replace or extend them once real code lands.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_python_version_is_at_least_3_12():
    assert sys.version_info[:2] >= (3, 12), f"expected Python >= 3.12, got {sys.version}"


def test_readme_exists_and_is_not_empty():
    readme = REPO_ROOT / "README.md"
    assert readme.is_file(), f"missing README.md at {readme}"
    assert readme.read_text(encoding="utf-8").strip(), "README.md is empty"
