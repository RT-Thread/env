# 极简工程

- 在env中引入rt-env的package，提供相关的支持<在导入rt-thread之前，可以获得python定制包支持>；
- 对于读入project.json的处理放在env中；
- project.json中的特性包括：
  - RTT_ROOT，指向`rt-thread`的根目录，如果当前目录下存在`rt-thread`目录，则(优先)使用当前本地目录；
  - SDK_LIB，指向SDK的目录位置，如`${RTT_ROOT}/stm32/libraries`；
  - board，工程中使用的板卡相关信息
    - name，板卡名称，如`rt-spark`
    - path，板卡路径，如`stm32/stm32f407-rt-spark`
    - linker_script，链接脚本，如`board/linker_scripts/link.lds`
