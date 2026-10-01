"""Local HTTP wrapper for Codex CLI. No LLM API key is used by n8n."""
from __future__ import annotations
import json, os, subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST=os.getenv("CODEX_SERVICE_HOST","127.0.0.1")
PORT=int(os.getenv("CODEX_SERVICE_PORT","8765"))
TIMEOUT=int(os.getenv("CODEX_TIMEOUT_SECONDS","900"))

class Handler(BaseHTTPRequestHandler):
    def _send(self,status,payload):
        body=json.dumps(payload).encode()
        self.send_response(status); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        self._send(200,{"ok":True,"service":"salead-codex"}) if self.path=="/health" else self._send(404,{"error":"not_found"})
    def do_POST(self):
        if self.path!="/codex/exec": return self._send(404,{"error":"not_found"})
        try:
            length=int(self.headers.get("Content-Length","0")); data=json.loads(self.rfile.read(length) or b"{}"); prompt=data.get("prompt","")
            if not isinstance(prompt,str) or not prompt.strip(): return self._send(400,{"error":"prompt_required"})
            # shell=False: prompt is one argument, not interpolated into a shell command.
            p=subprocess.run(["codex","exec",prompt],capture_output=True,text=True,timeout=TIMEOUT,shell=False)
            self._send(200 if p.returncode==0 else 502,{"ok":p.returncode==0,"exit_code":p.returncode,"stdout":p.stdout,"stderr":p.stderr})
        except subprocess.TimeoutExpired:
            self._send(504,{"ok":False,"error":"codex_timeout"})
        except FileNotFoundError:
            self._send(500,{"ok":False,"error":"codex_not_found","hint":"Install/authenticate Codex CLI and ensure 'codex' is on PATH."})
        except Exception as e:
            self._send(500,{"ok":False,"error":type(e).__name__,"message":str(e)})
    def log_message(self,fmt,*args): print("[codex-service]",fmt%args)

if __name__=="__main__":
    print(f"Codex service listening on http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
