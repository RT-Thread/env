#!/usr/bin/env bash

TOUCH_ENV_URL=https://raw.githubusercontent.com/RT-Thread/env/master/touch_env.sh
COUNTRY=$(wget -qO- --timeout=3 https://ipinfo.io/country 2>/dev/null)
if [ "$COUNTRY" = "CN" ]; then
    TOUCH_ENV_URL=https://gitee.com/RT-Thread-Mirror/env/raw/master/touch_env.sh
elif [ -z "$COUNTRY" ] && [ -t 0 ]; then
    read -r -p "Unable to detect network region. Use Gitee mirror? (y/N, default: GitHub) " use_gitee
    if [[ "$use_gitee" =~ ^[Yy]$ ]]; then
        TOUCH_ENV_URL=https://gitee.com/RT-Thread-Mirror/env/raw/master/touch_env.sh
    fi
fi

# Python runtime dependencies are installed in the Env venv on first activation.
sudo pacman -Syu python gcc git ncurses \
    arm-none-eabi-gcc arm-none-eabi-gdb \
    qemu-desktop qemu-system-arm-firmware

wget "$TOUCH_ENV_URL" -O touch_env.sh
chmod 777 touch_env.sh
./touch_env.sh
rm touch_env.sh
