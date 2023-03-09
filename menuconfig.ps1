$env_scripts_dir = "$HOME\.env\tools\scripts"
$env_bin_dir = "$HOME\.env\tools\bin"

if (!(Test-Path -Path $env_bin_dir)) {
    echo 'Can not find kconfig-mconf, install now.'
    mkdir $env_bin_dir | Out-Null
    Expand-Archive -Path $env_scripts_dir\kconfig-mconf.zip -DestinationPath $env_bin_dir
    if (!$?)  {
        echo 'Expand-Archive failed.'
        exit
    }
    echo 'install kconfig-mconf done.'
}
$env:path="$HOME\.env\tools\bin;$env:path"
python $HOME/.env/tools/scripts/env.py menuconfig $args