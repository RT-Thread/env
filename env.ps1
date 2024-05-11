$VENV_ROOT = "$PSScriptRoot\.venv"
# rt-env目录是否存在
if (-not (Test-Path -Path $VENV_ROOT)) {
    Write-Host "Create Python venv for RT-Thread..."
    python -m venv $VENV_ROOT
    # 激活python venv
    & "$VENV_ROOT\Scripts\Activate.ps1"
    # 安装env-script
    pip install "$PSScriptRoot\tools\scripts"
} else {
    # 激活python venv
    & "$VENV_ROOT\Scripts\Activate.ps1"
}

$env:pathext = ".PS1;$env:pathext"
