"""Tests for workflow architecture and Snakemake host boundaries."""

import re
from pathlib import Path

FORBIDDEN_HOST_PATTERNS = (
    r"\bsys\.path\b",
    r"^\s*import\s+pandas\b",
    r"^\s*from\s+pandas\b",
    r"^\s*import\s+numpy\b",
    r"^\s*from\s+numpy\b",
    r"^\s*import\s+geopandas\b",
    r"^\s*from\s+geopandas\b",
    r"^\s*import\s+rioxarray\b",
    r"^\s*from\s+rioxarray\b",
    r"^\s*import\s+pandera\b",
    r"^\s*from\s+pandera\b",
    r"^\s*import\s+tclean\b",
    r"^\s*from\s+tclean\b",
)


def test_snakemake_host_code_has_no_module_runtime_dependencies() -> None:
    """Check for runtime dependencies."""
    workflow_files = [Path("workflow/Snakefile"), *Path("workflow/rules").glob("*.smk")]
    violations = []
    for path in workflow_files:
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_HOST_PATTERNS:
            if re.search(pattern, text, flags=re.MULTILINE):
                violations.append(f"{path}: {pattern}")
    assert not violations, (
        "Snakemake host code must not depend on module runtime packages:\n"
        + "\n".join(violations)
    )


def test_removed_legacy_packages_are_not_reintroduced() -> None:
    """Test legacy package removal."""
    assert not Path("workflow/scripts/cleaning").exists()
    assert not Path("workflow/scripts/common").exists()

    violations = []
    for path in Path("workflow/scripts").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if re.search(r"^\s*(?:from|import)\s+cleaning\b", text, re.MULTILINE):
            violations.append(str(path))
        if re.search(r"^\s*(?:from|import)\s+common\b", text, re.MULTILINE):
            violations.append(str(path))
    assert not violations, "Legacy package imports remain:\n" + "\n".join(violations)
