"""Golden acceptance against a real model (Groq etc.). Run: make test-live  (needs LLM_API_KEY, LLM_MODEL)."""
import os

import pytest

from artemis.agent.llm import OpenAICompatClient
from artemis.agent.loop import run_case
from artemis.models import EvidenceStatus as ES
from artemis.wiring import build_deps
from tests.conftest import FIXTURES

pytestmark = [pytest.mark.live, pytest.mark.skipif(not os.environ.get("LLM_API_KEY"), reason="no LLM_API_KEY")]


def test_hero_and_twins_take_different_paths_with_right_grades():
    deps = build_deps("fixtures", fixtures_dir=FIXTURES)
    s = deps.settings
    outs = {c: run_case(c, deps, OpenAICompatClient(s.llm_base_url, s.llm_api_key, s.llm_model))
            for c in ("CASE-0007", "CASE-0008", "CASE-0009")}
    assert outs["CASE-0007"].grade.status == ES.VERIFIED and outs["CASE-0007"].allocation.unexplained_paise == 0
    assert outs["CASE-0008"].grade.status == ES.PROBABLE and "request_evidence" in outs["CASE-0008"].tool_path
    assert outs["CASE-0009"].grade.status == ES.CONFLICTING
    assert len({tuple(o.tool_path) for o in outs.values()}) == 3
