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

./touch_env.sh
