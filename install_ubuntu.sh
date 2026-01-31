#!/usr/bin/env bash
#
# DEPRECATED / 已废弃
#
# 此脚本已废弃，推荐直接使用 tools/install.sh
#
# Ubuntu Quick Install Script (Deprecated)
# Usage:
#   ./install_ubuntu.sh              # Auto-install (auto-detect mirror)
#   ./install_ubuntu.sh --cn        # Auto-install (China mirror)
#   ./install_ubuntu.sh --gitee     # Auto-install (Gitee)
#
# Deprecated: Please use tools/install.sh directly
#   curl https://raw.githubusercontent.com/RT-Thread/env/master/tools/install.sh | bash -s -- -y
#   curl https://gitee.com/RT-Thread-Mirror/env/raw/master/tools/install.sh | bash -s -- -y --cn
#
# This script maintains backward compatibility with old versions while
# delegating to the new unified install.sh script
#

set -e

# ============================================================================
# Configuration
# ============================================================================

# URL configurations
URL_GITHUB="https://raw.githubusercontent.com/RT-Thread/env/master/tools/install.sh"
URL_GITEE="https://gitee.com/RT-Thread-Mirror/env/raw/master/tools/install.sh"

# IP detection service
IPINFO_URL="https://ipinfo.io/json"

# Environment directory (compatible with old versions - use .env by default)
ENV_DEFAULT_DIR=".env"
: "${ENV_ROOT:=$HOME/$ENV_DEFAULT_DIR}"

# ============================================================================
# Activate Virtual Environment (for backward compatibility)
# ============================================================================

activate_venv() {
    # Activate the virtual environment if it exists
    local venv_path="$ENV_ROOT/venv/rt-env/bin/activate"
    if [ -f "$venv_path" ]; then
        source "$venv_path"
        echo "✓ Virtual environment activated"
    else
        echo "⚠ Virtual environment not found at $venv_path"
    fi
}

# ============================================================================
# Main
# ============================================================================

# Show deprecation notice
echo "============================================================"
echo "   DEPRECATED / 已废弃"
echo "============================================================"
echo ""
echo "此脚本已废弃，推荐直接使用 tools/install.sh"
echo "This script is deprecated, please use tools/install.sh directly"
echo ""
echo "使用 GitHub / Using GitHub:"
echo "  curl $URL_GITHUB | bash -s -- -y"
echo ""
echo "使用中国镜像 / Using China Mirror:"
echo "  curl $URL_GITEE | bash -s -- -y --cn"
echo ""
echo "============================================================"
echo ""

# Parse arguments
USE_CN=""
USE_CN_SET="false"
OTHER_ARGS=""

for arg in "$@"; do
    case "$arg" in
        --cn|--gitee)
            USE_CN="true"
            USE_CN_SET="true"
            ;;
        --no-mirror)
            USE_CN="false"
            USE_CN_SET="true"
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --cn, --gitee       Use China mirror (Gitee)"
            echo "  --no-mirror         Force use official GitHub source"
            echo "  --help, -h          Show this help"
            echo ""
            echo "This script downloads and executes the new install.sh with"
            echo "backward compatibility settings for old .env path and GitHub Actions."
            exit 0
            ;;
        *)
            OTHER_ARGS="$OTHER_ARGS $arg"
            ;;
    esac
done

# Auto-detect China if not explicitly set
if [[ "$USE_CN_SET" == "false" ]]; then
    USE_CN=$(detect_china)
fi

# Determine URL
if [[ "$USE_CN" == "true" ]]; then
    INSTALL_URL="$URL_GITEE"
else
    INSTALL_URL="$URL_GITHUB"
fi

echo "检测到位置: $([ "$USE_CN" == "true" ] && echo "中国大陆" || echo "其他地区")"
echo "下载地址: $INSTALL_URL"
echo ""

# Download and execute install.sh directly (without writing to disk)
wget -qO- "$INSTALL_URL" | bash -s -- -y --env-root "$ENV_ROOT" $OTHER_ARGS

# Activate virtual environment after installation
if [ -d "$ENV_ROOT" ]; then
    echo ""
    echo "============================================================"
    echo "激活虚拟环境 / Activating Virtual Environment"
    echo "============================================================"
    echo ""
    activate_venv
    echo ""
    echo "To activate the environment manually, run:"
    echo "  source $ENV_ROOT/env.sh"
    echo ""
fi
