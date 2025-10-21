Param(
  [string]$Port = "8000",
  [string]$EnvName = ".venv"
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

# Only install inside an active venv
$env:PIP_REQUIRE_VIRTUALENV = "true"

# Create venv if missing
if (!(Test-Path $EnvName)) {
  Write-Host "Creating virtual environment: $EnvName"
  python -m venv $EnvName
}

# Activate venv
. "$EnvName\Scripts\Activate.ps1"

# Assert venv active
if (-not $env:VIRTUAL_ENV) {
  Write-Error "Virtual environment not active. Aborting."
  exit 1
}

# Show environment info
python -c "import sys,site,platform; print('VENV OK'); print('Python:', sys.executable); print('Base:', sys.base_prefix); print('Venv:', sys.prefix); print('Sites:', site.getsitepackages()); print('OS:', platform.platform())"

# Upgrade pip and install requirements (if file exists)
python -m pip install --upgrade pip
if (Test-Path "requirements.txt") {
  pip install -r requirements.txt
} else {
  Write-Host "requirements.txt not found; continuing without installs."
}

# Ensure output directories
foreach ($d in @("out","bucket","outputs")) {
  if (!(Test-Path $d)) { New-Item -ItemType Directory -Path $d | Out-Null }
}

# Ensure uvicorn is available
try {
  python -c "import uvicorn" | Out-Null
} catch {
  Write-Host "Installing uvicorn"
  pip install uvicorn
}

Write-Host (">>> Starting server at http://127.0.0.1:" + $Port + " (Ctrl+C to stop)")
python -m uvicorn app.main:app --host 127.0.0.1 --port $Port --reload