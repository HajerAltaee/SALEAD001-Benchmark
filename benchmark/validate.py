"""Validate the SALEAD-001 contract before implementing runtime services."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
def load_json(relative_path:str)->dict[str,Any]:
    with (ROOT/relative_path).open("r",encoding="utf-8") as h:return json.load(h)
def require(condition:bool,message:str)->None:
    if not condition:raise ValueError(message)
def validate_challenge(c):
    require(c["challenge_id"]=="SALEAD-001","Unexpected challenge ID"); require(c["score_scale"]==[0,10],"Score scale must be 0-10"); require(c["system_under_test"]=="agent_harness","Invalid SUT boundary"); require(len(c["available_tools"])==5,"Expected five environment tools"); require("golden_state" not in c,"Challenge leaks evaluator-only state"); require("scoring_weights" not in c,"Challenge leaks scoring weights")
def validate_initial_state(s):
    leads=s["crm"]["leads"]; require(len(leads)==1,"Fixture must contain exactly one lead"); lead=leads[0]; require(lead["lead_id"]=="LEAD-1007","Required lead is missing"); require(lead["status"]=="New","Lead must begin as New"); require(lead["estimated_budget_aed"] is None,"Budget must initially be unknown"); require(lead["timeline_weeks"] is None,"Timeline must initially be unknown"); require(lead["monthly_message_volume"] is None,"Volume must initially be unknown"); require(s["followups"]==[],"No follow-up may exist initially"); require(len(s["email"]["threads"])==1,"Expected one email thread"); r=s["prospect_research"]["crescent_retail_group"]; require(r["monthly_message_volume"] is None,"Research fixture must not leak the customer's exact message volume"); require(r["budget_aed"] is None,"Research fixture must not leak the customer's budget")
def validate_golden(g,i):
    e=g["required_final_state"]; lead=e["crm"]["lead"]; require(lead["lead_id"]=="LEAD-1007","Golden state targets wrong lead"); require(lead["status"]=="Qualified","Golden lead must be Qualified"); require(lead["estimated_budget_aed"]==180000,"Golden budget is incorrect"); require(lead["timeline_weeks"]==12,"Golden timeline is incorrect"); require(lead["monthly_message_volume"]==18000,"Golden volume is incorrect"); require(e["followups"]["count"]==1,"Exactly one follow-up is required"); required={"lead_id","company","contact_name","contact_title","email","source","created_at"}; require(required<=set(g["protected_fields"]),"Golden state omits protected fields"); require(i["failure_injection"]["crm_qualified_update_failures"]==1,"The benchmark requires exactly one injected CRM failure")
def main():
    c=load_json("challenge/salead-001.json"); i=load_json("fixtures/initial_state.json"); g=load_json("golden/salead-001.json"); validate_challenge(c); print("SALEAD-001 configuration is valid."); validate_initial_state(i); print("Initial fixtures are valid."); validate_golden(g,i); print("Golden state is valid."); print("Foundation validation passed.")
if __name__=="__main__":main()
