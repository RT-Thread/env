#!/usr/bin/env bash

sudo zypper update -y

sudo zypper install python3 python3-pip python3-venv gcc git ncurses-devel cross-arm-none-gcc11-bootstrap cross-arm-binutils qemu qemu-arm qemu-extra -y
python3 -m pip install scons requests tqdm kconfiglib
python3 -m pip install -U pyocd

wget https://raw.githubusercontent.com/RT-Thread/env/master/touch_env.sh -O touch_env.sh
chmod 777 touch_env.sh
./touch_env.sh
rm touch_env.sh
