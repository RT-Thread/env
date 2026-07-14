#!/usr/bin/env bash

sudo apt-get update
sudo apt-get -qq install python3 python3-pip python3-venv gcc git libncurses5-dev -y
pip install scons requests tqdm kconfiglib pyyaml

wget https://raw.githubusercontent.com/RT-Thread/env/master/touch_env.sh -O touch_env.sh
chmod 777 touch_env.sh
./touch_env.sh
rm touch_env.sh
