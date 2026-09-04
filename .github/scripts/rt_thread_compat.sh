#!/usr/bin/env bash
# Exercise the Env layout the same way RT-Thread CI does:
# source env.sh, install the SDK toolchain, then configure, update packages,
# and build RT-Thread BSPs.

set -euo pipefail

ENV_ROOT=${ENV_ROOT:-$HOME/.env}
RTT_ROOT=${RTT_ROOT:?RTT_ROOT must point at an RT-Thread checkout}
QEMU_BSP=${QEMU_BSP:-bsp/qemu-vexpress-a9}
SPARK_BSP=${SPARK_BSP:-bsp/stm32/stm32f407-rt-spark}
SDK_TOOLCHAIN_VERSION=${SDK_TOOLCHAIN_VERSION:-v13.2.rel1}

fail() {
    echo "::error::$1" >&2
    exit 1
}

require_dir() {
    [ -d "$1" ] || fail "missing directory: $1"
}

require_file() {
    [ -f "$1" ] || fail "missing file: $1"
}

require_dir "$ENV_ROOT"
require_file "$ENV_ROOT/env.sh"
require_dir "$ENV_ROOT/tools/scripts"
require_dir "$RTT_ROOT"
require_file "$RTT_ROOT/$QEMU_BSP/Kconfig"
require_file "$RTT_ROOT/$SPARK_BSP/Kconfig"

export ENV_ROOT
export ENV_VENV_AUTO_UPGRADE=${ENV_VENV_AUTO_UPGRADE:-1}
export RTT_ROOT

# shellcheck disable=SC1091
. "$ENV_ROOT/env.sh"

command -v python3 >/dev/null || fail "python3 is not on PATH after sourcing env.sh"
command -v scons >/dev/null || fail "scons is not on PATH after sourcing env.sh"
command -v pkgs >/dev/null || fail "pkgs is not on PATH after sourcing env.sh"
command -v menuconfig >/dev/null || fail "menuconfig is not on PATH after sourcing env.sh"

python3 -c 'import kconfiglib, requests, SCons' || fail "Env Python dependencies are missing after activation"

if ! pkgs --printenv | grep -F "ENV_ROOT:$ENV_ROOT" >/dev/null; then
    fail "pkgs --printenv did not report ENV_ROOT=$ENV_ROOT"
fi
if ! pkgs --printenv | grep -F "PKGS_ROOT:$ENV_ROOT/packages" >/dev/null; then
    fail "pkgs --printenv did not report PKGS_ROOT=$ENV_ROOT/packages"
fi

python3 "$ENV_ROOT/tools/scripts/env.py" -v
pkgs -h >/dev/null
menuconfig -h >/dev/null

case "$SDK_TOOLCHAIN_VERSION" in
    v13.2.rel1)
        sdk_version_symbol=V132REL1
        ;;
    v10.3)
        sdk_version_symbol=V103
        ;;
    *)
        fail "unsupported SDK ARM GCC version: $SDK_TOOLCHAIN_VERSION"
        ;;
esac

sdk_config="$ENV_ROOT/tools/scripts/.config"
printf '%s\n' \
    'CONFIG_TARGET_FILE=""' \
    'CONFIG_PKG_USING_ARM_NONE_EABI_GCC=y' \
    'CONFIG_PKG_ARM_NONE_EABI_GCC_PATH="sdk/Linux/arm-none-eabi-gcc"' \
    "CONFIG_PKG_USING_ARM_NONE_EABI_GCC_${sdk_version_symbol}=y" \
    "CONFIG_PKG_ARM_NONE_EABI_GCC_VER=\"$SDK_TOOLCHAIN_VERSION\"" \
    > "$sdk_config"

echo "==> Install ARM GCC $SDK_TOOLCHAIN_VERSION from the SDK index"
(
    cd "$ENV_ROOT/tools/scripts"
    pkgs --update-force
    pkgs --list
)

sdk_toolchain_root="$ENV_ROOT/tools/scripts/packages/arm-none-eabi-gcc-$SDK_TOOLCHAIN_VERSION"
if [ -z "$sdk_toolchain_root" ] || [ ! -x "$sdk_toolchain_root/bin/arm-none-eabi-gcc" ]; then
    fail "SDK did not install arm-none-eabi-gcc"
fi
"$sdk_toolchain_root/bin/arm-none-eabi-gcc" --version

if [ -f "$RTT_ROOT/tools/requirements.txt" ]; then
    python3 -m pip install -r "$RTT_ROOT/tools/requirements.txt"
fi

run_bsp() {
    bsp_rel=$1
    bsp_dir="$RTT_ROOT/$bsp_rel"

    echo "==> RT-Thread Env steps for $bsp_rel"
    scons --pyconfig-silent -C "$bsp_dir"
    require_file "$bsp_dir/.config"
    require_file "$bsp_dir/rtconfig.h"

    (
        cd "$bsp_dir"
        pkgs --update-force
        pkgs --list
    )
    require_file "$bsp_dir/packages/SConscript"

    echo "==> Build $bsp_rel"
    scons -j"$(nproc)" -C "$bsp_dir"
}

run_bsp "$QEMU_BSP"
run_bsp "$SPARK_BSP"

echo "RT-Thread Env compatibility checks passed."
