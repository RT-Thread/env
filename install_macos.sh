#!/usr/bin/env bash

RTT_PYTHON=python

for p_cmd in python3 python; do
    $p_cmd --version >/dev/null 2>&1 || continue
    RTT_PYTHON=$p_cmd
    break
done

$RTT_PYTHON --version 2 >/dev/null || {
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

brew list ncurses >/dev/null || {
    echo "Installing ncurses."
    brew install ncurses
}

if ! [ -x "$(command -v arm-none-eabi-gcc)" ]; then
    echo "Installing GNU Arm Embedded Toolchain."
    brew install gnu-arm-embedded
fi

curl https://raw.githubusercontent.com/RT-Thread/env/master/touch_env.sh -o touch_env.sh
chmod 777 touch_env.sh
./touch_env.sh
rm touch_env.sh
