[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$BackendPort = 8000,

    [ValidateRange(1, 65535)]
    [int]$FrontendPort = 5173,

    [switch]$RefreshDependencies,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$webRoot = Join-Path $repoRoot "web"
$venvRoot = Join-Path $repoRoot ".venv"
$pythonExe = Join-Path $venvRoot "Scripts\python.exe"
$logRoot = Join-Path $repoRoot ".local-playtest"
$backendProcess = $null
$frontendProcess = $null
$previousApiKey = $env:MIMO_API_KEY
$previousProxyTarget = $env:VITE_BACKEND_PROXY_TARGET
$modelEnvironmentNames = @(
    "MODEL_API_KEY",
    "MODEL_API_MODEL",
    "MODEL_API_BASE_URL",
    "MODEL_API_AUTH_HEADER",
    "MODEL_API_AUTH_SCHEME",
    "MODEL_API_JSON_MODE",
    "MODEL_API_TOKEN_FIELD",
    "MODEL_API_TIMEOUT_SECONDS"
)
$previousModelEnvironment = @{}
foreach ($name in $modelEnvironmentNames) {
    $previousModelEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
}

function Read-ValueWithDefault {
    param(
        [string]$Prompt,
        [string]$Default
    )

    $value = Read-Host "$Prompt [$Default]"
    if ([string]::IsNullOrWhiteSpace($value)) {
        return $Default
    }
    return $value.Trim()
}

function Read-HiddenApiKey {
    $secureKey = Read-Host "Model API key (input is hidden)" -AsSecureString
    $keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer)
    }
}

function Assert-PortAvailable {
    param([int]$Port)

    $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    if ($listener) {
        throw "Port $Port is already in use. Stop the existing listener or choose another port."
    }
}

function Wait-ForListener {
    param(
        [int]$Port,
        [System.Diagnostics.Process]$Process,
        [string]$Name,
        [string]$ErrorLog
    )

    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        Start-Sleep -Milliseconds 500
        $Process.Refresh()
        if ($Process.HasExited) {
            $tail = if (Test-Path $ErrorLog) {
                (Get-Content -LiteralPath $ErrorLog -Tail 20) -join [Environment]::NewLine
            } else {
                "No error log was written."
            }
            throw "$Name exited before listening on port $Port.`n$tail"
        }

        if (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) {
            return
        }
    }

    throw "$Name did not listen on port $Port within 30 seconds. See $ErrorLog"
}

function Stop-PlaytestProcessTree {
    param([System.Diagnostics.Process]$Process)

    if (-not $Process) {
        return
    }

    $Process.Refresh()
    if (-not $Process.HasExited) {
        & taskkill.exe /PID $Process.Id /T /F *> $null
    }
}

function Stop-PlaytestListener {
    param([int]$Port)

    # Both ports were verified free before this run, so remaining listeners on
    # these exact ports belong to the process trees started above.
    $listeners = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    foreach ($listener in $listeners) {
        Stop-Process -Id $listener.OwningProcess -Force -ErrorAction SilentlyContinue
    }
}

