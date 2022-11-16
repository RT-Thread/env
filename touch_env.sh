#!/usr/bin/env bash

DEFAULT_RTT_PACKAGE_URL=https://github.com/RT-Thread/packages.git
# you can change the package url by defining RTT_PACKAGE_URL, ex:
#    export RTT_PACKAGE_URL=https://github.com/Varanda-Labs/packages.git
RTT_URL=https://github.com/RT-Thread/rt-thread.git
ENV_URL=https://github.com/RT-Thread/env.git

if [ $1 ] && [ $1 = --gitee ]; then
    gitee=1
    DEFAULT_RTT_PACKAGE_URL=https://gitee.com/RT-Thread-Mirror/packages.git
    RTT_URL=https://gitee.com/rtthread/rt-thread.git
    ENV_URL=https://gitee.com/RT-Thread-Mirror/env.git
fi

env_dir=$HOME/.env
if ! [ -d $env_dir ]; then
    package_url=${RTT_PACKAGE_URL:-$DEFAULT_RTT_PACKAGE_URL}
    mkdir $env_dir
    mkdir $env_dir/local_pkgs
    mkdir $env_dir/packages
    mkdir $env_dir/tools
    git clone $package_url $env_dir/packages/packages
    echo 'source "$PKGS_DIR/packages/Kconfig"' > $env_dir/packages/Kconfig
    git clone $ENV_URL $env_dir/tools/scripts
    echo 'export PATH=$HOME/.env/tools/scripts:$PATH' > $env_dir/env.sh
fi

RTT_ROOT=$HOME/rt-thread
# you can download rt-thread to another directory by changing RTT_ROOT
if ! [ -d $RTT_ROOT ]; then
    git clone $RTT_URL $RTT_ROOT
    if [ $gitee ]; then
        cd $RTT_ROOT
        git checkout master
    fi
fi
