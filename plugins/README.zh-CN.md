# Env 插件系统

英文文档见 [`README.md`](README.md)。

`plugins/` 实现 Env 的本地插件生命周期、命令运行时和本机 WebUI。插件包从本地文件导入，Env 负责检查、安装、升级、启用、禁用、诊断和卸载。CLI 和 WebUI 使用同一套状态和 `PluginService`，不会各自维护一份插件状态。

当前系统不包含在线插件市场，也不会根据插件 ID 自动下载插件。用户需要先取得 `.epack` 文件，再通过 Env CLI 或本机 WebUI 导入。

## 目录职责

- `manifest.py`、`package.py`：解析并校验 `.epack` v1 清单、ZIP 结构和完整性摘要。
- `installer.py`、`store.py`、`launchers.py`：管理安装状态、事务回滚和插件命令启动器。
- `dispatcher.py`、`sdk/`：统一分发插件命令，并创建插件运行上下文。
- `epack/`：插件工程初始化、校验、构建和包检查工具。
- `webui/`：Env 本机 Host API、前端源码和发行版静态资源。
- `bundled/epack/`：官方可选 `epack` 开发工具的插件工程。
- `examples/`：CLI、WebUI 以及两者组合的示例工程。
- `spec/`：`.epack` v1 包格式和 `manifest.json` 契约。
- `tests/`：生命周期、事务回滚、安全边界和端到端测试。

## 插件包是什么

`.epack` 是一个带有固定清单和完整性记录的 ZIP 包。典型内容如下：

```text
org.example.demo-1.0.0-py3-none-any.epack
├── manifest.json
├── integrity.json
├── licenses/LICENSE
├── build/build.json
└── backend/org_example_demo-1.0.0-py3-none-any.whl
```

`manifest.json` 声明插件 ID、名称、版本和兼容性，并按插件能力声明权限、命令、WebUI 和后端 artifact。命令入口使用 `module.path:callable` 格式，并实现：

```python
def main(argv, context):
    return 0
```

构建器会生成后端 wheel、构建元数据和 `integrity.json`。Env 在安装和运行时都会重新检查包完整性、当前 Env/Python 兼容性、命令冲突和必需权限。

包格式的完整约束见 [`spec/README.md`](spec/README.md)。

## 安装插件

激活 Env 后，已安装的 Env 入口通常是 `rt-env`：

```bash
source ~/.env/env.sh
rt-env plugin install /path/to/plugin.epack --yes
```

在 Env 源码树中，可以使用等价命令：

```bash
python env.py plugin install /path/to/plugin.epack --yes
```

v1 包目前没有可验证的签名，因此交互式安装会显示插件信息、权限和未签名警告并要求确认；自动化或非交互环境应使用 `--yes`。

安装成功后，插件在 `manifest.json` 中声明的命令会生成对应的启动器。例如命令名为 `env-build-insight` 时，可以直接执行：

```bash
env-build-insight
```

常用生命周期操作：

```bash
rt-env plugin list
rt-env plugin info org.example.demo
rt-env plugin doctor org.example.demo
rt-env plugin disable org.example.demo
rt-env plugin enable org.example.demo
rt-env plugin update /path/to/plugin-1.1.0.epack --yes
rt-env plugin uninstall org.example.demo --yes
```

卸载时加上 `--purge-data` 会同时删除插件自己的配置、数据和缓存；工作区文件不会由卸载流程删除。

插件运行状态默认位于 `${ENV_ROOT}/var/plugins/`：

```text
var/plugins/
├── state-v1.json
├── installed/<plugin-id>/<version>/
├── config/<plugin-id>/
├── data/<plugin-id>/
├── cache/<plugin-id>/
├── runtime/
└── staging/
```

## 安装和使用 `epack`

`epack` 是官方提供的可选开发工具，用于创建和发布其他 Env 插件。它不是 Env 生命周期管理器的必需组件；不安装 `epack` 也可以安装和运行已有的 `.epack` 插件。

从 Env 源码树构建并安装官方 `epack` 插件：

```bash
python -m plugins.epack.cli build plugins/bundled/epack
python env.py plugin install \
    plugins/bundled/epack/dist/org.rt-thread.epack-1.0.0-py3-none-any.epack \
    --yes
```

在源码树中也可以使用 `plugins/epack/` 下的便捷脚本：

```bash
python plugins/epack/build_epack.py
```

脚本默认将相同的插件包输出到 `plugins/bundled/epack/dist/`。可以使用
`-o/--output` 指定输出目录，使用 `--backend-format` 覆盖 wheel 格式，或使用
`--json` 输出机器可读结果。脚本只负责构建，不会自动安装；安装仍需显式执行
Env 的插件安装命令。

构建命令默认将包放在 `plugins/bundled/epack/dist/`。安装成功后会生成 `epack` 启动器：

```bash
epack --help
```

如果尚未安装 `epack`，可以在源码树中直接使用 `python -m plugins.epack.cli`，其命令和已安装的 `epack` 启动器相同。

## 使用 `epack` 创建插件

