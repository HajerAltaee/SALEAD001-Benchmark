"""Render a compact HTML benchmark report."""
from __future__ import annotations
import html,json
from pathlib import Path
def render_files(run_path:Path,report_path:Path,output_path:Path)->None:
    run=json.loads(run_path.read_text(encoding="utf-8")); report=json.loads(report_path.read_text(encoding="utf-8"))
    rows="".join(f"<tr><td>{html.escape(c['id'])}</td><td>{html.escape(c['name'])}</td><td>{'PASS' if c['passed'] else 'FAIL'}</td><td>{c['points_awarded']}/{c['points_available']}</td></tr>" for c in report["checks"])
    events="".join(f"<tr><td>{e['sequence']}</td><td>{html.escape(e['actor'])}</td><td>{html.escape(e['operation'])}</td><td>{'Success' if e['success'] else 'Expected failure'}</td></tr>" for e in run["events"])
    before=html.escape(json.dumps(run["initial_state"]["crm"]["leads"][0],indent=2)); after=html.escape(json.dumps(run["final_state"]["crm"]["leads"][0],indent=2))
    doc=f"""<!doctype html><html><head><meta charset='utf-8'><title>SALEAD-001 Evaluation Report</title><style>body{{font-family:Arial,sans-serif;max-width:1100px;margin:40px auto;padding:0 20px}}table{{width:100%;border-collapse:collapse;margin:16px 0}}th,td{{padding:8px;border:1px solid #ddd;text-align:left}}pre{{background:#f5f5f5;padding:14px;overflow:auto}}</style></head><body><h1>SALEAD-001 Benchmark Report</h1><p><b>Verified score:</b> {report['final_score']:.2f}/10 &nbsp; <b>Deterministic:</b> {report['deterministic_score']:.2f}/9 &nbsp; <b>LLM judge:</b> {'Pending' if report['llm_judge_score'] is None else report['llm_judge_score']}</p><p><b>Reference infrastructure run:</b> this proves the environment and evaluator work. It is not yet a live Sapiens4 performance result.</p><h2>Initial state</h2><pre>{before}</pre><h2>Final state</h2><pre>{after}</pre><h2>Execution timeline</h2><table><tr><th>#</th><th>Actor</th><th>Action</th><th>Result</th></tr>{events}</table><h2>Evaluation checks</h2><table><tr><th>ID</th><th>Criterion</th><th>Result</th><th>Points</th></tr>{rows}</table></body></html>"""
    output_path.parent.mkdir(parents=True,exist_ok=True); output_path.write_text(doc,encoding="utf-8")
