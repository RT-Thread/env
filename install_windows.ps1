
$RTT_PYTHON = "python"

function Test-Command( [string] $CommandName ) {
    (Get-Command $CommandName -ErrorAction SilentlyContinue) -ne $null
}

foreach ($p_cmd in ("python3","python")) {
    cmd /c $p_cmd --version | Out-Null
    if (!$?)  { continue }
    $RTT_PYTHON = $p_cmd
    break
}

if (!(Test-Command $RTT_PYTHON)) {
    echo "Python not installed. Will install python 3.11.2."
    echo "Downloading Python."
    wget -O Python_setup.exe https://www.python.org/ftp/python/3.11.2/python-3.11.2.exe
    echo "Installing Python."
    if (Test-Path -Path "D:\") {
        cmd /c Python_setup.exe /quiet TargetDir=D:\Progrem\Python311 InstallAllUsers=1 PrependPath=1 Include_test=0
    }
    else {
        cmd /c Python_setup.exe /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
    }
}

if (!(Test-Command git)) {
    echo "Git not installed. Will install Git."
    echo "Installing git."
    winget install --id Git.Git -e --source winget
}

cmd /c $RTT_PYTHON -m pip list | Out-Null
if (!$?) {
    echo "Installing pip."
    cmd /c $RTT_PYTHON -m ensurepip --upgrade
}

cmd /c $RTT_PYTHON -m pip install --upgrade pip | Out-Null

if (!(Test-Command scons)) {
    echo "Installing scons."
    cmd /c $RTT_PYTHON -m pip install scons
}

cmd /c $RTT_PYTHON -m pip list | findstr "requests"  | Out-Null
if (!$?) {
    echo "Installing requests."
    cmd /c $RTT_PYTHON -m pip install requests
}

$url="https://raw.githubusercontent.com/RT-Thread/env/master/touch_env.ps1"
if ($args[0] -eq "--gitee") {
    $url="https://gitee.com/RT-Thread-Mirror/env/raw/master/touch_env.ps1"
}

wget $url -O touch_env.ps1
./touch_env.ps1 $args[0]
