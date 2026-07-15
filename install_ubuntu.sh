#!/usr/bin/env bash

TOUCH_ENV_URL=https://raw.githubusercontent.com/RT-Thread/env/master/touch_env.sh
if [ "$(wget -qO- --timeout=3 https://ipinfo.io/country 2>/dev/null)" = "CN" ]; then
    TOUCH_ENV_URL=https://gitee.com/RT-Thread-Mirror/env/raw/master/touch_env.sh
fi

sudo apt-get update
sudo apt-get -qq install python3 python3-pip python3-venv gcc git libncurses5-dev -y
pip install scons requests tqdm kconfiglib pyyaml

wget "$TOUCH_ENV_URL" -O touch_env.sh
chmod 777 touch_env.sh
./touch_env.sh
rm touch_env.sh
