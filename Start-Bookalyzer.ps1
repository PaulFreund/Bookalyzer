$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    throw 'Python-Umgebung fehlt. Bitte zuerst die Einrichtung in README.md ausführen.'
}
if (-not (Test-Path -LiteralPath 'node_modules')) {
    & npm.cmd ci
    if ($LASTEXITCODE -ne 0) { throw 'Installation der Desktop-Abhängigkeiten fehlgeschlagen.' }
}
& npm.cmd start
