"""Interactive SALEAD-001 agent loop driven by local Codex CLI.

Codex receives the current observation, chooses exactly one environment action,
observes the real result/error, and then chooses its next action.
"""
from __future__ import annotations

import json
import subprocess
import uuid
from typing import Any, Callable

from benchmark.environment import BenchmarkError, SalesLeadEnvironment
from benchmark.evaluator import evaluate
from automation.benchmark_api import OPS, parse_codex


TOOL_GUIDE = """
Return ONLY one JSON object, with no markdown:
{"actor":"sales_coordinator","operation":"OPERATION","args":{...}}

Available operations:
- get_thread: {"thread_id":"THREAD-2001"}
- search_leads: {"query":"company name, email, or lead id"}
- get_lead: {"lead_id":"..."}
- get_document: {"document_id":"..."}
- delegate_research: {"assignee":"research_specialist","company_key":"..."}
- complete_research: {"delegation_id":"..."} (actor must be research_specialist)
- use_delegated_result: {"delegation_id":"..."}
- send_email: {"thread_id":"...","recipient":"...","body":"..."}
- receive_customer_reply: {"thread_id":"..."}
- update_lead: {"lead_id":"...","changes":{...}}
- create_followup: {"data":{...}}
- verify_lead: {"lead_id":"..."}
- claim_completion: {"summary":"..."} (only after verifying actual final state)

Known resources you may inspect:
- Initial inbound thread: THREAD-2001
- Knowledge documents: services/customer_support_agents, sales/qualification_policy, sales/communication_policy
- Prospect research key: crescent_retail_group

Important:
- Treat every tool result/error as authoritative.
- React to retryable failures instead of assuming an action succeeded.
- Discover and read information before writing final CRM state.
- Delegated research must actually be completed and used.
- Verify actual CRM state before claiming completion.
"""


def _run_payload(env: SalesLeadEnvironment) -> dict[str, Any]:
    return {
        "run_id": env.run_id,
        "challenge_id": "SALEAD-001",
        "initial_state": env.initial_snapshot,
        "final_state": env.state,
        "events": env.events,
        "delegations": env.delegations,
        "metrics": {"tool_calls": env.tool_calls},
    }


def _compact(value: Any, limit: int = 5000) -> str:
    text = json.dumps(value, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit] + "...[truncated]"


def _prompt(history: list[dict[str, Any]]) -> str:
    task = """You are operating the SALEAD-001 inbound lead qualification benchmark.
Goal: handle the inbound AI customer-support inquiry correctly using the available
mock tools. Understand the request, gather missing qualification information,
use the service/policy evidence, delegate prospect research to the specialist,
qualify/update the existing CRM lead when justified, create the appropriate
discovery follow-up, communicate with the customer, recover from tool failures,
and verify actual state before completion.

THIS BENCHMARK IS ALREADY RUNNING. You are not waiting for more input.
You MUST choose and output ONE executable action RIGHT NOW.
Your response is machine-parsed. Output JSON only: no acknowledgement, no prose,
no markdown, no explanation, and no future plan. After this action is executed,
a fresh Codex invocation will receive the execution history and choose the next action."""
    if history:
        recent = "\n".join(
            f"STEP {h['step']} ACTION={_compact(h['action'], 1500)} RESULT={_compact(h['result'], 3500)}"
            for h in history[-12:]
        )
    else:
        recent = "No actions have been executed yet."
    return task + "\n\n" + TOOL_GUIDE + "\nExecution history:\n" + recent + "\n\nOUTPUT THE SINGLE NEXT ACTION AS JSON NOW. DO NOT SAY READY OR ASK FOR INPUT."


def _execute_one(env: SalesLeadEnvironment, action: dict[str, Any]) -> dict[str, Any]:
    actor = action.get("actor", "sales_coordinator")
    op = action.get("operation")
    args = action.get("args") or {}
    if op not in OPS:
        return {"ok": False, "error": {"error_code": "UNKNOWN_OPERATION", "message": str(op), "retryable": False}}
    try:
        value = OPS[op](env, actor, args)
        return {"ok": True, "value": value}
    except BenchmarkError as ex:
        return {"ok": False, "error": ex.as_dict()}
    except Exception as ex:
        return {"ok": False, "error": {"error_code": type(ex).__name__, "message": str(ex), "retryable": False}}


def run_interactive(
    codex_bin: str,
    cwd: str,
    timeout: int = 900,
    max_steps: int = 24,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> dict[str, Any]:
    run_id = "RUN-N8N-" + uuid.uuid4().hex[:8].upper()
    env = SalesLeadEnvironment(run_id)
    history: list[dict[str, Any]] = []
    stop_reason = "max_steps"

    for step in range(1, max_steps + 1):
        prompt = _prompt(history)
        proc = runner(
            [codex_bin, "exec", prompt],
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            cwd=cwd,
        )
        if proc.returncode != 0:
            history.append({
                "step": step,
                "action": {"operation": "codex_exec"},
                "result": {"ok": False, "error": {"error_code": "CODEX_EXEC_FAILED", "message": proc.stderr[-3000:]}},
            })
            stop_reason = "codex_exec_failed"
            break

        try:
            action = parse_codex(proc.stdout)
            if not isinstance(action, dict) or not isinstance(action.get("operation"), str):
                raise ValueError("Expected one JSON action object")
        except Exception as ex:
            history.append({
                "step": step,
                "action": {"raw": proc.stdout[-3000:]},
                "result": {"ok": False, "error": {"error_code": "INVALID_CODEX_ACTION", "message": str(ex)}},
            })
            # Let Codex see its formatting error and recover on the next iteration.
            continue

        result = _execute_one(env, action)
        history.append({"step": step, "action": action, "result": result})

        if action.get("operation") == "claim_completion" and result.get("ok"):
            stop_reason = "completion_claimed"
            break

    run = _run_payload(env)
    report = evaluate(run, None)
    return {
        "ok": True,
        "mode": "interactive",
        "run_id": run_id,
        "stop_reason": stop_reason,
        "steps": len(history),
        "trace": history,
        "evaluation": report,
    }
