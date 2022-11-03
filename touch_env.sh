#!/usr/bin/env bash

DEFAULT_RTT_PACKAGE_URL=https://github.com/RT-Thread/packages.git
# you can change the package url by defining RTT_PACKAGE_URL, ex:
#    export RTT_PACKAGE_URL=https://github.com/Varanda-Labs/packages.git

env_dir=$HOME/.env
if ! [ -d $env_dir ]; then
    echo 1
    package_url=${RTT_PACKAGE_URL:-$DEFAULT_RTT_PACKAGE_URL}
    mkdir $env_dir
    mkdir $env_dir/local_pkgs
    mkdir $env_dir/packages
    mkdir $env_dir/tools
    git clone $package_url $env_dir/packages/packages
    echo 'source "$PKGS_DIR/packages/Kconfig"' > $env_dir/packages/Kconfig
    git clone https://github.com/RT-Thread/env.git $env_dir/tools/scripts
    echo 'export PATH=$HOME/.env/tools/scripts:$PATH' > $env_dir/env.sh
fi
