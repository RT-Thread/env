# RT-Thread 关联兼容性 CI

Env 仓库本身不包含 RT-Thread 源码，但 RT-Thread 会把本仓库安装到 `~/.env/tools/scripts`，再执行：

- `source ~/.env/env.sh`
- `scons --pyconfig-silent`
- `pkgs --update` / `pkgs --list`
- `scons`

`.github/workflows/rt-thread-compat.yml` 用当前 Env 提交搭出同一套目录布局，再拉取 `RT-Thread/rt-thread`、`packages` 和 `sdk`，确认这条引用链不会被 Env 侧改动打断。兼容脚本位于 `.github/scripts/`，因为它们只服务于 GitHub Actions 及其本地复现。

## 本地运行

不要覆盖正在使用的 `~/.env`。可以在一次性 HOME 下运行：

```sh
export CI_HOME="$(mktemp -d)"
export HOME="$CI_HOME"
export RTT_ROOT=/path/to/rt-thread

./.github/scripts/prepare_env_layout.sh "$(pwd)" "$HOME/.env" \
    /path/to/packages /path/to/sdk
./.github/scripts/rt_thread_compat.sh
```

兼容脚本会从 SDK 索引安装 `arm-none-eabi-gcc`，不需要手动设置 `RTT_EXEC_PATH`。脚本会编译这两个 BSP：

- `bsp/qemu-vexpress-a9`
- `bsp/stm32/stm32f407-rt-spark`

## 检查范围

- Env 单元测试（Python 3.8 / 3.12）
- 从 SDK 索引安装 `arm-none-eabi-gcc`，并通过 Env 的 SDK 状态发现工具链
- `qemu-vexpress-a9` 的静默配置、包更新和 ARM GCC 编译
- `stm32/stm32f407-rt-spark` 的静默配置、包更新和 ARM GCC 编译
