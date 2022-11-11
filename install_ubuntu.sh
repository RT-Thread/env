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

$RTT_PYTHON -m pip list > /dev/null || {
    echo "Installing pip."
    sudo apt install $RTT_PYTHON-pip -y
}

sudo apt update
sudo apt upgrade -y

sudo apt install gcc git libncurses5-dev scons gcc-arm-none-eabi binutils-arm-none-eabi qemu qemu-system-arm -y

export RTT_EXEC_PATH=/usr/bin # set the default tool chain path

wget https://raw.githubusercontent.com/RT-Thread/env/master/touch_env.sh -O touch_env.sh
chmod 777 touch_env.sh
./touch_env.sh
