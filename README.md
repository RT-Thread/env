# Python Scripts for RT-Thread Env

## Usage under Linux

### Tutorial

[How to install Env Tool with QEMU simulator in Ubuntu](https://github.com/RT-Thread/rt-thread/blob/master/documentation/quick-start/quick_start_qemu/quick_start_qemu_linux.md)

### Install Env

```
wget https://raw.githubusercontent.com/RT-Thread/env/v1.5.x/install_ubuntu.sh
chmod 777 install_ubuntu.sh
./install_ubuntu.sh
```

对于中国大陆用户，请使用以下命令
```
wget https://gitee.com/RT-Thread-Mirror/env/raw/v1.5.x/install_ubuntu.sh
chmod 777 install_ubuntu.sh
./install_ubuntu.sh --gitee
```

### Prepare Env

PLAN A: Whenever start the ubuntu system, you need to type command `source ~/.env/env.sh` to activate the environment variables.

or PLAN B: open `~/.bashrc` file, and attach the command `source ~/.env/env.sh` at the end of the file. It will be automatically executed when you log in the ubuntu, and you don't need to execute that command any more.
### Use Env

Please see: https://github.com/RT-Thread/rt-thread/blob/master/documentation/env/env.md#bsp-configuration-menuconfig

## Usage under Windows

Tested on the following version of PowerShell:

- PSVersion                      5.1.22621.963
- PSVersion                      5.1.19041.2673

### Install Env

您需要以管理员身份运行 PowerShell 来设置执行。（You need to run PowerShell as an administrator to set up execution.）

在 PowerShell 中执行（Execute the command in PowerShell）：

```powershell
wget https://raw.githubusercontent.com/RT-Thread/env/v1.5.x/install_windows.ps1 -O install_windows.ps1
set-executionpolicy remotesigned
.\install_windows.ps1
```

对于中国大陆用户，请使用以下命令：

```powershell
wget https://gitee.com/RT-Thread-Mirror/env/raw/v1.5.x/install_windows.ps1 -O install_windows.ps1
set-executionpolicy remotesigned
.\install_windows.ps1 --gitee
```

注意：
1. Powershell要以管理员身份运行。
2. 将其设置为 remotesigned 后，您可以作为普通用户运行 PowerShell。（ After setting it to remotesigned, you can run PowerShell as a normal user.）
3. 一定要关闭杀毒软件，否则安装过程可能会被杀毒软件强退

### Prepare Env

方案 A：每次重启 PowerShell 时，都需要输入命令 `~/.env/env.ps1`，以激活环境变量。（PLAN A: Each time you restart PowerShell, you need to enter the command `~/.env/env.ps1` to activate the environment variable.）

方案 B (推荐)：打开 `C:\Users\user\Documents\WindowsPowerShell`，如果没有`WindowsPowerShell`则新建该文件夹。新建文件 `Microsoft.PowerShell_profile.ps1`，然后写入 `~/.env/env.ps1` 内容即可，它将在你重启 PowerShell 时自动执行，无需再执行方案 A 中的命令。（or PLAN B (recommended): Open `C:\Users\user\Documents\WindowsPowerShell` and create a new file `Microsoft.PowerShell_profile.ps1`. Then write `~/.env/env.ps1` to the file. It will be executed automatically when you restart PowerShell, without having to execute the command in scenario A.）

如果还需要使 scons 命令有效以及能使用 QEMU，则需要再添加工具链路径和 QEMU 路径。（If you also need the scons command to work and to use QEMU, you need to add the following two commands to add your toolchain path and the QEMU path.）

```
~/.env/env.ps1
$env:RTT_EXEC_PATH="your toolchain path"
$env:path="your QEMU path;$env:path"
```
