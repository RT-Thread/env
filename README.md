# Python Scripts for RT-Thread Env

## Usage under Linux

### Tutorial

[How to install Env Tool with QEMU simulator in Ubuntu](https://github.com/RT-Thread/rt-thread/blob/master/documentation/quick-start/quick_start_qemu/quick_start_qemu_linux.md)

### Install Env

```
wget https://raw.githubusercontent.com/RT-Thread/env/master/install_ubuntu.sh
chmod 777 install_ubuntu.sh
./install_ubuntu.sh
```

对于中国大陆用户，请使用以下命令
```
wget https://gitee.com/RT-Thread-Mirror/env/raw/master/install_ubuntu.sh
chmod 777 install_ubuntu.sh
./install_ubuntu.sh --gitee
```

### Prepare Env

PLAN A: Whenever start the ubuntu system, you need to type command `source ~/.env/env.sh` to activate the environment variables.

or PLAN B: open `~/.bashrc` file, and attach the command `source ~/.env/env.sh` at the end of the file. It will be automatically executed when you log in the ubuntu, and you don't need to execute that command any more.
### Use Env

Please see: https://github.com/RT-Thread/rt-thread/blob/master/documentation/env/env.md#bsp-configuration-menuconfig
