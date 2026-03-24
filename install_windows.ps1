
$RTT_PYTHON = "python"
$ARM_GNU_VERSION = "14.3.rel1"
$ARM_GNU_INSTALLER = "arm-gnu-toolchain-$ARM_GNU_VERSION-mingw-w64-i686-arm-none-eabi.exe"
$ARM_GNU_URL = "https://developer.arm.com/-/media/Files/downloads/gnu/$ARM_GNU_VERSION/binrel/$ARM_GNU_INSTALLER"
$ARM_GNU_DIR = "C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi\14.3 rel1"
$ARM_GNU_BIN = Join-Path $ARM_GNU_DIR "bin"

function Test-Command( [string] $CommandName ) {
    (Get-Command $CommandName -ErrorAction SilentlyContinue) -ne $null
}

function Download-File([string] $Url, [string] $OutFile) {
    if (Test-Command "Invoke-WebRequest") {
        try {
            Invoke-WebRequest -Uri $Url -OutFile $OutFile
            if (Test-Path -Path $OutFile) { return $true }
        } catch {
            echo "Invoke-WebRequest download failed: $Url"
        }
    }

    if (Test-Command "curl.exe") {
        cmd /c curl.exe -L $Url -o $OutFile | Out-Null
        if ($LASTEXITCODE -eq 0 -and (Test-Path -Path $OutFile)) {
            return $true
        }
    }

    return $false
}

function Ensure-SystemPathContains([string] $PathToAdd) {
    if (!(Test-Path -Path $PathToAdd)) {
        return
    }

    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    if ([string]::IsNullOrEmpty($machinePath)) {
        $machinePath = ""
    }

    $machineItems = $machinePath -split ";" | Where-Object { $_ -ne "" }
    if ($machineItems -notcontains $PathToAdd) {
        $newMachinePath = if ($machinePath.TrimEnd(";")) {
            $machinePath.TrimEnd(";") + ";" + $PathToAdd
        } else {
            $PathToAdd
        }

        try {
            [Environment]::SetEnvironmentVariable("Path", $newMachinePath, "Machine")
            echo "Add ARM GCC bin to system PATH: $PathToAdd"
        } catch {
            echo "Warning: failed to update system PATH. Please run PowerShell as Administrator."
        }
    } else {
        echo "ARM GCC bin already exists in system PATH."
    }

    $procItems = $env:Path -split ";" | Where-Object { $_ -ne "" }
    if ($procItems -notcontains $PathToAdd) {
        $env:Path = $env:Path.TrimEnd(";") + ";" + $PathToAdd
    }
}

function Ensure-UserEnvVar([string] $Name, [string] $Value) {
    if ([string]::IsNullOrWhiteSpace($Value)) {
        return
    }

    $currentValue = [Environment]::GetEnvironmentVariable($Name, "User")
    if ($currentValue -ne $Value) {
        [Environment]::SetEnvironmentVariable($Name, $Value, "User")
        echo "Set user environment variable $Name=$Value"
    } else {
        echo "User environment variable $Name already set."
    }

    Set-Item -Path "Env:$Name" -Value $Value
}

foreach ($p_cmd in ("python3", "python", "py")) {
    cmd /c $p_cmd --version | findstr "Python" | Out-Null
    if (!$?) { continue }
    $RTT_PYTHON = $p_cmd
    break
}

cmd /c $RTT_PYTHON --version | findstr "Python" | Out-Null
if (!$?) {
    echo "Python is not installed. Will install python 3.11.2."
    echo "Downloading Python."
    if (!(Download-File "https://www.python.org/ftp/python/3.11.2/python-3.11.2.exe" "Python_setup.exe")) {
        echo "Download Python installer failed."
        exit 1
    }
    echo "Installing Python."
    if (Test-Path -Path "D:\") {
        cmd /c Python_setup.exe /quiet TargetDir=D:\Progrem\Python311 InstallAllUsers=1 PrependPath=1 Include_test=0
    } else {
        cmd /c Python_setup.exe /quiet PrependPath=1 Include_test=0
    }
    echo "Install Python done. please close the current terminal and run this script again."
    exit
} else {
    echo "Python environment has installed. Jump this step."
}

$git_url = "https://github.com/git-for-windows/git/releases/download/v2.39.2.windows.1/Git-2.39.2-64-bit.exe"
if ($args[0] -eq "--gitee") {
    echo "Use gitee mirror server!"
    $git_url = "https://registry.npmmirror.com/-/binary/git-for-windows/v2.39.2.windows.1/Git-2.39.2-64-bit.exe"
}

if (!(Test-Command git)) {
    echo "Git is not installed. Will install Git."
    echo "Installing git."
    winget install --id Git.Git -e --source winget
    if (!$?) {
        echo "Can't find winget cmd, Will install git 2.39.2."
        echo "downloading git."
        if (!(Download-File $git_url "Git64.exe")) {
            echo "Download Git installer failed."
            exit 1
        }
        echo "Please install git. when install done, close the current terminal and run this script again."
        cmd /c Git64.exe /quiet PrependPath=1
        exit
    }
} else {
    echo "Git environment has installed. Jump this step."
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
} else {
    echo "Pip has installed. Jump this step."
}

