"""HTTP API for executing SALEAD-001 structured agent actions and evaluating actual state."""
from __future__ import annotations
import json
from typing import Any
from benchmark.environment import BenchmarkError, SalesLeadEnvironment
from benchmark.evaluator import evaluate

OPS = {
    "get_thread": lambda e,a,x: e.get_thread(a, x["thread_id"]),
    "search_leads": lambda e,a,x: e.search_leads(a, x["query"]),
    "get_lead": lambda e,a,x: e.get_lead(a, x["lead_id"]),
    "get_document": lambda e,a,x: e.get_document(a, x["document_id"]),
    "delegate_research": lambda e,a,x: e.delegate_research(a, x["assignee"], x["company_key"]),
    "complete_research": lambda e,a,x: e.complete_research(a, x["delegation_id"]),
    "use_delegated_result": lambda e,a,x: e.use_delegated_result(a, x["delegation_id"]),
    "send_email": lambda e,a,x: e.send_email(a, x["thread_id"], x["recipient"], x["body"]),
    "receive_customer_reply": lambda e,a,x: e.receive_customer_reply(a, x["thread_id"]),
    "update_lead": lambda e,a,x: e.update_lead(a, x["lead_id"], x["changes"]),
    "create_followup": lambda e,a,x: e.create_followup(a, x["data"]),
    "verify_lead": lambda e,a,x: e.verify_lead(a, x["lead_id"]),
    "claim_completion": lambda e,a,x: e.claim_completion(a, x["summary"]),
}
def parse_codex(text:str)->dict[str,Any]:
    text=text.strip()
    if text.startswith("```"):
        lines=text.splitlines()
        text="\n".join(lines[1:-1])
        if text.lstrip().startswith("json"): text=text.lstrip()[4:].lstrip()
    return json.loads(text)
def run_actions(codex_output:str)->dict[str,Any]:
    plan=parse_codex(codex_output); actions=plan.get("actions")
    if not isinstance(actions,list): raise ValueError("Codex output must contain an actions array")
    env=SalesLeadEnvironment("RUN-N8N-001"); results=[]
    aliases={}
    for i,item in enumerate(actions,1):
        actor=item.get("actor","sales_coordinator"); op=item.get("operation"); args=item.get("args") or {}
        # Allow Codex to refer to the first delegation symbolically.
        if args.get("delegation_id")=="DEL-001" and "DEL-001" in aliases: args["delegation_id"]=aliases["DEL-001"]
        try:
            if op not in OPS: raise BenchmarkError("UNKNOWN_OPERATION",str(op))
            value=OPS[op](env,actor,args)
            if op=="delegate_research": aliases["DEL-001"]=value
            results.append({"index":i,"operation":op,"ok":True,"result":value})
        except BenchmarkError as ex:
            results.append({"index":i,"operation":op,"ok":False,"error":ex.as_dict()})
            if not ex.retryable: break
        except Exception as ex:
            results.append({"index":i,"operation":op,"ok":False,"error":{"error_code":type(ex).__name__,"message":str(ex),"retryable":False}})
            break
    run={"run_id":env.run_id,"challenge_id":"SALEAD-001","initial_state":env.initial_snapshot,"final_state":env.state,"events":env.events,"delegations":env.delegations,"metrics":{"tool_calls":env.tool_calls}}
    report=evaluate(run,None)
    return {"ok":True,"run_id":env.run_id,"action_results":results,"evaluation":report}
