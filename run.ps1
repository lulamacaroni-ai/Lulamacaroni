# Run the LulaMacaroni back office on a Windows machine.
#
#   .\run.bat            open the app in your browser (real store + Sheet, from .env)
#   .\run.bat sync       refresh the Sheet from Shopify and Prodigi, then print alerts
#   .\run.bat demo       open the app with sample data (no keys needed, nothing real touched)
#   .\run.bat check      check the Google key and the Sheet without changing anything
#
# First run: creates .venv, installs the app, and creates .env from .env.example
# and opens it in Notepad so you can fill in the values. .env is gitignored:
# never commit it, never paste its values anywhere.

param([string]$Mode = "app")

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

function Stop-WithMessage([string]$Message) {
    Write-Host ""
    Write-Host $Message -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

# 1. Find Python 3.11 or newer ------------------------------------------------
$check = "import sys; print(1 if sys.version_info >= (3, 11) else 0)"
$python = $null
foreach ($candidate in @(@("py", "-3"), @("python"), @("python3"))) {
    $exe = $candidate[0]
    $extra = @($candidate | Select-Object -Skip 1)
    if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
    try {
        $ok = & $exe @extra -c $check 2>$null
        if ($LASTEXITCODE -eq 0 -and "$ok".Trim() -eq "1") { $python = $candidate; break }
    } catch { }
}
if (-not $python) {
    Stop-WithMessage ("Python 3.11 or newer was not found.`n" +
        "Install it from https://www.python.org/downloads/windows/ and tick " +
        "'Add python.exe to PATH' on the first screen of the installer. Then run this again.")
}

# 2. Virtual environment + install (only when pyproject.toml changes) --------
$venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Host "Creating the Python environment (.venv), first run only..."
    $exe = $python[0]; $extra = @($python | Select-Object -Skip 1)
    & $exe @extra -m venv .venv
    if ($LASTEXITCODE -ne 0) { Stop-WithMessage "Could not create .venv." }
}
$marker = Join-Path $PSScriptRoot ".venv\installed.txt"
$wanted = (Get-FileHash (Join-Path $PSScriptRoot "pyproject.toml")).Hash
$have = if (Test-Path $marker) { (Get-Content $marker -Raw).Trim() } else { "" }
if ($have -ne $wanted) {
    Write-Host "Installing the app and its libraries (takes a minute the first time)..."
    & $venvPy -m pip install --quiet --disable-pip-version-check --upgrade pip
    & $venvPy -m pip install --quiet --disable-pip-version-check -e ".[google]"
    if ($LASTEXITCODE -ne 0) { Stop-WithMessage "pip install failed. Check your internet connection and run this again." }
    Set-Content -Path $marker -Value $wanted
}

# 3. .env with the keys (demo does not need it) ------------------------------
$envFile = Join-Path $PSScriptRoot ".env"
if ($Mode -ne "demo") {
    if (-not (Test-Path $envFile)) {
        Copy-Item (Join-Path $PSScriptRoot ".env.example") $envFile
        Start-Process notepad.exe $envFile
        Stop-WithMessage ("Created .env and opened it in Notepad.`n" +
            "Fill in the values (see docs/run-local.md), save, close Notepad, and run this again.")
    }
    $missing = @()
    $text = Get-Content $envFile
    foreach ($name in @("SHOPIFY_STORE_DOMAIN", "SHOPIFY_CLIENT_ID", "SHOPIFY_CLIENT_SECRET",
                        "GOOGLE_SERVICE_ACCOUNT_JSON_B64")) {
        $line = $text | Where-Object { $_ -match "^\s*$name\s*=\s*\S" }
        if (-not $line) { $missing += $name }
    }
    if ($missing.Count -gt 0) {
        Stop-WithMessage ("These are still empty in .env: " + ($missing -join ", ") +
            "`nFill them in (see docs/run-local.md), save, and run this again.")
    }
}

# 4. Run -----------------------------------------------------------------------
switch ($Mode) {
    "app"   { Write-Host "Starting the back office. Leave this window open; press Ctrl+C to stop."
              & $venvPy -m lulamacaroni.app.server --open }
    "demo"  { Write-Host "Starting the back office with SAMPLE data. Press Ctrl+C to stop."
              & $venvPy -m lulamacaroni.app.server --demo --open }
    "sync"  { Write-Host "Refreshing the Sheet from Shopify and Prodigi..."
              & $venvPy -m lulamacaroni.sync }
    "check" { & $venvPy -m lulamacaroni.google_check }
    default { Stop-WithMessage "Unknown option '$Mode'. Use: app, sync, demo or check." }
}
exit $LASTEXITCODE
