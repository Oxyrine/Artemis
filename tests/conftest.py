from pathlib import Path

import pytest

from artemis.wiring import build_deps

FIXTURES = str(Path(__file__).resolve().parent.parent / "fixtures")
HERO = ["CASE-0007", "CASE-0008", "CASE-0009"]  # hero case + its Probable and Conflicting twins (both backends)


def make(backend: str, store=None):
    return build_deps(backend, store=store, fixtures_dir=FIXTURES)


@pytest.fixture(params=["fixtures", "real"])  # every Lane B test runs on the fakes AND on Lane A's real core
def backend(request):
    return request.param


@pytest.fixture
def deps(backend):
    return make(backend)
