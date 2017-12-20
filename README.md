# env
Python Scripts for RT-Thread/ENV

## Usage under Linux

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
