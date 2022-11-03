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

if ! [ -x "$(command -v gcc)" ]; then
    echo "Installing gcc."
    sudo apt install gcc
fi

if ! [ -x "$(command -v git)" ]; then
    echo "Installing git."
    sudo apt install git
fi

if [ $(dpkg-query -W -f='${Status}' libncurses5-dev 2>/dev/null | grep -c "ok installed") -eq 0 ]; then
    echo "Installing ncurses."
    sudo apt install libncurses5-dev
fi

$RTT_PYTHON -m pip list > /dev/null || {
    echo "Installing pip."
    sudo apt install python3-pip
}

if ! [ -x "$(command -v scons)" ]; then
    echo "Installing scons."
    sudo apt install scons
fi

./touch_env.sh
