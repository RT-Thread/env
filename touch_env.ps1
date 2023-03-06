$DEFAULT_RTT_PACKAGE_URL="https://github.com/RT-Thread/packages.git"
# you can change the package url by defining RTT_PACKAGE_URL, ex:
#    export RTT_PACKAGE_URL=https://github.com/Varanda-Labs/packages.git
$RTT_URL="https://github.com/RT-Thread/rt-thread.git"
$ENV_URL="https://github.com/RT-Thread/env.git"

if ($args[0] -eq "--gitee") {
    echo "Using gitee service."
    $DEFAULT_RTT_PACKAGE_URL="https://gitee.com/RT-Thread-Mirror/packages.git"
    $RTT_URL="https://gitee.com/rtthread/rt-thread.git"
    $ENV_URL="https://gitee.com/RT-Thread-Mirror/env.git"
}

$env_dir = "$HOME\.env"
if (!(Test-Path -Path $env_dir)) {
    $package_url=$DEFAULT_RTT_PACKAGE_URL
    mkdir $env_dir | Out-Null
    mkdir $env_dir\local_pkgs | Out-Null
    mkdir $env_dir\packages | Out-Null
    mkdir $env_dir\tools | Out-Null
    git clone $package_url $env_dir/packages/packages
    echo 'source "$PKGS_DIR/packages/Kconfig"' | Out-File -FilePath $env_dir/packages/Kconfig -Encoding ASCII
    git clone $ENV_URL $env_dir/tools/scripts
    echo '$env:path="$HOME\.env\tools\scripts;$env:path"' > $env_dir/env.ps1
    echo '$env:pathext=".PS1;$env:pathext"' >> $env_dir/env.ps1
}