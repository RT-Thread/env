# 极简工程

- 在env中引入[rt-env](https://github.com/RT-Thread/env/tree/standalone_project/env/site_tools)对scons的扩展tools；
  - 这样在未获得RT-Thread根目录及building.py扩展前获得一定的脚本支持；
  - 对于读入project.json的处理放在rt-env tools中；
- project.json中的特性包括：
  - RTT_ROOT，指向`rt-thread`的根目录，如果当前目录下存在`rt-thread`目录，则(优先)使用当前本地目录；
  - SDK_LIB，指向SDK的目录位置，如`${RTT_ROOT}/stm32/libraries`；
  - board，工程中使用的板卡相关信息
    - name，板卡名称，如`rt-spark`
    - path，板卡路径，如`stm32/stm32f407-rt-spark`
    - linker_script，链接脚本，如`board/linker_scripts/link.lds`
- 需要加入Kconfig的处理，这样可以能够正确配置`.config & rtconfig.h`文件

## 工程类型

- 工程应该可以分成三类（RT-Thread/BSP归入最后一类）
 - 传统`scons --dist`出的是一类，这类工程携带完整的rt-thread代码，及相关驱动；
 - 按支持到多固件编译的方式，和RT-Thread版本有些类似，但更本地化<例如针对stm32这样有SDK的公共驱动>
 - 传统的RT-Thread/BSP，在BSP目录下放置了繁多的BSP支持。

这三类中的前两类都可以很好的通过env创建出来工程，并在vscode扩展中很好的支持。