try {
    Assert-PortAvailable -Port $BackendPort
    Assert-PortAvailable -Port $FrontendPort

    $hasCustomConfiguration = -not [string]::IsNullOrWhiteSpace($env:MODEL_API_KEY) `
        -or -not [string]::IsNullOrWhiteSpace($env:MODEL_API_MODEL) `
        -or -not [string]::IsNullOrWhiteSpace($env:MODEL_API_BASE_URL)
    $hasLegacyMimoConfiguration = -not [string]::IsNullOrWhiteSpace($env:MIMO_API_KEY)

    if ($hasCustomConfiguration -or -not $hasLegacyMimoConfiguration) {
        if ([string]::IsNullOrWhiteSpace($env:MODEL_API_BASE_URL)) {
            $env:MODEL_API_BASE_URL = Read-ValueWithDefault `
                -Prompt "OpenAI-compatible API base URL or full chat/completions URL" `
                -Default "https://open.bigmodel.cn/api/paas/v4"
        }
        if ([string]::IsNullOrWhiteSpace($env:MODEL_API_MODEL)) {
            $env:MODEL_API_MODEL = Read-ValueWithDefault -Prompt "Model name" -Default "glm-5.1"
        }
        if ([string]::IsNullOrWhiteSpace($env:MODEL_API_KEY)) {
            $env:MODEL_API_KEY = Read-HiddenApiKey
        }
        if ([string]::IsNullOrWhiteSpace($env:MODEL_API_KEY)) {
            throw "MODEL_API_KEY cannot be empty."
        }

        try {
            $modelApiUri = [Uri]$env:MODEL_API_BASE_URL
        } catch {
            throw "MODEL_API_BASE_URL must be an absolute URL."
        }
        if (-not $modelApiUri.IsAbsoluteUri -or [string]::IsNullOrWhiteSpace($modelApiUri.Host)) {
            throw "MODEL_API_BASE_URL must be an absolute URL."
        }
        $isMimoEndpoint = $modelApiUri.Host -eq "xiaomimimo.com" `
            -or $modelApiUri.Host.EndsWith(".xiaomimimo.com")
        if ([string]::IsNullOrWhiteSpace($env:MODEL_API_AUTH_HEADER)) {
            $env:MODEL_API_AUTH_HEADER = if ($isMimoEndpoint) { "api-key" } else { "Authorization" }
        }
        if ([string]::IsNullOrWhiteSpace($env:MODEL_API_AUTH_SCHEME)) {
            $env:MODEL_API_AUTH_SCHEME = if ($isMimoEndpoint) { "none" } else { "Bearer" }
        }
        if ([string]::IsNullOrWhiteSpace($env:MODEL_API_JSON_MODE)) {
            $env:MODEL_API_JSON_MODE = "false"
        }
        if ([string]::IsNullOrWhiteSpace($env:MODEL_API_TOKEN_FIELD)) {
            $env:MODEL_API_TOKEN_FIELD = if ($isMimoEndpoint) {
                "max_completion_tokens"
            } else {
                "max_tokens"
            }
        }
        if ([string]::IsNullOrWhiteSpace($env:MODEL_API_TIMEOUT_SECONDS)) {
            $env:MODEL_API_TIMEOUT_SECONDS = "30"
        }
    }

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand) {
        throw "Python 3.11 or newer is required and was not found on PATH."
    }

    $npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if (-not $npmCommand) {
        $npmCommand = Get-Command npm -ErrorAction SilentlyContinue
    }
    if (-not $npmCommand) {
        throw "Node.js and npm are required and were not found on PATH."
    }

    if (-not (Test-Path -LiteralPath $pythonExe)) {
        Write-Host "Creating Python virtual environment..."
        & $pythonCommand.Source -m venv $venvRoot
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create the Python virtual environment."
        }
    }

    $pythonReady = $false
    if (-not $RefreshDependencies) {
        & $pythonExe -c "import fastapi, uvicorn, rules_beyond" 2>$null
        $pythonReady = $LASTEXITCODE -eq 0
    }
    if (-not $pythonReady) {
        Write-Host "Installing Python runtime dependencies..."
        & $pythonExe -m pip install -e $repoRoot
        if ($LASTEXITCODE -ne 0) {
            throw "Python dependency installation failed."
        }
    }

    $nodeModules = Join-Path $webRoot "node_modules"
    if ($RefreshDependencies -or -not (Test-Path -LiteralPath $nodeModules)) {
        Write-Host "Installing frontend dependencies..."
        Push-Location $webRoot
        try {
            & $npmCommand.Source ci
            if ($LASTEXITCODE -ne 0) {
                throw "Frontend dependency installation failed."
            }
        } finally {
            Pop-Location
        }
    }

    New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
    $backendOut = Join-Path $logRoot "backend.stdout.log"
    $backendErr = Join-Path $logRoot "backend.stderr.log"
    $frontendOut = Join-Path $logRoot "frontend.stdout.log"
    $frontendErr = Join-Path $logRoot "frontend.stderr.log"

    $env:VITE_BACKEND_PROXY_TARGET = "http://127.0.0.1:$BackendPort"

    $backendProcess = Start-Process `
        -FilePath $pythonExe `
        -ArgumentList @("-m", "rules_beyond.api_server", "--host", "127.0.0.1", "--port", $BackendPort) `
        -WorkingDirectory $repoRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $backendOut `
        -RedirectStandardError $backendErr `
        -PassThru

    $frontendProcess = Start-Process `
        -FilePath $npmCommand.Source `
        -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1", "--port", $FrontendPort, "--strictPort") `
        -WorkingDirectory $webRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $frontendOut `
        -RedirectStandardError $frontendErr `
        -PassThru

    Wait-ForListener -Port $BackendPort -Process $backendProcess -Name "Backend" -ErrorLog $backendErr
    Wait-ForListener -Port $FrontendPort -Process $frontendProcess -Name "Frontend" -ErrorLog $frontendErr

    $gameUrl = "http://127.0.0.1:$FrontendPort/"
    Write-Host ""
    Write-Host "Rules Beyond is ready: $gameUrl" -ForegroundColor Green
    Write-Host "Logs: $logRoot"
    Write-Host "Press Ctrl+C to stop both local services."

    if (-not $NoBrowser) {
        Start-Process $gameUrl
    }

    while ($true) {
        Start-Sleep -Seconds 1
        $backendProcess.Refresh()
        $frontendProcess.Refresh()
        if ($backendProcess.HasExited -or $frontendProcess.HasExited) {
            throw "A local service stopped unexpectedly. See $logRoot"
        }
    }
} finally {
    Stop-PlaytestProcessTree -Process $frontendProcess
    Stop-PlaytestProcessTree -Process $backendProcess
    Start-Sleep -Milliseconds 250
    Stop-PlaytestListener -Port $FrontendPort
    Stop-PlaytestListener -Port $BackendPort

    if ($null -eq $previousApiKey) {
        Remove-Item Env:MIMO_API_KEY -ErrorAction SilentlyContinue
    } else {
        $env:MIMO_API_KEY = $previousApiKey
    }

    foreach ($name in $modelEnvironmentNames) {
        [Environment]::SetEnvironmentVariable(
            $name,
            $previousModelEnvironment[$name],
            "Process"
        )
    }

    if ($null -eq $previousProxyTarget) {
        Remove-Item Env:VITE_BACKEND_PROXY_TARGET -ErrorAction SilentlyContinue
    } else {
        $env:VITE_BACKEND_PROXY_TARGET = $previousProxyTarget
    }
}
