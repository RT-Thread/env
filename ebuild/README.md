# EBuild 嵌入式构建系统

EBuild (Embedded Build System) 是一个基于 SCons 的统一嵌入式构建框架，为嵌入式项目提供配置管理、工具链配置、组件注册和工程导出等一站式解决方案。

## 特性

- **统一构建入口** - 通过 `PrepareBuilding`/`DoBuilding` 简化构建流程
- **灵活配置管理** - 支持 menuconfig 图形配置和 attachconfig 快速配置方案
- **智能工具链检测** - 自动从 `~/.env` 或项目配置检测 GCC 工具链路径
- **组件化构建** - 支持 `DefineGroup` 和 `package.json` 两种组件组织方式
- **多 IDE 支持** - 可导出 VS Code、CMake、Keil MDK 工程文件
- **条件编译** - 基于配置项的依赖检查和条件编译支持

## 快速开始

### 基本使用

在项目根目录的 `SConstruct` 中：

```python
from ebuild import PrepareBuilding, DoBuilding

# 准备构建环境
env = Environment()
build = PrepareBuilding(env, proj_config=proj_config)

# 注册组件（在 SConscript 中）
# env.DefineGroup('my_component', ['src/*.c'], depend=['CONFIG_MY_FEATURE'])

# 执行构建
DoBuilding(env, 'target.elf')
```

### 配置项目

```bash
# 打开图形配置界面
scons --menuconfig

# 查看可用的 attachconfig 配置方案
scons --attach=?

# 应用某个配置方案
scons --attach=stm32f103-basic
```

### 构建项目

```bash
# 默认构建
scons

# 清理构建
scons -c

# 详细输出
scons --verbose
```

### 导出工程

```bash
# 导出 VS Code 工程
scons --target=vscode

# 导出 CMake 工程
scons --target=cmake

# 导出 Keil MDK 工程
scons --target=mdk5
```

## 核心概念

### 配置文件

- **proj_config.py** - 项目配置，定义工具链、MCU 系列、工程名称等
- **proj_config.h** - 由 menuconfig 生成的 C 头文件，包含所有配置宏
- **Kconfig** - menuconfig 配置描述文件

ProjectRoot 指 SCons 的执行根目录（`scons` 或 `scons -C dir` 的 `dir`），上述配置文件与 `.config`、`.ci/attachconfig` 都应位于该目录下。

### 组件注册

EBuild 提供两种组件组织方式：

#### 1. DefineGroup

```python
# 在 SConscript 中
src = ['init.c', 'driver.c']
depend = ['CONFIG_USE_DRIVER']
CPPPATH = ['./include']
CPPDEFINES = ['DEBUG_MODE=1']

env.DefineGroup('my_component', src, depend=depend, CPPPATH=CPPPATH, CPPDEFINES=CPPDEFINES)
```

#### 2. package.json

```json
{
    "type": "rt-thread-component",
    "name": "my_component",
    "dependencies": ["CONFIG_USE_DRIVER"],
    "defines": ["DEBUG_MODE=1"],
    "sources": [
        {
            "dependencies": [],
            "includes": ["./include"],
            "files": ["*.c"]
        }
    ]
}
```

### 工具链配置

EBuild 支持多种工具链配置方式：

1. **自动检测** - 从 `~/.env/tools/scripts/packages` 自动检测
2. **proj_config.py** - 设置 `EXEC_PATH` 和 `CC_PREFIX`
3. **命令行参数** - 使用 `--cross-compile`、`--cpu` 等

```python
# proj_config.py 示例
TOOLCHAIN_CONFIG = {
    'CC_PREFIX': 'arm-none-eabi-',
    'EXEC_PATH': '/opt/gcc-arm-none-eabi/bin',
    'MCU_SERIES': {
        'CONFIG_STM32F103': {
            'cpu': 'cortex-m3',
            'link_script': 'linkstm32f103xe.ld'
        }
    },
    'BUILD': 'release'  # or 'debug'
}

# 可选：构建结束后执行的动作（如生成 bin）
POST_ACTION = "$OBJCOPY -O binary $TARGET build/stm32f103.bin"
```

## 命令行选项

| 选项 | 说明 |
|------|------|
| `--target=TYPE` | 导出工程：mdk4/mdk5/cmake/vscode |
| `--menuconfig` | 打开配置菜单 |
| `--attach=NAME` | 应用 attachconfig 方案（`?` 查看列表，`default` 恢复） |
| `--verbose` | 显示完整编译命令 |
| `--cross-compile=PREFIX` | 交叉编译器前缀 |
| `--cpu=CPU` | 目标 CPU 类型 |
| `--fpu=FPU` | FPU 类型 |
| `--float-abi=ABI` | 浮点 ABI |

## 支持的工具链

| 架构 | 配置模块 |
|------|----------|
| ARM | `ebuild.configs.arm_gcc` |
| AArch64 | `ebuild.configs.aarch64_gcc` |
| RISC-V | `ebuild.configs.riscv_gcc` |
| Linux | `ebuild.configs.linux_gcc` |

## 项目结构

```
project/
├── SConstruct              # 主构建脚本
├── proj_config.py          # 项目配置
├── Kconfig                 # 配置菜单定义
├── proj_config.h           # 生成的配置头文件
├── .config                 # menuconfig 配置输出
├── SConscript              # 组件注册脚本
├── .vscode/                # VS Code 配置（导出后）
├── CMakeLists.txt          # CMake 配置（导出后）
└── *.uvprojx               # Keil 工程（导出后）
```

## 高级功能

### AttachConfig 快速配置

AttachConfig 允许预定义常用配置方案，快速切换：

```bash
# 查看可用方案
scons --attach=?

# 应用方案
scons --attach=nrf52832-peripheral

# 恢复默认配置
scons --attach=default
```

### 条件编译

```python
# 仅当依赖满足时才编译该组件
env.DefineGroup('feature_x', ['feature_x.c'], depend=['CONFIG_FEATURE_X'])
```

### 包构建

```python
# 扫描并构建当前目录下的 package.json
env.BuildPackage('.')

# 构建指定路径的包
env.BuildPackage('path/to/package')
```

### 桥接模式

```python
# 自动扫描子目录并执行其中的 SConscript
groups = env.Bridge()
```

## API 参考

### 核心函数

- `PrepareBuilding(env, proj_config)` - 初始化构建系统
- `DoBuilding(env, target, objs)` - 执行构建或导出

### SCons 环境方法

- `env.DefineGroup(name, src, depend, **kwargs)` - 注册组件组
- `env.BuildPackage(path)` - 构建 package.json 组件
- `env.Bridge()` - 桥接子目录组件
- `env.GetDepend(dep)` - 检查配置依赖
- `env.GlobFiles(pattern)` - 获取文件列表
- `env.SrcRemove(src, remove)` - 从源文件列表中移除
- `env.DoBuilding(target, objs)` - 执行构建

## 安装依赖

```bash
# 安装 SCons
pip install scons

# 安装 kconfiglib（用于 menuconfig）
pip install kconfiglib

# 安装 PyYAML（用于 attachconfig）
pip install pyyaml
```

## 许可证

本项目为内部构建工具，遵循项目许可证。
