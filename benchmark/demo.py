"""Reference demo runner proving the environment and evaluator work end to end."""
from __future__ import annotations
import argparse
from pathlib import Path
from .environment import BenchmarkError,SalesLeadEnvironment
from .evaluator import evaluate_file
from .judge import write_request
from .report_html import render_files
def run_reference(output_dir:Path,judge_score:float|None=None)->dict:
    env=SalesLeadEnvironment("RUN-REFERENCE-001"); c="sales_coordinator"; r="research_specialist"
    env.get_thread(c,"THREAD-2001"); env.search_leads(c,"Crescent Retail Group"); env.get_lead(c,"LEAD-1007"); env.get_document(c,"services/customer_support_agents"); env.get_document(c,"sales/qualification_policy"); env.get_document(c,"sales/communication_policy")
    d=env.delegate_research(c,r,"crescent_retail_group"); env.complete_research(r,d); env.use_delegated_result(c,d)
    env.send_email(c,"THREAD-2001","noor@crescentretail.example","Thank you for contacting us. To assess the right approach, could you share your approximate budget, preferred pilot timeline, monthly message volume, required languages, current CRM, and human handoff needs?"); env.receive_customer_reply(c,"THREAD-2001")
    changes={"status":"Qualified","qualification":{"service_fit":True,"business_need_identified":True,"authorized_contact":True,"budget_confirmed":True,"budget_meets_threshold":True,"timeline_confirmed":True,"timeline_acceptable":True,"integration_supported":True,"human_handoff_supported":True},"estimated_budget_aed":180000,"timeline_weeks":12,"monthly_message_volume":18000,"requirements":["whatsapp_customer_support","arabic_support","english_support","human_handoff","salesforce_integration"],"crm_platform":"Salesforce","next_action":"discovery_call","owner":"sales_coordinator","notes":["Prospect research completed; customer confirmed budget, volume, and timeline."]}
    try: env.update_lead(c,"LEAD-1007",changes)
    except BenchmarkError as e:
        if not e.retryable: raise
        env.update_lead(c,"LEAD-1007",changes)
    env.create_followup(c,{"lead_id":"LEAD-1007","type":"discovery_call","status":"pending_scheduling","priority":"high","assigned_to":"sales_coordinator","due_at":None,"description":"Discuss requirements, pilot scope, security, and technical feasibility."})
    env.send_email(c,"THREAD-2001","noor@crescentretail.example","Thank you for the details. Your use case appears aligned with our customer-support agent capabilities, including Arabic and English support, human escalation, and potential Salesforce integration. We recommend a discovery call to confirm scope, security, integration feasibility, pricing, and the pilot plan before commitments.")
    env.verify_lead(c,"LEAD-1007"); env.claim_completion(c,"Lead qualified, CRM verified, and discovery follow-up created.")
    run_path=output_dir/"reference-run.json"; report_path=output_dir/"evaluation-report.json"; env.export(run_path); report=evaluate_file(run_path,report_path,judge_score); write_request(run_path,output_dir/"llm-judge-request.json"); render_files(run_path,report_path,output_dir/"evaluation-report.html"); return report
def main():
    p=argparse.ArgumentParser(); p.add_argument("--output-dir",type=Path,default=Path("runs/reference")); p.add_argument("--judge-score",type=float,default=None); a=p.parse_args(); report=run_reference(a.output_dir,a.judge_score); print("SALEAD-001 reference environment run completed."); print(f"Deterministic score: {report['deterministic_score']:.2f}/9.00"); print("LLM-as-a-Judge: pending (1.00 point)" if report["llm_judge_score"] is None else f"LLM-as-a-Judge: {report['llm_judge_score']:.2f}/1.00"); print(f"Current verified score: {report['final_score']:.2f}/10.00"); print(f"Report: {a.output_dir/'evaluation-report.json'}"); print(f"Visual report: {a.output_dir/'evaluation-report.html'}"); print(f"LLM judge request: {a.output_dir/'llm-judge-request.json'}")
if __name__=="__main__":main()
