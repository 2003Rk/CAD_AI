$ErrorActionPreference = "Stop"

# Build a Windows executable.
# Run on Windows PowerShell from project root:
#   powershell -ExecutionPolicy Bypass -File .\scripts\build_windows_exe.ps1

Set-Location (Join-Path $PSScriptRoot "..")

if (-Not (Test-Path ".venv")) {
    Write-Error "Missing .venv. Create it first: py -m venv .venv"
}

. .\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip pyinstaller

if (Test-Path build) { Remove-Item build -Recurse -Force }
if (Test-Path dist) { Remove-Item dist -Recurse -Force }

# Prefer an onedir, non-UPX build on Windows.
# Defender commonly flags unsigned onefile PyInstaller bootloaders as PUA/virus.
$pyArgs = @(
  "--noconfirm",
  "--clean",
  "--windowed",
  "--onedir",
  "--noupx",
  "--name", "desktop_launcher",
  "--collect-all", "matplotlib",
  "--collect-all", "ezdxf",
  "--collect-all", "PIL",
  "--collect-all", "rich"
)

if (Test-Path ".env") {
  $pyArgs += @("--add-data", ".env;.")
}

if (Test-Path "credentials") {
  $pyArgs += @("--add-data", "credentials;credentials")
}

$pyArgs += "desktop_launcher.py"

pyinstaller @pyArgs

Write-Host "Built EXE: dist\desktop_launcher\desktop_launcher.exe"
