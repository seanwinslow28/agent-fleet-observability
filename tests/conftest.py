import pytest

from dashboard import fixture


@pytest.fixture
def brain(tmp_path):
    return fixture.build(tmp_path / "brain")
