[CmdletBinding()]
param(
    [ValidateSet("cpu", "cuda")][string]$Backend = "cuda",
    [ValidateSet("cu121", "cu122", "cu123", "cu124", "cu125")][string]$Cuda = "cu125",
    [ValidateSet("auto", "prebuilt", "source", "skip")][string]$AceStep = "auto"
)

$ErrorActionPreference = "Stop"
$Installer = Join-Path $PSScriptRoot "installer\install.py"

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 $Installer --backend $Backend --cuda $Cuda --acestep $AceStep
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python $Installer --backend $Backend --cuda $Cuda --acestep $AceStep
} else {
    throw "Python 3.10～3.12をインストールしてください。"
}

if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
