# n8n automation

This layer automates SALEAD-001 without putting an LLM API key in an n8n LLM node.

## Architecture

n8n -> local HTTP service -> `codex exec PROMPT` -> result -> benchmark evaluator/report

The local service uses the already authenticated Codex CLI on the machine. It invokes Codex with `shell=False`; the prompt is passed as one process argument rather than interpolated into a shell command.

## 1. Verify Codex

In PowerShell:

```powershell
codex --version
codex exec "Reply with exactly: CODEX_OK"
```

## 2. Start the local service

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File automation/run_codex_service.ps1
```

Leave that terminal open. Test in another PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/health
```

## 3. n8n

The first workflow should be deliberately small:

Manual Trigger
-> Set benchmark prompt
-> HTTP POST to /codex/exec
-> inspect Codex output

Once this bridge works, connect the existing SALEAD environment/evaluator around it. Do not replace the benchmark logic with n8n; n8n is the orchestrator.

### Important networking note

If n8n itself runs in Docker, `127.0.0.1` inside n8n is the container, not Windows. Use `http://host.docker.internal:8765/codex/exec` and start the service on a host interface reachable by the container. Keep it local/private; do not expose this unauthenticated command wrapper to the public internet.
