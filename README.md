<p align="center">
  <img src="assets/env.png" alt="RT-Thread Env" width="406">
</p>

# RT-Thread Env

> A command-line toolkit for RT-Thread development.

> WARNING
>
> [env v2.0](https://github.com/RT-Thread/env/tree/master) and [env-windows v2.0](https://github.com/RT-Thread/env-windows/tree/v2.0.0) only **FULL SUPPORT** RT-Thread > v5.1.0 or [master](https://github.com/rt-thread/rt-thread) branch. if you work on RT-Thread <= v5.1.0, please use [env v1.5.x](https://github.com/RT-Thread/env/tree/v1.5.x) for linux, [env-windows v1.5.x](https://github.com/RT-Thread/env-windows/tree/v1.5.2) for windows
>
> env v2.0 has made the following important changes:
>
> - Upgrading Python version from v2 to v3
> - Replacing kconfig-frontends with Python kconfiglib
>
> Env v2.0 installs kconfiglib and its other runtime dependencies in a Python venv; do not preinstall them into the host Python environment.

## Installation Dependencies

安装脚本只准备宿主 Python、Git 和平台所需的系统构建工具，不再向宿主 Python
安装或升级 pip、SCons、requests、psutil、tqdm、kconfiglib 等 Python 包。
首次运行 `source ~/.env/env.sh` 或 `~/.env/env.ps1` 时，Env 创建
`~/.env/.venv`，并根据 `pyproject.toml` 在其中安装运行依赖。

The installers prepare the host Python, Git, and platform-specific system build
tools only. They do not install or upgrade pip or Env runtime packages in the
host Python environment. On first activation, Env creates `~/.env/.venv` and
installs its runtime dependencies there from `pyproject.toml`.

pyocd 和 OpenOCD 不属于基础安装，不会默认安装；需要时可由独立的可选 Env
插件提供。Arch 安装入口使用受控的系统依赖列表，不再调用 AUR 元包或询问
是否安装额外调试工具。

pyocd and OpenOCD are not part of the base installation. They can be provided by
optional Env plugins when needed. The Arch installer uses an explicit system
dependency list instead of an AUR meta-package or debugger installation prompts.

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

请根据自身网络地区选择对应的下载地址来下载安装脚本。安装脚本会自动识别网络区域，使用相应镜像下载后续仓库，完成后将仓库远程地址统一设为 GitHub。

### Prepare Env

Run `source ~/.env/env.sh` to activate Env. The script creates a missing Python
virtual environment and always attempts to activate it. When the local
`tools/scripts` source changes, it offers to reinstall Env into the venv and
synchronize the activation script. To activate Env automatically, add this
command to `~/.bashrc`.

The upgrade check is local and does not fetch the Env Git repository. Python
packages use the Alibaba Cloud PyPI mirror when a mainland China IP is detected;
other regions and detection failures use pip's configured default. Set
`ENV_PYPI_INDEX_URL` to override the package index or
`ENV_VENV_AUTO_UPGRADE=1` to accept a pending local-source upgrade without a
prompt.

### Use Env

Please see: [https://github.com/RT-Thread/rt-thread/blob/master/documentation/env/env.md#bsp-configuration-menuconfig](https://github.com/RT-Thread/rt-thread/blob/master/documentation/env/env.md#bsp-configuration-menuconfig)

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

Run `~/.env/env.ps1` to activate Env. It follows the same venv creation, local
upgrade, mirror selection, and activation behavior as `env.sh`. To activate Env
automatically, add `~/.env/env.ps1` to your PowerShell profile.