cmd /c $RTT_PYTHON -m pip install --upgrade pip -i $PIP_SOURCE --trusted-host $PIP_HOST | Out-Null

if (!(Test-Command scons)) {
    echo "Installing scons."
    cmd /c $RTT_PYTHON -m pip install scons -i $PIP_SOURCE --trusted-host $PIP_HOST
} else {
    echo "scons has installed. Jump this step."
}

if (!(Test-Command pyocd)) {
    echo "Installing pyocd."
    cmd /c $RTT_PYTHON -m pip install -U pyocd -i $PIP_SOURCE --trusted-host $PIP_HOST
} else {
    echo "pyocd has installed. Jump this step."
}

cmd /c $RTT_PYTHON -m pip list -i $PIP_SOURCE --trusted-host $PIP_HOST | findstr "tqdm"  | Out-Null
if (!$?) {
    echo "Installing tqdm module."
    cmd /c $RTT_PYTHON -m pip install tqdm -i $PIP_SOURCE --trusted-host $PIP_HOST
} else {
    echo "tqdm module has installed. Jump this step."
}

cmd /c $RTT_PYTHON -m pip list -i $PIP_SOURCE --trusted-host $PIP_HOST | findstr "kconfiglib"  | Out-Null
if (!$?) {
    echo "Installing kconfiglib module."
    cmd /c $RTT_PYTHON -m pip install kconfiglib -i $PIP_SOURCE --trusted-host $PIP_HOST
} else {
    echo "kconfiglib module has installed. Jump this step."
}


cmd /c $RTT_PYTHON -m pip list -i $PIP_SOURCE --trusted-host $PIP_HOST | findstr "requests"  | Out-Null
if (!$?) {
    echo "Installing requests module."
    cmd /c $RTT_PYTHON -m pip install requests -i $PIP_SOURCE --trusted-host $PIP_HOST
} else {
    echo "requests module has installed. Jump this step."
}

cmd /c $RTT_PYTHON -m pip list -i $PIP_SOURCE --trusted-host $PIP_HOST | findstr "psutil"  | Out-Null
if (!$?) {
    echo "Installing psutil module."
    cmd /c $RTT_PYTHON -m pip install psutil -i $PIP_SOURCE --trusted-host $PIP_HOST
} else {
    echo "psutil module has installed. Jump this step."
}

if (Test-Command arm-none-eabi-gcc) {
    echo "ARM GNU GCC has installed. Jump this step."
} else {
    if (!(Test-Path -Path $ARM_GNU_DIR)) {
        echo "Downloading ARM GNU Toolchain $ARM_GNU_VERSION."
        if (!(Download-File $ARM_GNU_URL $ARM_GNU_INSTALLER)) {
            echo "Download ARM GNU Toolchain installer failed."
            exit 1
        }

        echo "Installing ARM GNU Toolchain $ARM_GNU_VERSION."
        $proc = Start-Process -FilePath ".\$ARM_GNU_INSTALLER" -ArgumentList "/S", "/P", "/R" -Wait -PassThru
        if ($proc.ExitCode -ne 0) {
            echo "Install ARM GNU Toolchain failed, exit code: $($proc.ExitCode)"
            exit 1
        }
    } else {
        echo "Found ARM GNU Toolchain directory: $ARM_GNU_DIR"
    }

    Ensure-SystemPathContains $ARM_GNU_BIN
}

$rttExecPath = ""
if (Test-Path -Path $ARM_GNU_BIN) {
    $rttExecPath = $ARM_GNU_BIN
} elseif (Test-Command arm-none-eabi-gcc) {
    $rttExecPath = Split-Path -Parent (Get-Command arm-none-eabi-gcc).Source
}

if (![string]::IsNullOrWhiteSpace($rttExecPath)) {
    Ensure-UserEnvVar "RTT_EXEC_PATH" $rttExecPath
} else {
    echo "Warning: arm-none-eabi-gcc not found, skip setting RTT_EXEC_PATH."
}

$url = "https://raw.githubusercontent.com/RT-Thread/env/master/touch_env.ps1"
if ($args[0] -eq "--gitee") {
    $url = "https://gitee.com/RT-Thread-Mirror/env/raw/master/touch_env.ps1"
}

if (!(Download-File $url "touch_env.ps1")) {
    echo "Download touch_env.ps1 failed. Please check network/proxy and retry."
    exit 1
}
echo "run touch_env.ps1"
& .\touch_env.ps1 $args[0]

if ($args.Count -ge 2 -and $args[1] -eq "-y") {
    echo "Windows Env environment installment has finished. (auto mode, no pause)"
} else {
    Read-Host -Prompt "Windows Env environment installment has finished. Press any key to continue..."
}
