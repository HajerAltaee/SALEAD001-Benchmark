$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
python automation/codex_service.py
