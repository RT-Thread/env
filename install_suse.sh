#!/usr/bin/env bash

TOUCH_ENV_URL=https://raw.githubusercontent.com/RT-Thread/env/master/touch_env.sh
if [ "$(wget -qO- --timeout=3 https://ipinfo.io/country 2>/dev/null)" = "CN" ]; then
    TOUCH_ENV_URL=https://gitee.com/RT-Thread-Mirror/env/raw/master/touch_env.sh
fi

sudo zypper update -y

sudo zypper install python3 python3-pip python3-venv gcc git ncurses-devel cross-arm-none-gcc11-bootstrap cross-arm-binutils qemu qemu-arm qemu-extra -y
python3 -m pip install scons requests tqdm kconfiglib
python3 -m pip install -U pyocd

wget "$TOUCH_ENV_URL" -O touch_env.sh
chmod 777 touch_env.sh
./touch_env.sh
rm touch_env.sh
