<# verify_openai.ps1 (v2, Windows/PowerShell)
   - Creates/activates .venv
   - Installs from requirements.txt (if present)
   - Verifies OPENAI_API_KEY presence (.env or env) and OpenAI connectivity
   - Prints full Python traceback on failure
#>

Param(
  [string]$EnvName = ".venv"
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

# 0) Optional: better console encoding (prevents weird characters)
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

# 1) Check Python
try {
  $pyVersion = & python --version
  Write-Host "Python detected: $pyVersion"
} catch {
  Write-Error "Python not found on PATH. Install Python 3.x and re-run."
  exit 1
}

# 2) Create venv if missing
if (!(Test-Path $EnvName)) {
  Write-Host "Creating virtual environment: $EnvName"
  python -m venv $EnvName
}

# 3) Activate venv
Write-Host "Activating virtual environment..."
. "$EnvName\Scripts\Activate.ps1"
if (-not $env:VIRTUAL_ENV) {
  Write-Error "Virtual environment not active. Aborting."
  exit 1
}

# 4) Upgrade pip
python -m pip install --upgrade pip | Out-Null

# 5) Install deps from requirements.txt (fallback to minimal if missing)
if (Test-Path "requirements.txt") {
  Write-Host "Installing dependencies from requirements.txt ..."
  pip install -r requirements.txt
} else {
  Write-Host "requirements.txt not found. Installing minimal dependencies (openai, python-dotenv) ..."
  pip install openai python-dotenv
}

# 6) Write the Python verification to a temp file (better error capture)
$pyFile = Join-Path $env:TEMP "verify_openai_check.py"
@'
import os, sys, traceback
from typing import Optional
from dotenv import load_dotenv

def mask(s: Optional[str], tail: int = 4) -> str:
    if not s:
        return "<MISSING>"
    return "*" * max(0, len(s) - tail) + s[-tail:]

def main():
    try:
        # Load .env from current working directory (project root).
        load_dotenv()
        key = os.getenv("OPENAI_API_KEY", "")
        print(f"OPENAI_API_KEY present: {bool(key)}")
        print(f"OPENAI_API_KEY masked:  {mask(key)}")

        if not key:
            print("AUTH_OK=False")
            print("AUTH_ERROR=No OPENAI_API_KEY found in env or .env")
            return 2

        try:
            from openai import OpenAI
            client = OpenAI(api_key=key)
            _ = client.models.list()  # small call to verify auth + connectivity
            print("AUTH_OK=True")
            return 0
        except Exception as e:
            print("AUTH_OK=False")
            # Print full traceback for debugging
            tb = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            # Keep it readable (but complete)
            print("AUTH_ERROR_BEGIN")
            print(tb)
            print("AUTH_ERROR_END")
            return 3
    except Exception as e:
        print("AUTH_OK=False")
        tb = "".join(traceback.format_exception(type(e), e, e.__traceback__))
        print("AUTH_ERROR_BEGIN")
        print(tb)
        print("AUTH_ERROR_END")
        return 4

if __name__ == "__main__":
    sys.exit(main())
'@ | Set-Content -LiteralPath $pyFile -Encoding UTF8

# 7) Run the Python check file
Write-Host "------------------ VERIFICATION ------------------"
& python $pyFile
$exitCode = $LASTEXITCODE
Write-Host "---------------------------------------------------"

# 8) Summarize outcome with friendly messages
if ($exitCode -eq 0) {
  Write-Host "SUCCESS: OPENAI_API_KEY loaded and OpenAI authentication succeeded."
  exit 0
}
elseif ($exitCode -eq 2) {
  Write-Host "WARNING: OPENAI_API_KEY not found. Set it in your environment or add it to a .env file in the project root."
  Write-Host "Example .env line:  OPENAI_API_KEY=sk-your-real-key"
  exit 2
}
else {
  Write-Host "FAILURE: Authentication or connectivity failed. See traceback above for details."
  Write-Host "Common causes:"
  Write-Host "  - Invalid/expired key (rotate at https://platform.openai.com/api-keys)"
  Write-Host "  - Wrong project/org (set OPENAI_ORG_ID / OPENAI_PROJECT if needed)"
  Write-Host "  - Network/firewall blocking api.openai.com"
  exit 3
}