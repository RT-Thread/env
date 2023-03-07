$env_bin_dir = "$HOME\.env\tools\bin"

if (!(Test-Path -Path $env_bin_dir)) {
    echo 'Can not find kconfig-mconf, install now.'
    mkdir $env_bin_dir | Out-Null
    Expand-Archive -Path kconfig-mconf.zip -DestinationPath $env_bin_dir
    echo 'install kconfig-mconf done.'
}
$env:path="$HOME\.env\tools\bin;$env:path"
python $HOME/.env/tools/scripts/env.py menuconfig $args