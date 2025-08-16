$VENV_ROOT = "$PSScriptRoot\.venv"
# rt-env目录是否存在
if (-not (Test-Path -Path $VENV_ROOT)) {
    Write-Host "Create Python venv for RT-Thread..."
    python -m venv $VENV_ROOT
    # 激活python venv
    & "$VENV_ROOT\Scripts\Activate.ps1"
    # 安装env-script
    # 判断IP是否在中国大陆，若是则用清华源，否则用默认源
    try {
        $china = $false
        $ipinfo = Invoke-RestMethod -Uri "https://ipinfo.io/json" -UseBasicParsing -TimeoutSec 3
        if ($ipinfo.country -eq "CN") {
            $china = $true
        }
    } catch {
        $china = $false
    }
    if ($china) {
        Write-Host "Detected China Mainland IP, using Tsinghua PyPI mirror."
        pip install -i https://pypi.tuna.tsinghua.edu.cn/simple "$PSScriptRoot\tools\scripts"
    } else {
        pip install "$PSScriptRoot\tools\scripts"
    }
} else {
    # 激活python venv
    & "$VENV_ROOT\Scripts\Activate.ps1"
}

$env:pathext = ".PS1;$env:pathext"
