#!/usr/bin/env bash
#
# File      : install.sh
# This file is part of RT-Thread RTOS
# COPYRIGHT (C) 2006 - 2026, RT-Thread Development Team
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License along
#  with this program; if not, write to the Free Software Foundation, Inc.,
#  51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Change Logs:
# Date           Author          Notes
# 2026-01-31     dongly         Refactored

# RT-Thread ENV Installation Script (Unix)
# Unified installation script for Linux and macOS
# Supports: English / 中文
#
# Usage:
#   ./install.sh [-y] [-c] [-o] [-d] [-r <path>] [-e|-z] [-P <repo>[#<branch>]] [-E <repo>[#<branch>]] [-S <repo>[#<branch>]] [-b <strategy>] [-t <url>] [-h]
#
# Options:
#   -y, --yes, --auto    Auto-install without prompts
#   -c, --cn, --gitee    Use China mirror (Gitee, PyPI TUNA)
#   -o, --official       Force use official source
#   -d, --pyocd          Install pyocd for debugging
#   -r, --env-root <path> Set custom install directory
#   -e, --en, --english  Force English messages
#   -z, --zh, --chinese  Force Chinese messages
#   -P, --packages <repo>[#<branch>]  Specify custom packages repository and branch
#   -E, --env <repo>[#<branch>]  Specify custom env repository and branch
#   -S, --sdk <repo>[#<branch>]  Specify custom sdk repository and branch
#   -b, --backup <strategy> Backup strategy when ENV exists:
#                          preserve: Keep .config and local_pkgs, restore and delete backup
#                                    保留 .config 和 local_pkgs，恢复后删除备份
#                          delete_all: Backup then delete everything, no restore
#                                    备份后删除所有内容，不恢复
#                          delete_all_now: Delete everything immediately, no backup
#                                    立即删除所有内容，不备份
#                          backup_all: Keep backup with hardlink restore
#                                    保留备份，用硬链接恢复工具链
#   -t, --touch-env-url <url> Specify touch_env.py download URL
#   -h, --help           Show this help message
#

# ============================================================================
# Configuration
# ============================================================================

# Verify script is running in bash or zsh
if [ -z "$BASH_VERSION" ] && [ -z "$ZSH_VERSION" ]; then
    echo "Error: This script must be run with bash or zsh, not sh" >&2
    exit 1
fi

# Global configuration variables (like $script:Config in PowerShell)
CONFIG_AUTO_MODE=false
CONFIG_HELP_MODE=false
CONFIG_PYOCD_MODE=false
CONFIG_ENV_ROOT=""
CONFIG_LANG="en"
CONFIG_USE_CN_SET=false
CONFIG_USE_CN=false
CONFIG_CUSTOM_PACKAGES_REPO=""
CONFIG_CUSTOM_ENV_REPO=""
CONFIG_CUSTOM_SDK_REPO=""
CONFIG_BACKUP_STRATEGY=""
CONFIG_TOUCH_ENV_URL_VALUE=""

# Global variables for user context (initialized in init_environment)
REAL_USER_HOME=""
REAL_USER=""
REAL_USER_SHELL=""

# Global variable for tracking temporary files (for cleanup)
TEMP_FILES=()

# IP detection service
IPINFO_URL="https://ipinfo.io/json"

# Homebrew installation script
HOMEBREW_INSTALL_URL="https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh"

# touch_env.py download URLs
TOUCH_ENV_URL_GITHUB="https://raw.githubusercontent.com/RT-Thread/env/master/tools/touch_env.py"
TOUCH_ENV_URL_GITEE="https://gitee.com/RT-Thread-Mirror/env/raw/master/tools/touch_env.py"

# ============================================================================
# Message Dictionary (Centralized i18n messages like PowerShell $script:Messages)
# ============================================================================

