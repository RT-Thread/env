#!/usr/bin/env bash

# 函数：从 AUR 安装 rt-thread-env-meta 包
install_from_aur() {
    echo "正在从 AUR 安装 rt-thread-env-meta 包..."
    yay -Syu rt-thread-env-meta
}

# 函数：手动安装所需的包
install_manually() {
    echo "正在手动安装所需的包..."

    # 安装基本依赖包
    sudo pacman -Syu python python-pip gcc git ncurses \
        arm-none-eabi-gcc arm-none-eabi-gdb \
        qemu-desktop qemu-system-arm-firmware scons \
        python-requests python-tqdm python-kconfiglib

    # 提示用户安装 python-pyocd 及其插件
    echo "
    # python-pyocd 可以通过 AUR 安装或从 GitHub 获取:
    # https://github.com/taotieren/aur-repo
    yay -Syu python-pyocd python-pyocd-pemicro
    "

    # 询问用户是否要继续安装 python-pyocd
    read -p "是否现在安装 python-pyocd 和 python-pyocd-pemicro? (y/n) " choice
    case "$choice" in
    y | Y)
        yay -Syu python-pyocd python-pyocd-pemicro
        ;;
    n | N)
        echo "跳过安装 python-pyocd 和 python-pyocd-pemicro."
        ;;
    *)
        echo "无效输入，跳过安装 python-pyocd 和 python-pyocd-pemicro."
        ;;
    esac
}

# 显示菜单供用户选择
echo "请选择安装方式:"
echo "1. 从 AUR 安装 rt-thread-env-meta 包"
echo "2. 手动安装所有所需包"
read -p "请输入选项 [1 或 2]: " option

case $option in
1)
    install_from_aur
    ;;
2)
    install_manually
    ;;
*)
    echo "无效选项，退出安装程序。"
    exit 1
    ;;
esac

echo "安装完成。"

url=https://raw.githubusercontent.com/RT-Thread/env/master/touch_env.sh
if [ $1 ] && [ $1 = --gitee ]; then
    url=https://gitee.com/RT-Thread-Mirror/env/raw/master/touch_env.sh
fi

wget $url -O touch_env.sh
chmod 777 touch_env.sh
./touch_env.sh $@
rm touch_env.sh
