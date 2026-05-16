from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def run_history_path() -> Path:
    return FIXTURES / "sample-run-history.csv"


@pytest.fixture
def synth_manifests_dir() -> Path:
    return FIXTURES
