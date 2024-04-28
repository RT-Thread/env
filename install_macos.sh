#!/usr/bin/env bash

RTT_PYTHON=python

for p_cmd in python3 python; do
    $p_cmd --version >/dev/null 2>&1 || continue
    RTT_PYTHON=$p_cmd
    break
done

$RTT_PYTHON --version 2 > /dev/null || {
    echo "Python not installed. Please install Python before running the installation script."
    exit 1
}

if ! [ -x "$(command -v brew)" ]; then
    echo "Installing Homebrew."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

brew update
brew upgrade

if ! [ -x "$(command -v git)" ]; then
    echo "Installing git."
    brew install git
fi

brew list ncurses > /dev/null || {
    echo "Installing ncurses."
    brew install ncurses
}

$RTT_PYTHON -m pip list > /dev/null || {
    echo "Installing pip."
    $RTT_PYTHON -m ensurepip --upgrade
}

if ! [ -x "$(command -v scons)" ]; then
    echo "Installing scons."
    $RTT_PYTHON -m pip install scons
fi

if ! [ -x "$(command -v pyocd)" ]; then
    echo "Installing pyocd."
    $RTT_PYTHON -m pip install -U pyocd
fi

if ! [[ `$RTT_PYTHON -m pip list | grep requests` ]]; then
    echo "Installing requests."
    $RTT_PYTHON -m pip install requests
fi

if ! [ -x "$(command -v arm-none-eabi-gcc)" ]; then
    echo "Installing GNU Arm Embedded Toolchain."
    brew install gnu-arm-embedded
fi

url=https://raw.githubusercontent.com/RT-Thread/env/v1.5.x/touch_env.sh
if [ $1 ] && [ $1 = --gitee ]; then
    url=https://gitee.com/RT-Thread-Mirror/env/raw/v1.5.x/touch_env.sh
fi
curl $url -o touch_env.sh
chmod 777 touch_env.sh
./touch_env.sh $@
