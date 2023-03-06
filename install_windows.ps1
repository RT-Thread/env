
$RTT_PYTHON = "python"

function Test-Command( [string] $CommandName ) {
    (Get-Command $CommandName -ErrorAction SilentlyContinue) -ne $null
}

foreach ($p_cmd in ("python3", "python", "py")) {
    cmd /c $p_cmd --version | findstr "Python" | Out-Null
    if (!$?)  { continue }
    $RTT_PYTHON = $p_cmd
    break
}

cmd /c $RTT_PYTHON --version | findstr "Python" | Out-Null
if (!$?) {
    echo "Python not installed. Will install python 3.11.2."
    echo "Downloading Python."
    wget -O Python_setup.exe https://www.python.org/ftp/python/3.11.2/python-3.11.2.exe
    echo "Installing Python."
    if (Test-Path -Path "D:\") {
        cmd /c Python_setup.exe /quiet TargetDir=D:\Progrem\Python311 InstallAllUsers=1 PrependPath=1 Include_test=0
    }
    else {
        cmd /c Python_setup.exe /quiet PrependPath=1 Include_test=0
    }
    echo "Install Python done. please close the current terminal and run this script again."
    exit
}

$git_url = "https://github.com/git-for-windows/git/releases/download/v2.39.2.windows.1/Git-2.39.2-64-bit.exe"
if ($args[0] -eq "--gitee") {
    $git_url = "https://registry.npmmirror.com/-/binary/git-for-windows/v2.39.2.windows.1/Git-2.39.2-64-bit.exe"
}
if (!(Test-Command git)) {
    echo "Git not installed. Will install Git."
    echo "Installing git."
    winget install --id Git.Git -e --source winget
    if (!$?) {
        echo "Can't find winget cmd, Will install git 2.39.2."
        echo "downloading git."
        wget -O Git64.exe $git_url
        echo "Please install git. when install done, close the current terminal and run this script again."
        cmd /c Git64.exe /quiet PrependPath=1
        exit
    }
}

$PIP_SOURCE = "https://pypi.org/simple"
$PIP_HOST = "pypi.org"
if ($args[0] -eq "--gitee") {
    $PIP_SOURCE = "http://mirrors.aliyun.com/pypi/simple"
    $PIP_HOST = "mirrors.aliyun.com"
}

cmd /c $RTT_PYTHON -m pip list -i $PIP_SOURCE --trusted-host $PIP_HOST | Out-Null
if (!$?) {
    echo "Installing pip."
    cmd /c $RTT_PYTHON -m ensurepip --upgrade
}

cmd /c $RTT_PYTHON -m pip install --upgrade pip -i $PIP_SOURCE --trusted-host $PIP_HOST | Out-Null

if (!(Test-Command scons)) {
    echo "Installing scons."
    cmd /c $RTT_PYTHON -m pip install scons -i $PIP_SOURCE --trusted-host $PIP_HOST
}

cmd /c $RTT_PYTHON -m pip list -i $PIP_SOURCE --trusted-host $PIP_HOST | findstr "requests"  | Out-Null
if (!$?) {
    echo "Installing requests."
    cmd /c $RTT_PYTHON -m pip install requests -i $PIP_SOURCE --trusted-host $PIP_HOST
}

$url="https://raw.githubusercontent.com/RT-Thread/env/master/touch_env.ps1"
if ($args[0] -eq "--gitee") {
    $url="https://gitee.com/RT-Thread-Mirror/env/raw/master/touch_env.ps1"
}

wget $url -O touch_env.ps1
./touch_env.ps1 $args[0]
