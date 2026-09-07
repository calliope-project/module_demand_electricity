"""Set of standard Modelblocks tests.

PLEASE ENSURE THIS SET OF MINIMAL TESTS WORKS BEFORE PUBLISHING YOUR MODULE.
Contents may be updated in future template updates.
"""

import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest
from clio_tools.data_module import ModuleInterface


@pytest.fixture(scope="module")
def pixi_platforms(module_path) -> list[str]:
    """Pixi platforms defined for this project."""
    with (module_path / "pixi.toml").open("rb") as pixi_config:
        return tomllib.load(pixi_config)["workspace"]["platforms"]


def test_snakemake_environments(module_path, pixi_platforms, tmp_path):
    """All Snakemake environment files should be based on pixi counterparts."""
    env_dir = module_path / "workflow/envs"
    env_files = sorted(env_dir.glob("*.yaml"))
    assert env_files, f"No conda environments found in {module_path}."

    for env_file in env_files:
        env_name = env_file.stem

        output_dir = tmp_path / env_name
        subprocess.run(
            ["pixi", "run", "export-snakemake-env", env_name, str(output_dir)],
            check=True,
            cwd=module_path,
        )

        generated_yaml = output_dir / env_file.name
        assert generated_yaml.read_text() == env_file.read_text()

        for platform in pixi_platforms:
            pin_file = env_dir / f"{env_name}.{platform}.pin.txt"
            assert pin_file.exists(), f"{env_name} has no conda pins for {platform}"


@pytest.fixture(scope="module")
def integration_path(
    europe_small_shapes: Path, user_path: Path, module_path: Path, token_entsoe: Path
):
    """Ensures the minimal integration test is ready."""
    integration_dir = Path(module_path / "tests/integration")

    if integration_dir.exists():
        shutil.rmtree(integration_dir / "resources", ignore_errors=True)
        shutil.rmtree(integration_dir / "results/", ignore_errors=True)

    user_integ_dir = integration_dir / "resources/user"

    files_to_copy = {
        europe_small_shapes: Path("EUROPE_S_C1_ADM1/shapes.parquet"),
        token_entsoe: Path("token_entsoe.txt"),
        user_path / "external_profiles/alb_external_test.csv": Path(
            "external_profiles/alb_external_test.csv"
        ),
    }

    for source_file, destination in files_to_copy.items():
        destination_file = user_integ_dir / destination
        destination_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(source_file, destination_file)

    return integration_dir


def test_interface_file(module_path):
    """The interfacing file should be correct."""
    assert ModuleInterface.from_yaml(module_path / "INTERFACE.yaml")


@pytest.mark.parametrize(
    "file",
    [
        "AUTHORS",
        "CITATION.cff",
        "INTERFACE.yaml",
        "LICENSE",
        "README.md",
        "config/config.yaml",
        "workflow/internal/config.schema.yaml",
        "tests/integration/Snakefile",
    ],
)
def test_standard_file_existance(module_path, file):
    """Check that a minimal set of files used for documentation are present."""
    assert Path(module_path / file).exists()


def test_snakemake_all_failure(module_path):
    """The snakemake 'all' rule should return an error by default."""
    process = subprocess.run(
        "snakemake --cores 1", shell=True, cwd=module_path, capture_output=True
    )
    assert "INVALID" in str(process.stderr)


def test_snakemake_integration_testing(integration_path):
    """Run a light-weight test simulating someone using this module."""
    assert subprocess.run(
        "snakemake --use-conda --cores 1", shell=True, check=True, cwd=integration_path
    )
