$DEFAULT_RTT_PACKAGE_URL = "https://github.com/RT-Thread/packages.git"
$ENV_URL = "https://github.com/RT-Thread/env.git"
$SDK_URL = "https://github.com/RT-Thread/sdk.git"

if ($args[0] -eq "--gitee") {
    echo "Using gitee service."
    $DEFAULT_RTT_PACKAGE_URL = "https://gitee.com/RT-Thread-Mirror/packages.git"
    $ENV_URL = "https://gitee.com/RT-Thread-Mirror/env.git"
    $SDK_URL = "https://gitee.com/RT-Thread-Mirror/sdk.git"
}

$env_dir = "$HOME\.env"

if (Test-Path -Path $env_dir) {
    $option = Read-Host ".env directory already exists. Would you like to remove and recreate .env directory? (Y/N) " option
} if (( $option -eq 'Y' ) -or ($option -eq 'y')) {
    Get-ChildItem $env_dir -Recurse | Remove-Item -Force -Recurse
    rm -r $env_dir
}

if (!(Test-Path -Path $env_dir)) {
    echo "creating .env folder!"
    $package_url = $DEFAULT_RTT_PACKAGE_URL
    mkdir $env_dir | Out-Null
    mkdir $env_dir\local_pkgs | Out-Null
    mkdir $env_dir\packages | Out-Null
    mkdir $env_dir\tools | Out-Null
    git clone $package_url $env_dir/packages/packages --depth=1
    echo 'source "$PKGS_DIR/packages/Kconfig"' | Out-File -FilePath $env_dir/packages/Kconfig -Encoding ASCII
    git clone $SDK_URL $PKGS_DIR/packages/sdk --depth=1
    git clone $ENV_URL $env_dir/tools/scripts --depth=1
    copy $env_dir/tools/scripts/env.ps1 $env_dir/env.ps1
} else {
    echo ".env folder has exsited. Jump this step."
}
