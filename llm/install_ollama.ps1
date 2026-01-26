param(
    [switch]$RunIntegration,
    [string]$IntegrationArgs = '--prompt "Play 2048 game: restart game" --model mistral'
)

Write-Host "Ollama automated installer (PowerShell)" -ForegroundColor Cyan

function Open-Docs {
    Write-Host "Opening Ollama installation docs in your browser..."
    Start-Process "https://ollama.com/docs/installation"
}

try {
    $consent = Read-Host "This script will attempt to download and run the Ollama Windows installer. Continue? (Y/N)"
    if ($consent -notin @('Y','y')) {
        Write-Host "User cancelled. To install manually, visit https://ollama.com/docs/installation"
        exit 1
    }

    Write-Host "Querying GitHub releases for Ollama..."
    $headers = @{ 'User-Agent' = 'PowerShell' }
    $release = Invoke-RestMethod -Uri 'https://api.github.com/repos/ollama/ollama/releases/latest' -Headers $headers -ErrorAction Stop
    $asset = $null
    foreach ($a in $release.assets) {
        if ($a.name -match 'windows|win' -and $a.name -match '\.exe$') { $asset = $a; break }
    }

    if (-not $asset) {
        Write-Host "Could not find a Windows installer asset in latest GitHub release." -ForegroundColor Yellow
        Open-Docs
        exit 2
    }

    $url = $asset.browser_download_url
    $installer = Join-Path $env:TEMP 'ollama-installer.exe'
    Write-Host "Downloading $($asset.name) to $installer ..."
    Invoke-WebRequest -Uri $url -OutFile $installer -UseBasicParsing -ErrorAction Stop

    Write-Host "Running installer (elevation required). Follow the installer UI to completion." -ForegroundColor Green
    Start-Process -FilePath $installer -Verb RunAs -Wait

    Write-Host "Installer finished. Waiting a few seconds for PATH changes to propagate..."
    Start-Sleep -Seconds 3

    Write-Host "Re-running project's Ollama availability checker..."
    python -m llm_n.check_ollama

    if ($RunIntegration) {
        Write-Host "Running integration: python -m llm_n.integrate_with_project $IntegrationArgs"
        python -m llm_n.integrate_with_project $IntegrationArgs
    }
}
catch {
    Write-Host "Installer script failed: $($_.Exception.Message)" -ForegroundColor Red
    Open-Docs
    exit 10
}
