$ErrorActionPreference = 'Stop'
$python = Get-Command python.exe -CommandType Application -ErrorAction SilentlyContinue
if (-not $python) { Write-Error 'Python 3.9+ x64 is required.'; exit 2 }
Push-Location -LiteralPath $PSScriptRoot
try {
    & $python.Source -X utf8 -B (Join-Path $PSScriptRoot 'tools\update_source.py') @args
    $result = $LASTEXITCODE
} finally { Pop-Location }
exit $result
