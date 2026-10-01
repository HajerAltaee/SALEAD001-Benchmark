"""Local HTTP wrapper for Codex CLI and SALEAD benchmark. No LLM API key is used by n8n.

V3 exposes elementary benchmark operations so n8n owns the agent loop,
branching, retries, and completion decision instead of hiding them in Python.
"""
from __future__ import annotations
import json, os, shutil, subprocess, sys, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))

from benchmark.environment import BenchmarkError, SalesLeadEnvironment
from benchmark.evaluator import evaluate
from automation.benchmark_api import OPS, run_actions
from automation.interactive_agent import run_interactive

HOST=os.getenv("CODEX_SERVICE_HOST","0.0.0.0")
PORT=int(os.getenv("CODEX_SERVICE_PORT","8765"))
TIMEOUT=int(os.getenv("CODEX_TIMEOUT_SECONDS","900"))
CODEX_BIN=os.getenv("CODEX_BIN") or shutil.which("codex.cmd") or shutil.which("codex")

# In-memory benchmark sessions. n8n owns orchestration; this service only keeps
# the mock SALEAD environment alive between elementary HTTP calls.
SESSIONS={}

def _run_payload(env):
    return {
        "run_id":env.run_id,
        "challenge_id":"SALEAD-001",
        "initial_state":env.initial_snapshot,
        "final_state":env.state,
        "events":env.events,
        "delegations":env.delegations,
        "metrics":{"tool_calls":env.tool_calls},
    }

def _execute_action(env, action):
    actor=action.get("actor","sales_coordinator")
    op=action.get("operation")
    args=action.get("args") or {}
    if op not in OPS:
        return {"ok":False,"error":{"error_code":"UNKNOWN_OPERATION","message":str(op),"retryable":False}}
    try:
        return {"ok":True,"value":OPS[op](env,actor,args)}
    except BenchmarkError as ex:
        return {"ok":False,"error":ex.as_dict()}
    except Exception as ex:
        return {"ok":False,"error":{"error_code":type(ex).__name__,"message":str(ex),"retryable":False}}

class Handler(BaseHTTPRequestHandler):
    def _send(self,status,payload):
        body=json.dumps(payload,ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length=int(self.headers.get("Content-Length","0"))
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self):
        self._send(200,{"ok":True,"service":"salead-codex-benchmark","active_runs":len(SESSIONS)}) if self.path=="/health" else self._send(404,{"error":"not_found"})

    def do_POST(self):
        try:
            data=self._body()

            if self.path=="/codex/exec":
                prompt=data.get("prompt","")
                if not isinstance(prompt,str) or not prompt.strip():
                    return self._send(400,{"error":"prompt_required"})
                if not CODEX_BIN:
                    raise FileNotFoundError("Codex CLI launcher was not found")
                schema_path=ROOT/"automation"/"codex_action_schema.json"
                command=[CODEX_BIN,"exec"]
                if data.get("output_schema")=="salead_action":
                    command.extend(["--output-schema",str(schema_path)])
                command.append(prompt)
                p=subprocess.run(command,capture_output=True,text=True,timeout=TIMEOUT,shell=False,cwd=str(ROOT))
                # context is an opaque n8n-owned object echoed back so workflow
                # state remains visible between elementary nodes.
                return self._send(200 if p.returncode==0 else 502,{
                    "ok":p.returncode==0,
                    "exit_code":p.returncode,
                    "stdout":p.stdout,
                    "stderr":p.stderr,
                    "context":data.get("context"),
                })

            # V3 elementary API: n8n owns the loop.
            if self.path=="/benchmark/start":
                run_id="RUN-N8N-"+uuid.uuid4().hex[:8].upper()
                SESSIONS[run_id]=SalesLeadEnvironment(run_id)
                return self._send(200,{"ok":True,"run_id":run_id,"challenge_id":"SALEAD-001"})

            if self.path=="/benchmark/action":
                run_id=data.get("run_id")
                action=data.get("action")
                env=SESSIONS.get(run_id)
                if env is None:
                    return self._send(404,{"ok":False,"error":"run_not_found","run_id":run_id})
                if not isinstance(action,dict):
                    return self._send(400,{"ok":False,"error":"action_object_required"})
                observation=_execute_action(env,action)
                return self._send(200,{
                    "ok":True,
                    "run_id":run_id,
                    "action":action,
                    "observation":observation,
                    "tool_calls":env.tool_calls,
                    "context":data.get("context"),
                })

            if self.path=="/benchmark/evaluate":
                run_id=data.get("run_id")
                env=SESSIONS.get(run_id)
                if env is None:
                    return self._send(404,{"ok":False,"error":"run_not_found","run_id":run_id})
                report=evaluate(_run_payload(env),None)
                return self._send(200,{
                    "ok":True,
                    "run_id":run_id,
                    "evaluation":report,
                    "events":env.events,
                    "tool_calls":env.tool_calls,
                    "context":data.get("context"),
                })

            # V2 kept as a comparison/fallback.
            if self.path=="/benchmark/interactive-run":
                if not CODEX_BIN:
                    raise FileNotFoundError("Codex CLI launcher was not found")
                max_steps=data.get("max_steps",24)
                if not isinstance(max_steps,int) or max_steps<1 or max_steps>40:
                    return self._send(400,{"error":"max_steps_must_be_1_to_40"})
                return self._send(200,run_interactive(CODEX_BIN,str(ROOT),TIMEOUT,max_steps))

            # V1 kept as a comparison/fallback.
            if self.path=="/benchmark/run":
                output=data.get("codex_output","")
                if not isinstance(output,str) or not output.strip():
                    return self._send(400,{"error":"codex_output_required"})
                return self._send(200,run_actions(output))

            return self._send(404,{"error":"not_found"})
        except subprocess.TimeoutExpired:
            self._send(504,{"ok":False,"error":"codex_timeout"})
        except FileNotFoundError:
            self._send(500,{"ok":False,"error":"codex_not_found"})
        except Exception as e:
            self._send(500,{"ok":False,"error":type(e).__name__,"message":str(e)})

    def log_message(self,fmt,*args):
        print("[salead-service]",fmt%args)

if __name__=="__main__":
    print(f"SALEAD service listening on http://{HOST}:{PORT}")
    print(f"Codex executable: {CODEX_BIN or 'NOT FOUND'}")
    print("V3 elementary endpoints: /benchmark/start, /benchmark/action, /benchmark/evaluate")
    ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
