[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$BaseFile,

    [Parameter(Mandatory = $true)]
    [string]$Object,

    [string]$User = "Администратор",
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")).Path
$cli = Join-Path $repositoryRoot "scripts\onec.py"
$manifestPath = $null

try {
    $createdJson = & $PythonExe $cli session-create `
        --base-file $BaseFile `
        --user $User
    if ($LASTEXITCODE -ne 0) {
        throw "session-create failed with exit code $LASTEXITCODE"
    }

    $created = $createdJson | ConvertFrom-Json
    if (-not $created.ok -or -not $created.session) {
        throw "session-create did not return a valid session manifest"
    }
    $manifestPath = [string]$created.session

    $exportJson = & $PythonExe $cli selective-export `
        --session $manifestPath `
        --object $Object `
        --label "example-inspection"
    if ($LASTEXITCODE -ne 0) {
        throw "selective-export failed with exit code $LASTEXITCODE"
    }

    $export = $exportJson | ConvertFrom-Json
    $export | ConvertTo-Json -Depth 8
    if ($export.output -and (Test-Path -LiteralPath $export.output)) {
        Get-ChildItem -LiteralPath $export.output -Recurse -File |
            Select-Object -First 20 FullName, Length
    }
}
finally {
    if ($manifestPath -and (Test-Path -LiteralPath $manifestPath)) {
        & $PythonExe $cli session-cleanup --session $manifestPath
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Automatic cleanup failed. Inspect this marked session: $manifestPath"
        }
    }
}
