if ([string]::IsNullOrWhiteSpace($env:ENV_ROOT)) {
    $EnvRoot = $PSScriptRoot
} else {
    $EnvRoot = $env:ENV_ROOT
}

$env:ENV_ROOT = $EnvRoot
$VenvRoot = Join-Path $EnvRoot ".venv"
$ScriptsRoot = Join-Path $EnvRoot "tools\scripts"
$BootstrapScript = Join-Path $ScriptsRoot "env_venv.py"
$VenvPython = Join-Path $VenvRoot "Scripts\python.exe"
$ActivateScript = Join-Path $VenvRoot "Scripts\Activate.ps1"
$BootstrapStatus = 0
$ActivateStatus = 0

if (Test-Path -Path $VenvPython -PathType Leaf) {
    $BootstrapPython = $VenvPython
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $BootstrapPython = "python"
} else {
    $BootstrapPython = $null
}

if ($null -eq $BootstrapPython) {
    Write-Error "Cannot prepare the RT-Thread Env venv: Python 3 was not found."
    $BootstrapStatus = 1
} elseif (-not (Test-Path -Path $BootstrapScript -PathType Leaf)) {
    Write-Error "Cannot prepare the RT-Thread Env venv: $BootstrapScript was not found."
    $BootstrapStatus = 1
} else {
    & $BootstrapPython $BootstrapScript `
        --venv $VenvRoot `
        --source $ScriptsRoot `
        --activation-script (Join-Path $EnvRoot "env.ps1")
    $BootstrapStatus = $LASTEXITCODE
}

if (Test-Path -Path $ActivateScript -PathType Leaf) {
    try {
        . $ActivateScript
    } catch {
        Write-Error "Failed to activate the RT-Thread Env Python venv: $_"
        $ActivateStatus = 1
    }
} else {
    Write-Error "Cannot activate the RT-Thread Env Python venv: $ActivateScript was not found."
    $ActivateStatus = 1
}

$env:PATHEXT = ".PS1;$env:PATHEXT"

if ($BootstrapStatus -ne 0) {
    Write-Warning "The Env venv preparation failed, but activation was still attempted."
}
if ($ActivateStatus -ne 0) {
    Write-Warning "The Env Python venv is not active."
}
