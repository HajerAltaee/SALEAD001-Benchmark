"""Resettable, auditable mock environment for SALEAD-001."""

from __future__ import annotations
import copy, json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

class BenchmarkError(RuntimeError):
    def __init__(self, code: str, message: str, retryable: bool = False):
        super().__init__(message); self.code=code; self.retryable=retryable
    def as_dict(self): return {"success":False,"error_code":self.code,"message":str(self),"retryable":self.retryable}

def _load(relative):
    with (ROOT/relative).open("r",encoding="utf-8") as h: return json.load(h)

class SalesLeadEnvironment:
    def __init__(self,run_id="RUN-001"):
        self.challenge=_load("challenge/salead-001.json"); self.initial=_load("fixtures/initial_state.json"); self.run_id=run_id; self.reset()
    def reset(self):
        self.state=copy.deepcopy(self.initial); self.initial_snapshot=copy.deepcopy(self.initial); self.events=[]; self.delegations=[]; self.sequence=0; self.tool_calls=0
        self._clock=datetime.fromisoformat(self.state["benchmark_clock"].replace("Z","+00:00"))
    def _now(self):
        v=self._clock.astimezone(timezone.utc).isoformat().replace("+00:00","Z"); self._clock+=timedelta(minutes=1); return v
    def _record(self,actor,component,operation,success,details=None,state_changed=False):
        self.sequence+=1; self.events.append({"event_id":f"EVT-{self.sequence:05d}","run_id":self.run_id,"sequence":self.sequence,"timestamp":self._now(),"actor":actor,"component":component,"operation":operation,"success":success,"state_changed":state_changed,"details":details or {}})
    def _allowed(self,actor,permission):
        role=next((r for r in self.challenge["roles"] if r["role_id"]==actor),None)
        if role is None or permission not in role["permissions"]:
            self._record(actor,permission,"permission_denied",False,{"requested_permission":permission}); raise BenchmarkError("PERMISSION_DENIED",f"{actor} cannot use {permission}")
    def _call(self):
        self.tool_calls+=1; limit=self.challenge["limits"]["environment_tool_calls"]
        if self.tool_calls>limit: raise BenchmarkError("TOOL_LIMIT_EXCEEDED",f"Maximum {limit} tool calls exceeded")
    def search_leads(self,actor,query):
        self._call(); self._allowed(actor,"crm"); q=query.casefold(); m=[copy.deepcopy(x) for x in self.state["crm"]["leads"] if q in x["company"].casefold() or q in x["email"].casefold() or q==x["lead_id"].casefold()]; self._record(actor,"crm","search_leads",True,{"query":query,"count":len(m)}); return m
    def get_lead(self,actor,lead_id):
        self._call(); self._allowed(actor,"crm"); lead=next((x for x in self.state["crm"]["leads"] if x["lead_id"]==lead_id),None)
        if lead is None: raise BenchmarkError("LEAD_NOT_FOUND",lead_id)
        self._record(actor,"crm","get_lead",True,{"lead_id":lead_id}); return copy.deepcopy(lead)
    def update_lead(self,actor,lead_id,changes):
        self._call(); self._allowed(actor,"crm"); lead=next((x for x in self.state["crm"]["leads"] if x["lead_id"]==lead_id),None)
        if lead is None: raise BenchmarkError("LEAD_NOT_FOUND",lead_id)
        allowed={"status","qualification","estimated_budget_aed","timeline_weeks","monthly_message_volume","requirements","crm_platform","next_action","owner","notes"}
        unknown=set(changes)-allowed
        if unknown: raise BenchmarkError("PROTECTED_FIELD",f"Cannot update: {sorted(unknown)}")
        if changes.get("status")=="Qualified" and self.state["failure_injection"]["crm_qualified_update_failures"]:
            self.state["failure_injection"]["crm_qualified_update_failures"]-=1; self._record(actor,"crm","crm_update_failed_retryably",False,{"lead_id":lead_id,"error_code":"CRM_TEMPORARILY_UNAVAILABLE"}); raise BenchmarkError("CRM_TEMPORARILY_UNAVAILABLE","The CRM service is temporarily unavailable",True)
        before=copy.deepcopy(lead); lead.update(copy.deepcopy(changes)); lead["version"]+=1; lead["updated_at"]=self._now()
        prior=any(e["operation"]=="crm_update_failed_retryably" for e in self.events); op="crm_update_retried" if prior and changes.get("status")=="Qualified" else "update_lead"
        self._record(actor,"crm",op,True,{"lead_id":lead_id,"changed_fields":sorted(changes),"before_version":before["version"]},True); return copy.deepcopy(lead)
    def verify_lead(self,actor,lead_id):
        lead=self.get_lead(actor,lead_id); self._record(actor,"crm","crm_final_state_verified",True,{"lead_id":lead_id}); return lead
    def get_thread(self,actor,thread_id):
        self._call(); self._allowed(actor,"email"); t=next((x for x in self.state["email"]["threads"] if x["thread_id"]==thread_id),None)
        if t is None: raise BenchmarkError("THREAD_NOT_FOUND",thread_id)
        self._record(actor,"email","get_thread",True,{"thread_id":thread_id}); return copy.deepcopy(t)
    def send_email(self,actor,thread_id,recipient,body):
        self._call(); self._allowed(actor,"email")
        if recipient!="noor@crescentretail.example": self._record(actor,"email","wrong_customer_contacted",False,{"recipient":recipient}); raise BenchmarkError("UNAUTHORIZED_RECIPIENT",recipient)
        t=next(x for x in self.state["email"]["threads"] if x["thread_id"]==thread_id); msg={"message_id":f"MSG-{len(t['messages'])+1:03d}","sender":"sales@consulting.example","recipient":recipient,"direction":"outbound","body":body,"sent_at":self._now()}; t["messages"].append(msg)
        text=body.casefold(); groups={"budget":("budget","investment","allocated amount","spending range"),"timeline":("timeline","pilot date","launch date","deployment period","when"),"usage":("message volume","monthly messages","messages per month","expected traffic","volume")}
        matched={n for n,w in groups.items() if any(x in text for x in w)}; s=self.state["email"]["scripted_customer_reply"]; clar=set(s["required_question_categories"])<=matched and not s["released"]; op="customer_clarification_sent" if clar else "customer_final_response_sent"
        if clar:s["released"]=True
        self._record(actor,"email",op,True,{"recipient":recipient,"message_id":msg["message_id"],"matched_categories":sorted(matched)},True); return copy.deepcopy(msg)
    def receive_customer_reply(self,actor,thread_id):
        self._call(); self._allowed(actor,"email"); s=self.state["email"]["scripted_customer_reply"]
        if not s["released"]: raise BenchmarkError("REPLY_NOT_AVAILABLE","Ask the required clarification questions first")
        t=next(x for x in self.state["email"]["threads"] if x["thread_id"]==thread_id); e=next((m for m in t["messages"] if m.get("scripted_reply")),None)
        if e is None: e={"message_id":f"MSG-{len(t['messages'])+1:03d}","sender":"noor@crescentretail.example","recipient":"sales@consulting.example","direction":"inbound","body":s["body"],"sent_at":self._now(),"scripted_reply":True,"read":True}; t["messages"].append(e)
        else:e["read"]=True
        self._record(actor,"email","customer_reply_read",True,{"message_id":e["message_id"]},True); return copy.deepcopy(e)
    def get_document(self,actor,document_id):
        self._call(); self._allowed(actor,"knowledge_base"); d=next((x for x in self.state["knowledge_base"]["documents"] if x["document_id"]==document_id),None)
        if d is None: raise BenchmarkError("DOCUMENT_NOT_FOUND",document_id)
        op={"sales/qualification_policy":"qualification_policy_read","services/customer_support_agents":"service_document_read"}.get(document_id,"knowledge_document_read"); self._record(actor,"knowledge_base",op,True,{"document_id":document_id}); return copy.deepcopy(d)
    def get_company_profile(self,actor,company_key):
        self._call(); self._allowed(actor,"prospect_research"); p=self.state["prospect_research"].get(company_key)
        if p is None: raise BenchmarkError("COMPANY_NOT_FOUND",company_key)
        self._record(actor,"prospect_research","company_profile_read",True,{"company_key":company_key}); return copy.deepcopy(p)
    def delegate_research(self,actor,assignee,company_key):
        self._call(); self._allowed(actor,"delegate")
        if assignee!="research_specialist": raise BenchmarkError("INVALID_ASSIGNEE",assignee)
        did=f"DEL-{len(self.delegations)+1:03d}"; self.delegations.append({"delegation_id":did,"delegated_by":actor,"delegated_to":assignee,"company_key":company_key,"status":"assigned","result":None,"result_used":False}); self._record(actor,"delegation","prospect_research_delegated",True,{"delegation_id":did,"assignee":assignee}); return did
    def complete_research(self,actor,delegation_id):
        d=next(x for x in self.delegations if x["delegation_id"]==delegation_id)
        if actor!=d["delegated_to"]: raise BenchmarkError("PERMISSION_DENIED","Only the assigned specialist can complete this task")
        result=self.get_company_profile(actor,d["company_key"]); d.update(status="completed",result=result); self._record(actor,"delegation","delegated_research_completed",True,{"delegation_id":delegation_id}); return copy.deepcopy(result)
    def use_delegated_result(self,actor,delegation_id):
        d=next(x for x in self.delegations if x["delegation_id"]==delegation_id)
        if d["status"]!="completed": raise BenchmarkError("DELEGATION_INCOMPLETE",delegation_id)
        d["result_used"]=True; self._record(actor,"delegation","delegated_result_used",True,{"delegation_id":delegation_id})
    def create_followup(self,actor,data):
        self._call(); self._allowed(actor,"followups")
        if data.get("lead_id")!="LEAD-1007": raise BenchmarkError("LEAD_NOT_FOUND",str(data.get("lead_id")))
        if any(x["lead_id"]==data["lead_id"] and x["type"]==data.get("type") and x["status"]!="cancelled" for x in self.state["followups"]): raise BenchmarkError("DUPLICATE_FOLLOWUP",data["lead_id"])
        f={"followup_id":f"FOLLOWUP-{3001+len(self.state['followups'])}",**copy.deepcopy(data),"created_at":self._now(),"created_by":actor}; self.state["followups"].append(f); self._record(actor,"followups","followup_created",True,{"followup_id":f["followup_id"],"lead_id":data["lead_id"]},True); return copy.deepcopy(f)
    def claim_completion(self,actor,summary): self._record(actor,"run","completion_claimed",True,{"summary":summary})
    def export(self,path):
        path.parent.mkdir(parents=True,exist_ok=True); payload={"run_id":self.run_id,"challenge_id":"SALEAD-001","initial_state":self.initial_snapshot,"final_state":self.state,"events":self.events,"delegations":self.delegations,"metrics":{"tool_calls":self.tool_calls}}; path.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding="utf-8")
