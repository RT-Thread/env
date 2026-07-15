# Python Scripts for RT-Thread Env

> WARNING
> 
> [env v2.0](https://github.com/RT-Thread/env/tree/master) and [env-windows v2.0](https://github.com/RT-Thread/env-windows/tree/v2.0.0) only **FULL SUPPORT** RT-Thread > v5.1.0 or [master](https://github.com/rt-thread/rt-thread) branch. if you work on RT-Thread <= v5.1.0, please use [env v1.5.x](https://github.com/RT-Thread/env/tree/v1.5.x) for linux, [env-windows v1.5.x](https://github.com/RT-Thread/env-windows/tree/v1.5.2) for windows
>
> env v2.0 has made the following important changes:
> - Upgrading Python version from v2 to v3
> - Replacing kconfig-frontends with Python kconfiglib
>
>  env v2.0 require python kconfiglib (install by `pip install kconfiglib`), but env v1.5.x confilt with kconfiglib (please run `pip uninstall kconfiglib`)

## Usage under Linux

### Tutorial

[How to install Env Tool with QEMU simulator in Ubuntu](https://github.com/RT-Thread/rt-thread/blob/master/documentation/quick-start/quick_start_qemu/quick_start_qemu_linux.md)

### Install Env

```
# 中国大陆网络：
wget https://gitee.com/RT-Thread-Mirror/env/raw/master/install_ubuntu.sh

# 其他地区网络：
wget https://raw.githubusercontent.com/RT-Thread/env/master/install_ubuntu.sh

chmod 777 install_ubuntu.sh
./install_ubuntu.sh
rm install_ubuntu.sh
```

请根据自身网络地区选择对应的下载地址。安装脚本会自动识别网络区域，使用相应镜像下载仓库，完成后将仓库远程地址统一设为 GitHub。

### Prepare Env

Run `source ~/.env/env.sh` to activate Env. The script creates and activates its Python virtual environment on first use. To activate Env automatically, add this command to `~/.bashrc`.

### Use Env

Please see: <https://github.com/RT-Thread/rt-thread/blob/master/documentation/env/env.md#bsp-configuration-menuconfig>

## Usage under Windows

Tested on the following version of PowerShell:

- PSVersion                      5.1.22621.963
- PSVersion                      5.1.19041.2673

### Install Env

您需要以管理员身份运行 PowerShell 来设置执行。（You need to run PowerShell as an administrator to set up execution.）

在 PowerShell 中执行（Execute the command in PowerShell）：

```powershell
wget https://raw.githubusercontent.com/RT-Thread/env/master/install_windows.ps1 -O install_windows.ps1
set-executionpolicy remotesigned
.\install_windows.ps1
```

安装脚本会自动识别网络区域，使用相应镜像下载仓库，完成后将仓库远程地址统一设为 GitHub。

注意：

1. Powershell要以管理员身份运行。
2. 将其设置为 remotesigned 后，您可以作为普通用户运行 PowerShell。（ After setting it to remotesigned, you can run PowerShell as a normal user.）
3. 一定要关闭杀毒软件，否则安装过程可能会被杀毒软件强退

### Prepare Env

Run `~/.env/env.ps1` to activate Env. The script creates and activates its Python virtual environment on first use. To activate Env automatically, add `~/.env/env.ps1` to your PowerShell profile.