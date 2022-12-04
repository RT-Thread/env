#!/usr/bin/env bash

sudo apt update
sudo apt upgrade -y

sudo apt install python3 python3-pip gcc git libncurses5-dev gcc-arm-none-eabi binutils-arm-none-eabi gdb-multiarch qemu qemu-system-arm -y
python3 -m pip install scons requests

url=https://raw.githubusercontent.com/RT-Thread/env/master/touch_env.sh
if [ $1 ] && [ $1 = --gitee ]; then
    url=https://gitee.com/RT-Thread-Mirror/env/raw/master/touch_env.sh
fi

wget $url -O touch_env.sh
chmod 777 touch_env.sh
./touch_env.sh $@
