[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8

# Overridden by $env:ENV_ROOT environment variable
$env:ENV_ROOT = $PSScriptRoot

# Virtual environment directory name
$RT_VENV_DIR = "$env:ENV_ROOT\venv\rt-env" 

if (Test-Path "$RT_VENV_DIR\Scripts\Activate.ps1") {
    . "$RT_VENV_DIR\Scripts\Activate.ps1"
    
    # Show welcome message using rt-env command
    if (Get-Command rt-env -ErrorAction SilentlyContinue) {
        rt-env -v
    }
}
else {
    Write-Host "Virtual environment($RT_VENV_DIR\Scripts\Activate.ps1) not found. Please run the installation `RT-Thread ENV` first."
    exit 1
}

$env:pathext = ".PS1;$env:pathext"