declare -A MESSAGES_EN=(
    ["banner_title"]="RT-Thread ENV Installation"
    ["info"]="INFO"
    ["success"]="SUCCESS"
    ["warning"]="WARNING"
    ["error"]="ERROR"
    ["git_not_found"]="Git is not installed. Please install Git first."
    ["git_found"]="Git version: %s"
    ["start"]="Starting RT-Thread ENV installation..."
    ["installing_ubuntu"]="Installing dependencies (Ubuntu/Debian)..."
    ["installing_suse"]="Installing dependencies (SUSE/openSUSE)..."
    ["installing_arch"]="Installing dependencies (Arch/Manjaro)..."
    ["installing_fedora"]="Installing dependencies (Fedora/RHEL/CentOS)..."
    ["installing_alpine"]="Installing dependencies (Alpine)..."
    ["unsupported_os"]="Unsupported OS: %s"
    ["missing_gcc"]="Missing GCC compiler, please install manually"
    ["installing_homebrew"]="Installing Homebrew..."
    ["installing_macos"]="Installing dependencies (macOS)..."
    ["missing_python"]="Python 3 not found. Please install Python first."
    ["python_version"]="Python version: %s"
    ["using_cn_mirror"]="Using China mirror"
    ["using_official_source"]="Using official source"
    ["downloading_touch_env"]="Downloading touch_env.py from: %s"
    ["touch_env_downloaded"]="touch_env.py downloaded successfully."
    ["touch_env_failed"]="touch_env.py execution failed with exit code: %s"
    ["touch_env_download_failed"]="Failed to download touch_env.py: %s"
)

declare -A MESSAGES_ZH=(
    ["banner_title"]="RT-Thread ENV 安装程序"
    ["info"]="信息"
    ["success"]="成功"
    ["warning"]="警告"
    ["error"]="错误"
    ["git_not_found"]="未安装 Git。请先安装 Git。"
    ["git_found"]="Git 版本: %s"
    ["start"]="开始启动 RT-Thread ENV 安装..."
    ["installing_ubuntu"]="正在安装依赖 (Ubuntu/Debian)..."
    ["installing_suse"]="正在安装依赖 (SUSE/openSUSE)..."
    ["installing_arch"]="正在安装依赖 (Arch/Manjaro)..."
    ["installing_fedora"]="正在安装依赖 (Fedora/RHEL/CentOS)..."
    ["installing_alpine"]="正在安装依赖 (Alpine)..."
    ["unsupported_os"]="不支持的操作系统: %s"
    ["missing_gcc"]="缺少 GCC 编译器，请手动安装"
    ["installing_homebrew"]="正在安装 Homebrew..."
    ["installing_macos"]="正在安装依赖 (macOS)..."
    ["missing_python"]="未找到 Python 3，请先安装"
    ["python_version"]="Python 版本: %s"
    ["using_cn_mirror"]="使用中国镜像源"
    ["using_official_source"]="使用官方源"
    ["downloading_touch_env"]="正在下载 touch_env.py，自: %s"
    ["touch_env_downloaded"]="touch_env.py 下载完成。"
    ["touch_env_failed"]="touch_env.py 执行失败，退出码: %s"
    ["touch_env_download_failed"]="下载 touch_env.py 失败: %s"
)

# ============================================================================
# Initialization Functions
# ============================================================================

init_environment() {
    # Get real user's home directory (handles sudo case)
    if [ -n "$SUDO_USER" ]; then
        # Running with sudo, use the original user's home
        REAL_USER_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
        REAL_USER="$SUDO_USER"
        # Get the real user's default shell from /etc/passwd
        REAL_USER_SHELL=$(getent passwd "$SUDO_USER" | cut -d: -f7)
    else
        # Running without sudo
        REAL_USER_HOME="$HOME"
        REAL_USER="$USER"
        REAL_USER_SHELL="$SHELL"
    fi

    # Detect language based on IP or system locale
    detect_china
}

# Cleanup function for temporary files
cleanup() {
    for temp_file in "${TEMP_FILES[@]}"; do
        rm -f "$temp_file" 2>/dev/null
    done
}

# Register cleanup handler for exit signals
trap cleanup EXIT INT TERM

# ============================================================================
# Message Functions
# ============================================================================

# Get message from dictionary (similar to PowerShell Get-Message)
get_message() {
    local key="$1"

    # Select appropriate language dictionary
    if [ "$CONFIG_LANG" = "zh" ]; then
        if [ -n "${MESSAGES_ZH[$key]+isset}" ]; then
            echo "${MESSAGES_ZH[$key]}"
        else
            echo "Unknown message: $key"
        fi
    else
        if [ -n "${MESSAGES_EN[$key]+isset}" ]; then
            echo "${MESSAGES_EN[$key]}"
        else
            echo "Unknown message: $key"
        fi
    fi
}