### 初始化工程

```bash
epack init demo \
    --id org.example.demo \
    --name Demo
```

初始化会创建 `manifest.json`、许可证、`src/` 下的 Python 包和一个最小命令入口。目标目录必须为空，插件 ID 使用小写反向域名格式，例如 `org.example.demo`。

当在 TTY 终端中执行 `epack init <directory>`，且没有传入初始化元数据参数时，会进入交互式向导。每项直接回车即可接受默认值：

```text
Plugin ID       [org.example.demo]:
Plugin name     [Demo]:
Version         [0.1.0]:
Description     [Demo Env plugin]:
Author          [Plugin Author]:
Register a command? [Y/n]:
Create a WebUI page? [y/N]:
```

向导会校验每项输入，非法值会重新询问。默认生成并注册一个命令，不默认生成 WebUI；插件至少需要提供命令或 WebUI 中的一项。在非 TTY 环境中，或者用户传入任意初始化选项时，不会启动向导。这使 CI 和脚本调用保持确定性：

```bash
epack init demo \
    --id org.example.demo \
    --name Demo \
    --version 0.1.0 \
    --description "Demo Env plugin" \
    --author "Plugin Author" \
    --with-command
```

也可以使用选项直接指定能力而不进入向导：`--with-command` 或
`--without-command` 控制命令骨架，`--with-webui` 或 `--without-webui`
控制 WebUI 骨架。例如创建纯 WebUI 插件：

```bash
epack init demo-web --without-command --with-webui
```

选择命令能力会生成 `src/<module>/`、`cli.py` 和测试骨架，并在
`manifest.json` 中加入命令入口和后端 wheel；选择 WebUI 能力会生成
`frontend/index.html` 并加入 `manifest.webui`。两项都选择时会生成组合工程。

### 修改实现和清单

在 `src/org_example_demo/` 中实现命令逻辑，入口函数接收命令参数和 `RuntimeContext`。如果需要访问工作区、执行进程、访问网络或设备，必须在 `manifest.json` 中声明相应权限。SDK 会检查工作区路径边界，但插件仍与 Env 以同一用户身份运行，不是恶意代码沙箱。

CLI 插件的最小工程通常包含：

```text
demo/
├── manifest.json
├── LICENSE
└── src/org_example_demo/
    ├── __init__.py
    └── cli.py
```

### 校验、构建和检查

```bash
epack validate demo
epack build demo -o dist
epack inspect dist/org.example.demo-0.1.0-py3-none-any.epack
```

`epack build` 默认生成 `source-wheel`。如果要生成当前 CPython ABI 对应的字节码包，可以指定：

```bash
epack build demo -o dist --backend-format pyc-wheel
```

构建完成后，可以用 `epack inspect` 检查清单和完整性，而无需执行包内代码。随后用 Env 安装生成的包：

```bash
rt-env plugin install \
    dist/org.example.demo-0.1.0-py3-none-any.epack \
    --yes
org-example-demo
```

### WebUI 插件

WebUI 页面由 `manifest.webui` 声明，并以预构建静态资源放在 `frontend/` 中，例如：

```json
{
  "webui": {
    "entry": "frontend/index.html",
    "icon": "puzzle",
    "frontend_sdk": ">=1.0.0,<2.0.0"
  }
}
```

纯 WebUI 插件可以没有 `src/` 和后端 wheel；CLI 或健康检查存在时则必须提供后端 artifact。安装后启动本机 WebUI：

```bash
webui start
```

`webui start` 会在后台启动本机服务，普通本地会话默认打开浏览器，打印启动 URL
后返回命令行。可以使用以下命令查询或停止服务：

```bash
webui status
webui stop
```

如果服务已经启动，重复执行 `webui start` 只会提示当前 URL，不会再启动第二个服务。
服务状态保存在 `${ENV_ROOT}/var/plugins/runtime/` 下。需要前台运行时仍可使用旧的
`webui [workspace]` 形式；使用 `--no-browser` 禁止打开浏览器，在 SSH 会话中可用
`--browser` 强制打开浏览器。

插件页面运行在不带 `allow-same-origin` 的 iframe 中，宿主通过版本化 `postMessage` 传递主题和语言。页面不能读取宿主 Cookie、会话或直接调用 Env 生命周期 API。完整示例见 [`examples/build-insight-1.0.0/README.md`](examples/build-insight-1.0.0/README.md)。

## 构建和发布注意事项

- `manifest.json` 中的命令名必须唯一，并且不能与系统已有命令或其他插件冲突。
- `workspace.write` 已包含读取能力，不应同时声明 `workspace.read`。
- 使用依赖 wheel 时，需要按清单路径把文件放在工程的 `wheels/` 目录中。
- 前端资源必须是预构建文件；不能包含 source map、符号链接或路径穿越成员。
- v1 包目前是未签名的本地制品，不应将 `--yes` 作为不可信来源包的默认策略。
- 当前开源 WebUI 只接受本地文件，不会查询在线 catalog，也不会根据 URL 下载插件。
