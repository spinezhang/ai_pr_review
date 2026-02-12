$ErrorActionPreference = 'Stop'

$RootDir = Resolve-Path (Join-Path $PSScriptRoot '..')

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 -m pip install --upgrade pip
    & py -3 -m pip install $RootDir
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python -m pip install --upgrade pip
    & python -m pip install $RootDir
} else {
    throw 'Python 3 is required but was not found in PATH.'
}

Write-Host 'Installation complete.'
Write-Host ''
Write-Host 'Run the tool from anywhere:'
Write-Host '  ai-pr-review --help'
Write-Host ''
Write-Host 'If the command is not found, add your Python Scripts directory to PATH.'