# Log functions (similar to PowerShell Write-LogInfo/Success/Warning/Error)
log_info() {
    local key="$1"
    shift
    local msg
    msg=$(get_message "$key")

    # Format message with arguments
    if [ $# -gt 0 ]; then
        # shellcheck disable=SC2059
        printf "\033[0;34m[%s]\033[0m ${msg}\n" "$(get_message 'info')" "$@" >&2
    else
        printf "\033[0;34m[%s]\033[0m ${msg}\n" "$(get_message 'info')" >&2
    fi
}

log_success() {
    local key="$1"
    shift
    local msg
    msg=$(get_message "$key")

    if [ $# -gt 0 ]; then
        # shellcheck disable=SC2059
        printf "\033[0;32m[%s]\033[0m ${msg}\n" "$(get_message 'success')" "$@" >&2
    else
        printf "\033[0;32m[%s]\033[0m ${msg}\n" "$(get_message 'success')" >&2
    fi
}

log_warning() {
    local key="$1"
    shift
    local msg
    msg=$(get_message "$key")

    if [ $# -gt 0 ]; then
        # shellcheck disable=SC2059
        printf "\033[1;33m[%s]\033[0m ${msg}\n" "$(get_message 'warning')" "$@" >&2
    else
        printf "\033[1;33m[%s]\033[0m ${msg}\n" "$(get_message 'warning')" >&2
    fi
}

log_error() {
    local key="$1"
    shift
    local msg
    msg=$(get_message "$key")

    if [ $# -gt 0 ]; then
        # shellcheck disable=SC2059
        printf "\033[0;31m[%s]\033[0m ${msg}\n" "$(get_message 'error')" "$@" >&2
    else
        printf "\033[0;31m[%s]\033[0m ${msg}\n" "$(get_message 'error')" >&2
    fi
}

# ============================================================================
# Download and Execute touch_env.py Functions
# ============================================================================

download_and_run_touch_env() {
    # Create temp file
    local touch_env_dest
    touch_env_dest=$(mktemp --suffix=.py)

    # Track temp file for cleanup
    TEMP_FILES+=("$touch_env_dest")

    # Download touch_env.py (determines URL internally)
    download_touch_env "$touch_env_dest" || {
        return 1
    }

    # Run touch_env.py
    run_touch_env "$touch_env_dest" || {
        return 1
    }

    # Temp file will be cleaned up by trap handler

    return 0
}

download_touch_env() {
    local touch_env_dest="$1"

    # Determine touch_env.py download URL
    local touch_env_download_url="$TOUCH_ENV_URL_GITHUB"

    if [ -n "$CONFIG_TOUCH_ENV_URL_VALUE" ]; then
        touch_env_download_url="$CONFIG_TOUCH_ENV_URL_VALUE"
    elif [ -n "$CONFIG_CUSTOM_ENV_REPO" ]; then
        # Parse URL and branch from string (format: url[#branch])
        local repo="$CONFIG_CUSTOM_ENV_REPO"
        local branch="master"
        if [[ "$repo" == *"#"* ]]; then
            branch="${repo#*#}"
            repo="${repo%#*}"
        fi

        # Convert GitHub repo URL to raw.githubusercontent.com URL
        if [[ "$repo" =~ ^https?://github\.com/([^/]+)/([^/]+?)(\.git)?$ ]]; then
            local owner="${BASH_REMATCH[1]}"
            local repo_name="${BASH_REMATCH[2]%.git}"
            touch_env_download_url="https://raw.githubusercontent.com/$owner/$repo_name/$branch/tools/touch_env.py"
        else
            # Non-GitHub repository: use /raw/ format
            touch_env_download_url="$repo/raw/$branch/tools/touch_env.py"
        fi
    elif [ "$CONFIG_USE_CN" = "true" ]; then
        touch_env_download_url="$TOUCH_ENV_URL_GITEE"
    fi

    log_info "downloading_touch_env" "$touch_env_download_url"

    # Download touch_env.py
    if command -v curl &> /dev/null 2>&1; then
        curl -fsSL --connect-timeout 30 "$touch_env_download_url" -o "$touch_env_dest"
    elif command -v wget &> /dev/null 2>&1; then
        wget --timeout=30 -O "$touch_env_dest" "$touch_env_download_url"
    else
        log_error "touch_env_download_failed" "$touch_env_download_url"
        return 1
    fi

    if [ ! -s "$touch_env_dest" ]; then
        log_error "touch_env_download_failed" "$touch_env_download_url"
        return 1
    fi

    log_success "touch_env_downloaded"
}

run_touch_env() {
    local touch_env_dest="$1"

    # Build Python command arguments for touch_env.py
    local python_args=()

    if [ -n "$CONFIG_ENV_ROOT" ]; then
        python_args+=("--env-root" "$CONFIG_ENV_ROOT")
    fi

    if [ "$CONFIG_USE_CN" = "true" ]; then
        python_args+=("--use-cn")
    fi

    if [ "$CONFIG_LANG" = "en" ]; then
        python_args+=("--language" "en")
    elif [ "$CONFIG_LANG" = "zh" ]; then
        python_args+=("--language" "zh")
    fi

    if [ "$CONFIG_AUTO_MODE" = "true" ]; then
        python_args+=("--auto-mode")
    fi

    if [ -n "$CONFIG_BACKUP_STRATEGY" ]; then
        python_args+=("--backup" "$CONFIG_BACKUP_STRATEGY")
    fi

    if [ "$CONFIG_PYOCD_MODE" = "true" ]; then
        python_args+=("--install-pyocd")
    fi

    # Custom repositories (pass full URL, touch_env.py parses branch if present)
    if [ -n "$CONFIG_CUSTOM_PACKAGES_REPO" ]; then
        python_args+=("--repo-packages" "$CONFIG_CUSTOM_PACKAGES_REPO")
    fi

    if [ -n "$CONFIG_CUSTOM_ENV_REPO" ]; then
        python_args+=("--repo-env" "$CONFIG_CUSTOM_ENV_REPO")
    fi

    if [ -n "$CONFIG_CUSTOM_SDK_REPO" ]; then
        python_args+=("--repo-sdk" "$CONFIG_CUSTOM_SDK_REPO")
    fi

    log_info "start"

    # Execute touch_env.py as REAL_USER
    if [ -n "$SUDO_USER" ]; then
        su "$REAL_USER" -c "python3 '$touch_env_dest' ${python_args[*]}"
    else
        python3 "$touch_env_dest" "${python_args[@]}"
    fi

    local result=$?

    if [ $result -ne 0 ]; then
        log_error "touch_env_failed" "$result"
        return 1
    fi

    return 0
}

# ============================================================================
# Argument Parsing
# ============================================================================

print_help() {
    echo "$(get_message 'banner_title')"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -y, --yes, --auto    Auto-install without prompts"
    echo "  -c, --cn, --gitee    Use China mirror (Gitee, PyPI TUNA)"
    echo "  -o, --official       Force use official source"
    echo "  -d, --pyocd          Install pyocd for debugging"
    echo "  -r, --env-root <path> Set custom install directory"
    echo "  -e, --en, --english  Force English messages"
    echo "  -z, --zh, --chinese  Force Chinese messages"
    echo "  -P, --packages <repo>[#<branch>]  Specify custom packages repository and branch"
    echo "  -E, --env <repo>[#<branch>]  Specify custom env repository and branch"
    echo "  -S, --sdk <repo>[#<branch>]  Specify custom sdk repository and branch"
    echo "  -b, --backup <strategy> Backup strategy (preserve/delete_all/delete_all_now/backup_all)"
    echo "                          preserve: Keep .config and local_pkgs, restore and delete backup"
    echo "                                    保留 .config 和 local_pkgs，恢复后删除备份"
    echo "                          delete_all: Backup then delete everything, no restore"
    echo "                                    备份后删除所有内容，不恢复"
    echo "                          delete_all_now: Delete everything immediately, no backup"
    echo "                                    立即删除所有内容，不备份"
    echo "                          backup_all: Keep backup with hardlink restore"
    echo "                                    保留备份，用硬链接恢复工具链"
    echo "  -t, --touch-env-url <url> Specify touch_env.py download URL"
    echo "  -h, --help           Show this help message"
    echo ""
}

check_git() {
    if ! command -v git &> /dev/null; then
        log_error "git_not_found"
        return 1
    fi
    local git_version
    git_version=$(git --version 2>&1 | grep -E 'git version' | awk '{print $3}')
    log_info "git_found" "$git_version"
    return 0
}

detect_china() {
    # Check if user is in China (by IP or system locale)
    # Only set CONFIG_USE_CN, don't override CONFIG_LANG (which may be set by --en/--zh)
    if [ "$CONFIG_USE_CN_SET" = "true" ]; then
        return  # User explicitly set mirror, skip detection
    fi

    # Check IP-based detection (works on all systems)
    if command -v curl &> /dev/null 2>&1; then
        local ip_info=$(curl -s -m 5 --connect-timeout 3 "$IPINFO_URL" 2>&1)
        if [[ "$ip_info" == *"\"country\":\"CN\""* ]]; then
            CONFIG_USE_CN="true"
            return
        fi
    fi

    # Fallback: check system timezone
    local timezone=$(date +%Z 2>/dev/null || timedatectl show -p Timezone --value 2>/dev/null || echo "")
    if [[ "$timezone" == *"CST"* ]] || [[ "$timezone" == *"Shanghai"* ]] || [[ "$timezone" == *"Beijing"* ]] || [[ "$timezone" == *"Asia/Shanghai"* ]]; then
        CONFIG_USE_CN="true"
        return
    fi

    # Fallback: check system locale - only set CONFIG_USE_CN
    case "${LC_ALL}:${LANG}" in
        *zh*|*CN*)
            CONFIG_USE_CN="true"
            ;;
    esac
}

parse_args() {
    # Local state variables for parse_args (not global config)
    CONFIG_LANG_SET="false"
    CONFIG_OFFICIAL_MODE="false"
    CONFIG_CUSTOM_PACKAGES_BRANCH=""
    CONFIG_CUSTOM_ENV_BRANCH=""
    CONFIG_CUSTOM_SDK_BRANCH=""

    while [ $# -gt 0 ]; do
        case "$1" in
            -h|--help)
                CONFIG_HELP_MODE="true"
                ;;
            -y|--yes|--auto)
                CONFIG_AUTO_MODE="true"
                ;;
            -e|--en|--english)
                CONFIG_EN_MODE="true"
                CONFIG_LANG="en"
                CONFIG_LANG_SET="true"
                ;;
            -z|--zh|--chinese)
                CONFIG_ZH_MODE="true"
                CONFIG_LANG="zh"
                CONFIG_LANG_SET="true"
                ;;
            -r|--env-root)
                shift
                CONFIG_ENV_ROOT="$1"
                ENV_ROOT="$1"
                ;;
            -P|--packages)
                shift
                CONFIG_CUSTOM_PACKAGES_REPO="$1"
                ;;
            -E|--env)
                shift
                CONFIG_CUSTOM_ENV_REPO="$1"
                ;;
            -S|--sdk)
                shift
                CONFIG_CUSTOM_SDK_REPO="$1"
                ;;
            -c|--cn|--gitee)
                CONFIG_CN_MODE="true"
                CONFIG_USE_CN_SET="true"
                CONFIG_USE_CN="true"
                CONFIG_LANG="zh"
                ;;
            -o|--official)
                CONFIG_OFFICIAL_MODE="true"
                CONFIG_USE_CN_SET="true"
                ;;
            -d|--pyocd)
                CONFIG_PYOCD_MODE="true"
                ;;
            -b|--backup)
                shift
                CONFIG_BACKUP_STRATEGY="$1"
                ;;
            -t|--touch-env-url)
                shift
                CONFIG_TOUCH_ENV_URL_VALUE="$1"
                ;;
            *)
                # Unknown argument, skip
                ;;
        esac
        shift
    done

    # IP detection (lower priority, only if not explicitly set)
    if [ "$CONFIG_USE_CN_SET" = "false" ]; then
        detect_china
    fi

    # Override with --official flag
    if [ "$CONFIG_OFFICIAL_MODE" = "true" ]; then
        CONFIG_USE_CN="false"
    fi

    # Set language based on CONFIG_USE_CN if not explicitly set
    if [ "$CONFIG_LANG_SET" = "false" ]; then
        if [ "$CONFIG_USE_CN" = "true" ]; then
            CONFIG_LANG="zh"
        else
            CONFIG_LANG="en"
        fi
    fi
}

