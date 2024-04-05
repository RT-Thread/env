$VENV_ROOT = "$HOME\.env\tools\rt-env"
# rt-env目录是否存在
if (-not (Test-Path -Path $VENV_ROOT)) {
    Write-Host "Create Python venv for RT-Thread..."
    python -m venv $VENV_ROOT
    # 激活python venv
    & "$VENV_ROOT\Scripts\Activate.ps1"
    # 安装env-script
    pip install "$HOME/.env/tools/scripts"
}
else 
{
    # 激活python venv
    & "$VENV_ROOT\Scripts\Activate.ps1"
}

$RTT_CC_NAME="arm-none-eabi-gcc"
$RTT_CC_PATH=""

# 读取当前目录下的env.json文件
if (Test-Path ".vscode\env.json")
{
    $env_json = Get-Content -Raw -Path ".vscode\env.json" | ConvertFrom-Json

    # 设置环境变量
    $RTT_CC_NAME = $env_json.env.CC
}

Write-Host "set CC to $RTT_CC_NAME"
if (Test-Path "$HOME\.env\tools\sdk_list.json")
{
    $sdk_json = Get-Content -Raw -Path "$HOME\.env\tools\sdk_list.json" | ConvertFrom-Json
    foreach ($sdk in $sdk_json)
    {
        if ($sdk.name -eq $RTT_CC_NAME)
        {
            $RTT_CC_PATH = $sdk.path
            break
        }
    }

    # set RTT_CC, RTT_EXEC_PATH
    if ($RTT_CC_NAME -match 'gcc')
    {
        $env:RTT_CC="gcc"
    }
    else
    {
        $env:RTT_CC=$RTT_CC_NAME
    }

    $RTT_CC_PATH="$HOME\.env\tools\packages\$RTT_CC_PATH\bin"
    $env:RTT_EXEC_PATH=$RTT_CC_PATH
}

$env:HOSTOS="Windows"
$env:path="$HOME\.env\tools\bin;$RTT_CC_PATH;$env:path"
$env:pathext=".PS1;$env:pathext"
