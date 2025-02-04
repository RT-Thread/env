#!/usr/bin/env bash

sudo apt-get update
sudo apt-get -qq install python3 python3-pip gcc git libncurses5-dev -y
pip install scons requests tqdm kconfiglib pyyaml

url=https://raw.githubusercontent.com/RT-Thread/env/master/touch_env.sh
if [ $1 ] && [ $1 = --gitee ]; then
    url=https://gitee.com/RT-Thread-Mirror/env/raw/master/touch_env.sh
fi

wget $url -O touch_env.sh
chmod 777 touch_env.sh
./touch_env.sh $@
rm touch_env.sh