# ============================================================================
# System Detection
# ============================================================================

detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    else
        echo "unknown"
    fi
}

detect_linux_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        echo "$ID"
    elif [ -f /etc/redhat-release ]; then
        echo "rhel"
    else
        echo "unknown"
    fi
}

# ============================================================================
# Dependency Installation
# ============================================================================

install_dependencies_linux() {
    local distro
    local sudo_cmd=""
    
    if [ "$EUID" -ne 0 ]; then
        sudo_cmd="sudo"
    fi
    
    distro=$(detect_linux_distro)

    case "$distro" in
        ubuntu|debian)
            log_info "installing_ubuntu"
            $sudo_cmd apt-get update -qq
            $sudo_cmd apt-get install -y python3 python3-venv python3-pip git gcc libncurses-dev
            ;;
        suse|opensuse*)
            log_info "installing_suse"
            $sudo_cmd zypper install -y python3 python3-venv python3-pip git gcc ncurses-devel
            ;;
        arch|manjaro)
            log_info "installing_arch"
            $sudo_cmd pacman -S --noconfirm python python-pip git gcc ncurses
            ;;
        rhel|centos|fedora)
            log_info "installing_fedora"
            $sudo_cmd dnf install -y python3 python3-venv python3-pip git gcc ncurses-devel
            ;;
        alpine)
            log_info "installing_alpine"
            $sudo_cmd apk add --no-cache python3 py3-venv py3-pip git gcc ncurses-dev linux-headers musl-dev
            ;;
        *)
            log_error "unsupported_os" "$distro"
            log_info "missing_gcc"
            exit 1
            ;;
    esac
}

