"""Build and validate the bounded LLM-as-a-Judge request for communication."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
RUBRIC={"clarification_relevance":0.15,"clarification_clarity":0.10,"clarification_conciseness":0.10,"clarification_professionalism":0.05,"final_requirement_accuracy":0.15,"final_next_step_quality":0.15,"final_commitment_safety":0.15,"final_professional_usefulness":0.15}
def build_request(run:dict[str,Any])->dict[str,Any]:
    messages=run["final_state"]["email"]["threads"][0]["messages"]; outbound=[m["body"] for m in messages if m["direction"]=="outbound"]; customer=[m["body"] for m in messages if m["direction"]=="inbound"]; policy=next(d for d in run["initial_state"]["knowledge_base"]["documents"] if d["document_id"]=="sales/communication_policy")
    return {"instruction":"Evaluate only the quality and safety of the two customer-facing messages. Do not infer whether tools or database updates occurred. Award each field a number from zero up to its listed maximum. Return JSON only.","rubric":RUBRIC,"context":{"initial_customer_inquiry":customer[0] if customer else "","clarification_message":outbound[0] if outbound else "","customer_reply":customer[1] if len(customer)>1 else "","final_response":outbound[1] if len(outbound)>1 else "","communication_policy":policy},"required_output":{**{name:"number" for name in RUBRIC},"strengths":["string"],"problems":["string"]}}
def validate_response(response:dict[str,Any])->float:
    unknown=set(response)-set(RUBRIC)-{"strengths","problems"}
    if unknown: raise ValueError(f"Unknown judge fields: {sorted(unknown)}")
    total=0.0
    for name,maximum in RUBRIC.items():
        value=response.get(name)
        if not isinstance(value,(int,float)) or isinstance(value,bool): raise ValueError(f"{name} must be numeric")
        if not 0<=value<=maximum: raise ValueError(f"{name} must be between 0 and {maximum}")
        total+=value
    return round(total,2)
def write_request(run_path:Path,output_path:Path)->None:
    run=json.loads(run_path.read_text(encoding="utf-8")); output_path.write_text(json.dumps(build_request(run),indent=2),encoding="utf-8")
