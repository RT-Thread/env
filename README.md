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

EnvAgent requires Python 3.11 or newer.

```
wget https://raw.githubusercontent.com/RT-Thread/env/master/install_ubuntu.sh
chmod 777 install_ubuntu.sh
./install_ubuntu.sh
rm install_ubuntu.sh
```

对于中国大陆用户，请使用以下命令

```
wget https://gitee.com/RT-Thread-Mirror/env/raw/master/install_ubuntu.sh
chmod 777 install_ubuntu.sh
./install_ubuntu.sh --gitee
rm install_ubuntu.sh
```

### Prepare Env

PLAN A: Whenever start the ubuntu system, you need to type command `source ~/.env/env.sh` to activate the environment variables.

or PLAN B: open `~/.bashrc` file, and attach the command `source ~/.env/env.sh` at the end of the file. It will be automatically executed when you log in the ubuntu, and you don't need to execute that command any more.

### Use Env

Please see: <https://github.com/RT-Thread/rt-thread/blob/master/documentation/env/env.md#bsp-configuration-menuconfig>

### Use EnvAgent

Env includes EnvAgent as an integrated AI assistant feature. After activating Env:

```bash
source ~/.env/env.sh
agent
```

You can also run it through the Env command dispatcher:

```bash
rt-env agent
rt-env agent --prompt "help me inspect this BSP"
```

EnvAgent reads model profiles from `~/.env/agent.json`, or falls back to
`ANTHROPIC_API_KEY` when no profile is configured. A typical `agent.json` looks
like this:

```json
{
  "active": "Kimi-K2",
  "profiles": [
    {
      "name": "Kimi-K2",
      "provider": "kimi",
      "model": "kimi-k2-2026",
      "key": "sk-xxxx",
      "base_url": "https://api.moonshot.cn/anthropic"
    }
  ]
}
```

Without `--prompt`, EnvAgent opens the full-screen TUI. Inside the TUI, press
`Enter` to send, `Alt+Enter` for a newline, `/agent` to switch model profiles,
and `Ctrl-D` to exit.

EnvAgent stores user-level configuration and runtime state under the Env root
directory, normally `~/.env`. For example, model profiles are stored in
`~/.env/agent.json`, sessions in `~/.env/sessions`, and user hooks/settings in
`~/.env/hooks` and `~/.env/settings.json`.

Skills are loaded in this priority order, with the first skill name winning when
duplicates exist:

1. Project skills: `<project>/.agents/skills`
2. User agent skills: `~/.agents/skills`
3. Env skills: `~/.env/skills`

## Usage under Windows

Tested on the following version of PowerShell:

- PSVersion                      5.1.22621.963
- PSVersion                      5.1.19041.2673

### Install Env

您需要以管理员身份运行 PowerShell 来设置执行。（You need to run PowerShell as an administrator to set up execution.）

EnvAgent 需要 Python 3.11 或更高版本。

在 PowerShell 中执行（Execute the command in PowerShell）：

```powershell
wget https://raw.githubusercontent.com/RT-Thread/env/master/install_windows.ps1 -O install_windows.ps1
set-executionpolicy remotesigned
.\install_windows.ps1
```

对于中国大陆用户，请使用以下命令：

```powershell
wget https://gitee.com/RT-Thread-Mirror/env/raw/master/install_windows.ps1 -O install_windows.ps1
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

### Use EnvAgent

激活 Env 后可以直接进入 EnvAgent：

```powershell
~/.env/env.ps1
agent
```

也可以通过 Env 命令调用：

```powershell
rt-env agent
rt-env agent --prompt "help me inspect this BSP"
```

EnvAgent 的模型配置文件为 `~/.env/agent.json`，格式与 Linux/macOS 相同。

EnvAgent 的用户级配置和运行状态与 Env 工具一致放在 `~/.env` 下，例如
`~/.env/agent.json`、`~/.env/sessions`、`~/.env/hooks` 和
`~/.env/settings.json`。Skills 按以下优先级加载，同名 skill 以先加载者为准：

1. 工程目录：`<project>/.agents/skills`
2. 用户 Agent 目录：`~/.agents/skills`
3. Env 目录：`~/.env/skills`

### 常见问题

对于中国大陆用户，请注意首次激活 Env 时可能出现错误，这可能是当前网络下使用的镜像（默认清华源）连接失败，修复方法：

1. 再次进入安装 Env 的目录，运行`.\install_windows.ps1 --gitee`重新安装，并在**安装完成后不要激活 Env**。
2. 打开 `~/.env/env.ps1` 文件，修改 `python -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple` 和 `pip install -i https://pypi.tuna.tsinghua.edu.cn/simple "$PSScriptRoot\tools\scriptse` 中的镜像地址 `https://pypi.tuna.tsinghua.edu.cn/simple` 为其他可用的镜像。
3. 激活 Env。
