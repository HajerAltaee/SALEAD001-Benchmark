"""Local HTTP wrapper for Codex CLI and SALEAD benchmark. No LLM API key is used by n8n."""
from __future__ import annotations
import json, os, shutil, subprocess, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from automation.benchmark_api import run_actions
from automation.interactive_agent import run_interactive
HOST=os.getenv("CODEX_SERVICE_HOST","0.0.0.0")
PORT=int(os.getenv("CODEX_SERVICE_PORT","8765"))
TIMEOUT=int(os.getenv("CODEX_TIMEOUT_SECONDS","900"))
CODEX_BIN=os.getenv("CODEX_BIN") or shutil.which("codex.cmd") or shutil.which("codex")
class Handler(BaseHTTPRequestHandler):
    def _send(self,status,payload):
        body=json.dumps(payload,ensure_ascii=False).encode()
        self.send_response(status); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body)
    def _body(self):
        length=int(self.headers.get("Content-Length","0")); return json.loads(self.rfile.read(length) or b"{}")
    def do_GET(self):
        self._send(200,{"ok":True,"service":"salead-codex-benchmark"}) if self.path=="/health" else self._send(404,{"error":"not_found"})
    def do_POST(self):
        try:
            data=self._body()
            if self.path=="/codex/exec":
                prompt=data.get("prompt","")
                if not isinstance(prompt,str) or not prompt.strip(): return self._send(400,{"error":"prompt_required"})
                if not CODEX_BIN: raise FileNotFoundError("Codex CLI launcher was not found")
                p=subprocess.run([CODEX_BIN,"exec",prompt],capture_output=True,text=True,timeout=TIMEOUT,shell=False,cwd=str(ROOT))
                return self._send(200 if p.returncode==0 else 502,{"ok":p.returncode==0,"exit_code":p.returncode,"stdout":p.stdout,"stderr":p.stderr})
            if self.path=="/benchmark/interactive-run":
                if not CODEX_BIN: raise FileNotFoundError("Codex CLI launcher was not found")
                max_steps=data.get("max_steps",24)
                if not isinstance(max_steps,int) or max_steps<1 or max_steps>40: return self._send(400,{"error":"max_steps_must_be_1_to_40"})
                result=run_interactive(CODEX_BIN,str(ROOT),TIMEOUT,max_steps)
                return self._send(200,result)
            if self.path=="/benchmark/run":
                output=data.get("codex_output","")
                if not isinstance(output,str) or not output.strip(): return self._send(400,{"error":"codex_output_required"})
                return self._send(200,run_actions(output))
            return self._send(404,{"error":"not_found"})
        except subprocess.TimeoutExpired: self._send(504,{"ok":False,"error":"codex_timeout"})
        except FileNotFoundError: self._send(500,{"ok":False,"error":"codex_not_found"})
        except Exception as e: self._send(500,{"ok":False,"error":type(e).__name__,"message":str(e)})
    def log_message(self,fmt,*args): print("[salead-service]",fmt%args)
if __name__=="__main__":
    print(f"SALEAD service listening on http://{HOST}:{PORT}")
    print(f"Codex executable: {CODEX_BIN or 'NOT FOUND'}")
    ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
