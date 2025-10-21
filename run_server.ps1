Param(
  [string]$Port = "8000",
  [string]$EnvName = ".venv"
)

# Fail fast on errors
$ErrorActionPreference = "Stop"

# Always run from the script's folder (project root)
Set-Location -Path $PSScriptRoot

# --- 0) Optional: ensure scripts can run (user scope). Comment out if org policy forbids.
# If ((Get-ExecutionPolicy) -in @('Restricted', 'Undefined')) { Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force }

# Only install inside an active venv (safety net)
$env:PIP_REQUIRE_VIRTUALENV = "true"

# --- 1) Create venv if missing ---
if (!(Test-Path $EnvName)) {
  Write-Host "📦 Creating virtual environment: $EnvName"
  python -m venv $EnvName
}

# --- 2) Activate venv ---
Write-Host "✅ Activating virtual environment..."
. "$EnvName\Scripts\Activate.ps1"

# Assert venv active
if (-not $env:VIRTUAL_ENV) {
  Write-Error "❌ Virtual environment not active. Aborting."
  exit 1
}

# --- 3) Environment info (helps debug path/import issues) ---
python - << 'PY'
import sys, site, platform, os, pathlib
print("VENV OK")
print("Python:", sys.executable)
print("Base  :", sys.base_prefix)
print("Venv  :", sys.prefix)
print("Sites :", site.getsitepackages())
print("PWD   :", pathlib.Path().resolve())
PY

# --- 4) Upgrade pip & install deps ---
python -m pip install --upgrade pip
if (Test-Path "requirements.txt") {
  pip install -r requirements.txt
} else {
  # Minimal deps for this app if requirements.txt is missing
  pip install fastapi uvicorn openai pydantic pydantic-settings python-dotenv
}

# --- 5) Ensure output directories exist ---
foreach ($d in @("out","bucket","outputs")) {
  if (!(Test-Path $d)) { New-Item -ItemType Directory -Path $d | Out-Null }
}

# --- 6) Verify OPENAI_API_KEY is available; try to load from .env if not ---
function MaskTail([string]$s, [int]$n=4) {
  if (-not $s) { return "<MISSING>" }
  $len = $s.Length
  return ("*" * [Math]::Max(0, $len - $n)) + $s.Substring($len - $n, $n)
}

if (-not $env:OPENAI_API_KEY) {
  Write-Host "⚠️  OPENAI_API_KEY not found in current environment. Attempting to load from .env..."
  if (Test-Path ".env") {
    # Parse .env (simple key=value lines)
    Get-Content ".env" | ForEach-Object {
      if ($_ -match "^\s*OPENAI_API_KEY\s*=\s*(.+)\s*$") {
        $env:OPENAI_API_KEY = $matches[1].Trim()
      }
    }
    if ($env:OPENAI_API_KEY) {
      Write-Host "🔐 Loaded OPENAI_API_KEY from .env (masked): $(MaskTail $env:OPENAI_API_KEY)"
    } else {
      Write-Host "❌ Could not find OPENAI_API_KEY in .env"
    }
  } else {
    Write-Host "❌ .env file not found."
  }
} else {
  Write-Host "🔐 OPENAI_API_KEY present (masked): $(MaskTail $env:OPENAI_API_KEY)"
}

# --- 7) Live auth smoke test against OpenAI (fast, safe) ---
$auth = $false
try {
  $code = @'
from app.ai.llm import test_auth
ok = test_auth()
print("AUTH_OK=" + str(ok))
'@
  $result = python -c $code 2>$null
  if ($LASTEXITCODE -eq 0 -and $result -match "AUTH_OK=True") {
    Write-Host "✅ OpenAI authentication successful."
    $auth = $true
  } else {
    Write-Host "❌ OpenAI authentication failed (see API key / network / project settings)."
  }
} catch {
  Write-Host "❌ OpenAI auth check raised an error: $($_.Exception.Message)"
}

# --- 8) Start Uvicorn and ensure clean deactivation on exit ---
Write-Host (">>> Starting server at http://127.0.0.1:" + $Port + " (Ctrl+C to stop)")
try {
  python -m uvicorn app.main:app --host 127.0.0.1 --port $Port --reload
} finally {
  Write-Host "🛑 Server stopped. Deactivating venv..."
  deactivate
}