# Run from a normal PowerShell session; does not alter execution policy or install OS tools.
$ErrorActionPreference = 'Stop'
$python = Get-Command python.exe -CommandType Application -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Error 'Python 3.9+ x64 is required. Install it, then reopen PowerShell.'
    exit 2
}
Push-Location -LiteralPath $PSScriptRoot
try {
    & $python.Source -X utf8 -B (Join-Path $PSScriptRoot 'tools\first_run.py') @args
    $result = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $result
