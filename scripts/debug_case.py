"""Run one case on the live LLM and print the trace: python -m scripts.debug_case CASE-0007 (use --env-file .env)."""
import sys

from artemis.agent.llm import OpenAICompatClient
from artemis.agent.loop import run_case
from artemis.wiring import build_deps

sys.stdout.reconfigure(encoding="utf-8")
case = sys.argv[1] if len(sys.argv) > 1 else "CASE-0007"
deps = build_deps()
s = deps.settings
out = run_case(case, deps, OpenAICompatClient(s.llm_base_url, s.llm_api_key, s.llm_model))
print("stop:", out.stop_reason, "| grade:", out.grade.status if out.grade else None, "| state:", out.final_state)
print("narrative:", out.narrative)
for c in deps.store.tool_calls(out.run_id):
    print(f"  step {c.step} {c.tool_name} {str(c.args_json)[:120]} -> {str(c.result_json)[:420]}")
