#!/usr/bin/env bash
# Create the ~/.env layout that RT-Thread CI and local builds expect, using
# the Env source under test instead of cloning env master.

set -euo pipefail

usage() {
    echo "Usage: $0 <env-source> [env-root] [packages-src] [sdk-src]" >&2
    exit 2
}

if [ "${1:-}" = "" ]; then
    usage
fi

ENV_SOURCE=$(cd -- "$1" && pwd)
ENV_ROOT=${2:-${ENV_ROOT:-$HOME/.env}}
PACKAGES_SRC=${3:-${PACKAGES_SRC:-}}
SDK_SRC=${4:-${SDK_SRC:-}}
PACKAGE_URL=${RTT_PACKAGE_URL:-https://github.com/RT-Thread/packages.git}
SDK_URL=${RTT_SDK_URL:-https://github.com/RT-Thread/sdk.git}

mkdir -p "$ENV_ROOT/local_pkgs" "$ENV_ROOT/packages" "$ENV_ROOT/tools"

if [ -e "$ENV_ROOT/tools/scripts" ] || [ -L "$ENV_ROOT/tools/scripts" ]; then
    echo "Refusing to replace existing Env scripts directory: $ENV_ROOT/tools/scripts" >&2
    exit 1
fi
if [ -e "$ENV_ROOT/env.sh" ]; then
    echo "Refusing to replace existing Env activation script: $ENV_ROOT/env.sh" >&2
    exit 1
fi
if [ -e "$ENV_ROOT/packages/Kconfig" ]; then
    echo "Refusing to replace existing packages Kconfig: $ENV_ROOT/packages/Kconfig" >&2
    exit 1
fi

ln -s "$ENV_SOURCE" "$ENV_ROOT/tools/scripts"
cp "$ENV_SOURCE/env.sh" "$ENV_ROOT/env.sh"

link_or_clone() {
    dest=$1
    src=$2
    url=$3
    name=$4

    if [ -d "$dest/.git" ] || [ -L "$dest" ]; then
        echo "Using existing $name at $dest"
        return 0
    fi
    if [ -e "$dest" ]; then
        echo "Refusing to replace existing $name path: $dest" >&2
        exit 1
    fi
    if [ -n "$src" ]; then
        src=$(cd -- "$src" && pwd)
        ln -s "$src" "$dest"
        echo "Linked $name from $src"
        return 0
    fi
    git clone --depth=1 "$url" "$dest"
}

link_or_clone "$ENV_ROOT/packages/packages" "$PACKAGES_SRC" "$PACKAGE_URL" "packages index"
link_or_clone "$ENV_ROOT/packages/sdk" "$SDK_SRC" "$SDK_URL" "SDK index"

printf 'source "$PKGS_DIR/packages/Kconfig"\n' > "$ENV_ROOT/packages/Kconfig"

echo "Env layout ready:"
echo "  ENV_ROOT=$ENV_ROOT"
echo "  scripts=$ENV_ROOT/tools/scripts -> $ENV_SOURCE"
