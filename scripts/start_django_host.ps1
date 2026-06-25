[CmdletBinding()]
param(
    [string]$Python = "python",
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8030,
    [ValidateSet("ask", "true", "false")]
    [string]$AllowSvgDataImages = "ask"
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

$BindAddress = "${HostAddress}:${Port}"

function Set-AgomTuiSvgDataImageOption {
    param([string]$Value)

    if ($Value -eq "ask") {
        $answer = Read-Host "Allow SVG data URL images to auto-render? [Y/n]"
        if ([string]::IsNullOrWhiteSpace($answer)) {
            $answer = "Y"
        }
        $Value = if ($answer.Trim().ToLowerInvariant().StartsWith("n")) { "false" } else { "true" }
    }

    $env:AGOMTUI_ALLOW_SVG_DATA_IMAGES = if ($Value -eq "false") { "0" } else { "1" }
}

Set-AgomTuiSvgDataImageOption -Value $AllowSvgDataImages

Write-Host "Starting AgomTUI Django host demo..."
Write-Host "Django host: http://$BindAddress/"
Write-Host "Mounted TUI: http://$BindAddress/tui/"
Write-Host "SVG data URL images: $($(if ($env:AGOMTUI_ALLOW_SVG_DATA_IMAGES -eq '0') { 'disabled' } else { 'enabled' }))"
Write-Host "Press Ctrl+C to stop."

& $Python "demo\django_host\manage.py" runserver $BindAddress --noreload
exit $LASTEXITCODE
