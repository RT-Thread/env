# Python Scripts for RT-Thread Env

## Usage under Linux

### Tutorial

[How to install Env Tool with QEMU simulator in Ubuntu](https://github.com/RT-Thread/rt-thread/blob/master/documentation/quick-start/quick_start_qemu/quick_start_qemu_linux.md)

### Prepare Env

run command under one of bsp:

    scons --menuconfig

If the env is not initialized in your machine, above command will intialize env script under your `~/.env` folder.

### Use Env

There is one `pkgs` shell script under `~/.env/tools/scripts` folder. In order to use it more conveniently, your can run following command to set environment:

    source ~/.env/env.sh

Then when you use `scons --menuconfig` to config online packages, you can use:

    pkgs --update

to update local packages under your local bsp project.