install_dependencies_macos() {
    log_info "installing_macos"

    # Install Homebrew if not installed
    if ! command -v brew &> /dev/null; then
        log_info "installing_homebrew"
        /bin/bash -c "$(curl -fsSL "$HOMEBREW_INSTALL_URL")"
    fi

    # Update Homebrew
    brew update

    # Install dependencies
    brew list python &> /dev/null || brew install python
    brew list git &> /dev/null || brew install git
    brew list ncurses &> /dev/null || brew install ncurses
}

# ============================================================================
# Python Environment Setup
# ============================================================================

check_python() {
    # Check python3
    if ! command -v python3 &> /dev/null; then
        log_error "missing_python"
        return 1
    fi

    # Show Python version first
    local version
    version=$(python3 --version 2>&1)
    version=$(echo "$version" | grep -Eo '[0-9]+\.[0-9]+\.[0-9]+')
    log_info "python_version" "$version"

    # Check python3-venv
    if ! python3 -c "import venv" 2>/dev/null; then
        return 1
    fi

    # Check pip
    if ! python3 -m pip --version &>/dev/null; then
        return 1
    fi

    return 0
}

# ============================================================================
# Banner and Next Steps
# ============================================================================

print_banner() {
    echo ""
    echo "============================================================"
    echo "   $(get_message 'banner_title')   "
    echo "============================================================"
    echo ""
}

# ============================================================================
# Main Function
# ============================================================================

main() {
    set -e  # Exit on error

    # Initialize environment
    init_environment

    # Parse command line arguments
    parse_args "$@"

    # Print help if requested
    if [ "$CONFIG_HELP_MODE" = "true" ]; then
        print_help
        exit 0
    fi

    # Print installation banner
    print_banner

    # Log mirror selection result
    if [ "$CONFIG_USE_CN" = "true" ]; then
        log_info "using_cn_mirror"
    else
        log_info "using_official_source"
    fi

    # Check dependencies (git, python), install if missing
    if ! check_git || ! check_python; then
        install_dependencies_linux
    fi

    # Download and execute touch_env.py
    download_and_run_touch_env
}

# ============================================================================
# Run Main Function
# ============================================================================

main "$@"
