from pathlib import Path

import pytest

from artemis.wiring import build_deps

FIXTURES = str(Path(__file__).resolve().parent.parent / "fixtures")


@pytest.fixture
def deps():
    return build_deps("fixtures", fixtures_dir=FIXTURES)
