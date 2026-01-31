#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# File      : touch_env.py
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
# 2026-01-30     dongly         Initial version
#
# RT-Thread ENV Setup Script (Python)
# RT-Thread ENV 安装脚本 (Python)
#
# This script handles the setup of RT-Thread ENV after the repository is cloned.
# 此脚本在仓库克隆后处理 RT-Thread ENV 的设置。
# It performs the installation process:
# 执行安装过程：
# 1. Setup repositories (clone packages, sdk, env) - 设置仓库（克隆 packages, sdk, env）
# 2. Create Python virtual environment - 创建 Python 虚拟环境
# 3. Install Python packages - 安装 Python 包
# 4. Restore preserved configuration - 恢复保留的配置
# 5. Show next steps - 显示后续步骤
#
# Usage:
# 用法:
#   python touch_env.py [OPTIONS]
#
# Options:
# 选项:
#   --env-root <path>          Installation root directory (default: ~/.rt-env)
#                              安装 ENV_ROOT（默认：~/.rt-env）
#   --use-cn                   Use China mirror (Gitee, TUNA PyPI)
#                              使用中国镜像（Gitee, TUNA PyPI）
#   --language <lang>          Language: 'en' or 'zh'
#                              语言：'en' 或 'zh'
#   --auto-mode                Auto-install without prompts
#                              自动安装，无提示
#   --backup <strategy>        Backup strategy when ENV exists:
#                              当 ENV 已存在时的备份策略：
#                                preserve: Keep .config and toolchains(local_pkgs), delete others
#                                            保留 .config 和 local_pkgs，删除其他内容
#                                delete_all: Backup then delete everything, no restore
#                                            备份后删除所有内容，不恢复
#                                delete_all_now: Delete everything immediately, no backup
#                                            立即删除所有内容，不备份
#                                backup_all: Keep backup with hardlink restore
#                                            保留备份，用硬链接恢复工具链(local_pkgs)
#   --install-pyocd            Install pyocd for debugging
#                              安装 pyocd 调试工具
#   --restore-config           Restore preserved configuration
#                              恢复保留的配置
#   --repo-env <url>           Custom env repository URL, e.g.:
#                              自定义 env 仓库 URL,例如：
#                                  https://github.com/user/env.git#branch1  <--- branch is optional
#                                  https://github.com/user/env.git          <--- 分支是可选的
#   --repo-packages <url>      Custom packages repository URL
#                              自定义 packages 仓库 URL
#   --repo-sdk <url>           Custom sdk repository URL
#                              自定义 sdk 仓库 URL
#
# Examples:
# 示例:
#   python touch_env.py
#   python touch_env.py --backup preserve
#   python touch_env.py --env-root /path/to/env
#   python touch_env.py --repo-env https://github.com/user/env.git#branch1
#   python touch_env.py --backup delete_all --repo-packages https://github.com/user/packages.git#my-branch
#

import os
import sys
import argparse
import platform
import shutil
import subprocess
import json
from pathlib import Path
from datetime import datetime

# ============================================================================
# Configuration Constants
# ============================================================================

# GitHub official sources
REPO_PACKAGES_GITHUB = "https://github.com/RT-Thread/packages.git"
REPO_ENV_GITHUB = "https://github.com/RT-Thread/env.git"
REPO_SDK_GITHUB = "https://github.com/RT-Thread/sdk.git"

# Gitee mirrors (China)
REPO_PACKAGES_GITEE = "https://gitee.com/RT-Thread-Mirror/packages.git"
REPO_ENV_GITEE = "https://gitee.com/RT-Thread-Mirror/env.git"
REPO_SDK_GITEE = "https://gitee.com/RT-Thread-Mirror/sdk.git"

# PyPI mirror
PYPI_MIRROR_CN = "https://pypi.tuna.tsinghua.edu.cn/simple"

# Internal default values
VENV_DIR_RELATIVE = "venv/rt-env"
SCRIPTS_DIR_RELATIVE = "tools/scripts"
TEMP_CONFIG_FILE = ".config.backup"

# Default installation root directory
DEFAULT_ENV_ROOT = "~/.rt-env"

# Portable Python directory name
PORTABLE_PYTHON_DIR = "python"

# Backup configuration constants
BACKUP_MIN_SPACE_GB = 1  # Minimum space required if size calculation fails (GB)
BACKUP_SAFETY_MARGIN = 1.2  # Safety margin for backup space (20%)

# Platform-specific imports
if platform.system() == 'Windows':
    try:
        import msvcrt
    except ImportError:
        msvcrt = None
else:
    msvcrt = None
    try:
        import tty
        import termios
        HAS_TTY = True
    except ImportError:
        HAS_TTY = False

# ============================================================================
# Python Version Check
# ============================================================================

MIN_PYTHON_VERSION = (3, 6)

if sys.version_info < MIN_PYTHON_VERSION:
    print(
        f"Error: Python {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]} or higher is required.", file=sys.stderr)
    print(f"Current Python version: {sys.version}", file=sys.stderr)
    sys.exit(1)

# ============================================================================
# Runtime Configuration
# ============================================================================

class RuntimeConfig:
    """Runtime configuration management"""
    def __init__(self):
        self._language = 'en'  # Default language

    @property
    def language(self):
        """Get current language"""
        return self._language

    @language.setter
    def language(self, value):
        """Set language"""
        self._language = value

# Global runtime configuration instance
_runtime_config = RuntimeConfig()

def get_language():
    """Get current language"""
    return _runtime_config.language

def set_language(lang):
    """Set language"""
    _runtime_config.language = lang

# ============================================================================
# TouchEnvConfig Class
# ============================================================================


class TouchEnvConfig:
    """Configuration management class for touch_env"""

    def __init__(self, args):
        # Check if using default env-root
        default_env_root = os.path.expanduser(DEFAULT_ENV_ROOT)
        if args.env_root == default_env_root:
            # Temporarily set language for log_info
            set_language(args.language)
            log_info('using_default_env_root', default_env_root)

        # Set language in runtime config
        set_language(args.language)

        self.env_root = args.env_root
        self.use_cn = args.use_cn
        self.language = args.language
        self.auto_mode = args.auto_mode
        self.install_pyocd = args.install_pyocd
        self.restore_config = args.restore_config
        self.custom_repos = args.custom_repos
        self.backup_strategy = args.backup

        # Backup-related attributes
        self.backup_path = None
        self.strategy = None  # 'preserve' or 'delete_all' or 'backup_all' or None

        # Compute internal paths
        self._compute_paths()

        # Validate configuration
        self._validate()

    def _compute_paths(self):
        """Compute internal paths based on env_root"""
        self.venv_dir = os.path.join(self.env_root, VENV_DIR_RELATIVE)
        self.scripts_dir = os.path.join(self.env_root, SCRIPTS_DIR_RELATIVE)
        self.temp_config_path = os.path.join(self.env_root, TEMP_CONFIG_FILE)

    def _validate(self):
        """Validate configuration"""
        # Validate env_root
        if not self.env_root:
            raise ValueError("env_root is required")

        # Validate language
        if self.language not in ['en', 'zh']:
            raise ValueError(
                f"Invalid language: {self.language}. Must be 'en' or 'zh'")

        # custom_repos is built internally in parse_arguments, no need for extensive validation
        # Basic type check is sufficient
        if self.custom_repos and not isinstance(self.custom_repos, dict):
            raise ValueError("custom_repos must be a dictionary")

# ============================================================================
# Internationalization Messages
# ============================================================================


MESSAGES = {
    'en': {
        'info': 'INFO',
        'success': 'SUCCESS',
        'warning': 'WARNING',
        'error': 'ERROR',
        'cloning': 'Cloning {0} to {1}',
        'cloned': 'Cloned {0}',
        'dir_exists': 'Directory already exists: {0}',
        'generating_kconfig': 'Generating Kconfig: {0}',
        'creating_venv': 'Creating virtual environment at: {0}',
        'venv_created': 'Virtual environment created',
        'venv_exists': 'Virtual environment already exists',
        'upgrading_pip': 'Upgrading pip...',
        'installing_packages': 'Installing Python packages...',
        'installed_packages': 'Python packages installed successfully',
        'using_cn_mirror': 'Using China mirror',
        'using_pypi_mirror': 'Using PyPI mirror: {0}',
        'copied_env_script': 'Copied env script: {0}',
        'restoring_config': 'Restoring config...',
        'config_restored': 'Config restored',
        'pyocd_install_prompt': 'Do you want to install pyocd (for debugging Cortex-M devices)?',
        'pyocd_install_confirm': 'Install pyocd? [y/N]: ',
        'installing_pyocd': 'Will install pyocd',
        'skipping_pyocd': 'Skipping pyocd installation',
        'install_pyocd_method': '5. To install pyocd, run after activation: `pip install pyocd`',
        'fixed_guiconfig': 'Fixed guiconfig.py (added missing import)',
        'setup_complete': 'RT-Thread ENV installation completed!',
        'next_steps': 'Next steps:',
        'activate_env': '1. Activate environment:',
        'add_to_profile': '2. Add to profile:',
        'install_toolchain': '3. Install toolchains:',
        'install_toolchain_cmd': '   Run `sdk` command to install required toolchains',
        'after_activation': '4. After activation, you can use:',
        'menuconfig': '     - menuconfig    : Configure project',
        'menuconfig_s': '     - menuconfig -s : Configure RT-Thread ENV',
        'pkgs': '     - pkgs          : Package manager',
        'scons': '     - scons         : Build project',
        'sdk': '     - sdk           : Install toolchains',
        'clone_failed': 'Git clone failed: {0}',
        'invalid_git_repo': 'Invalid git repository: {0}',
        'venv_not_found': 'Virtual environment not found',
        'package_install_failed': 'Package installation failed: {0}',
        'venv_creation_failed': 'Virtual environment creation failed: {0}',
        'fix_guiconfig_failed': 'Failed to fix guiconfig.py: {0}',
        'using_custom_repo': 'Using custom repository: {0}',
        'using_custom_repo_branch': 'Using custom repository: {0} (branch: {1})',
        'backup_config': 'Backing up configuration file...',
        'no_config_to_restore': 'No configuration to restore',
        'env_root_exists': 'Existing RT-Thread ENV detected at: {0}',
        'env_root_exists_prompt': 'Please select how to handle existing directory (ENV_ROOT)',
        'env_root_confirm': 'Are you sure you want to delete? [Y/A/b/D/C/n]: ',
        'env_root_confirm_help': '  Y/y: Preserve config and toolchains(local_pkgs), delete others (default)',
        'env_root_confirm_all': '  A/a: Backup then delete entire directory (including config and toolchains)',
        'env_root_confirm_backup': '  B/b: Backup entire directory and keep',
        'env_root_confirm_delete': '  D/d: Delete entire directory immediately (including config and toolchains)',
        'env_root_confirm_new': '  C/c: Specify new installation directory',
        'env_root_confirm_no': '  N/n: Cancel installation',
        'use_arrow_keys': 'Use ↑/↓ arrows to select, Enter to confirm',
        'press_enter_confirm': 'Or press Y/A/B/D/C/N directly',
        'installation_cancelled': 'Installation cancelled',
        'installation_failed': 'Installation failed: {0}',
        'skipping_item': 'Skipping: {0}',
        'item_deleted': 'Deleted: {0}',
        'file_delete_failed': 'Failed to delete file: {0} - {1}',
        'dir_delete_failed': 'Failed to delete directory: {0} - {1}',
        'deleting_env_root': 'Deleting existing directory: {0}',
        'deleting_env_root_failed': 'Failed to delete directory: {0}',
        'file_copy_failed': 'Failed to copy file: {0} - {1}',
        'dir_hardlink_failed': 'Failed to hardlink directory: {0} - {1}',
        'restoring_local_pkgs_with_hardlink': 'Restoring local_pkgs with hardlinks...',
        'local_pkgs_restored': 'Toolchains restored with hardlinks',
        'backup_creating': 'Creating backup: {0}...',
        'backup_created': 'Backup created: {0}',
        'backup_restore_failed': 'Failed to restore from backup: {0}',
        'backup_kept_for_manual_recovery': 'Backup kept for manual recovery at: {0}',
        'backup_create_failed': 'Failed to create backup: {0}',
        'manual_backup_required': 'Please manually backup and delete directory, then retry',
        'manual_delete_required': 'Please manually delete directory: {0}, then retry',
        'install_failed_options': 'Installation failed. What would you like to do?',
        'option_restore_backup': '  R/r: Restore from backup (roll back to previous state)',
        'option_keep_current': '  K/k: Keep current state (partial installation)',
        'option_delete_backup': '  D/d: Delete backup and exit',
        'install_failed_prompt': 'Your choice [R/k/d]: ',
        'restore_from_backup': 'Restoring from backup: {0}...',
        'backup_restored': 'Backup restored successfully',
        'backup_cleaned': 'Backup cleaned up: {0}',
        'no_space_for_backup': 'Insufficient disk space for backup. Required: {0}, Available: {1}',
        'checking_disk_space': 'Checking disk space...',
        'auto_restoring_backup': 'Automatically restoring backup...',
        'keeping_current_state': 'Keeping current state as is...',
        'start': '[PY]Starting RT-Thread ENV installation...',
        'using_default_env_root': 'Using default ENV_ROOT: {0}',
        'env_root_prompt': 'Enter installation root directory (ENV_ROOT)',
        'env_root_default': '[default: {0}]',
        'python_path_invalid': 'Path contains {0} (not allowed in Python paths)',
        'python_path_creating_dir': 'Creating directory: {0}',
        'python_path_no_permission': 'No write permission for directory: {0}',
    },
    'zh': {
        'info': '信息',
        'success': '成功',
        'warning': '警告',
        'error': '错误',
        'cloning': '正在克隆: {0} 到 {1}',
        'cloned': '已克隆: {0}',
        'dir_exists': '目录已存在: {0}',
        'generating_kconfig': '生成 Kconfig: {0}',
        'creating_venv': '正在创建虚拟环境: {0}',
        'venv_created': '虚拟环境创建完成',
        'venv_exists': '虚拟环境已存在',
        'upgrading_pip': '正在升级 pip...',
        'installing_packages': '正在安装 Python 包...',
        'installed_packages': 'Python 包安装完成',
        'using_cn_mirror': '使用中国镜像源',
        'using_pypi_mirror': '使用 PyPI 镜像: {0}',
        'copied_env_script': '已复制 env 脚本: {0}',
        'restoring_config': '正在恢复配置...',
        'config_restored': '配置已恢复',
        'pyocd_install_prompt': '是否要安装 pyocd (用于调试 Cortex-M 设备)？',
        'pyocd_install_confirm': '安装 pyocd？[y/N]: ',
        'installing_pyocd': '将要安装 pyocd',
        'skipping_pyocd': '跳过 pyocd 安装',
        'install_pyocd_method': '5. 如需安装 pyocd，激活后运行: `pip install pyocd`',
        'fixed_guiconfig': '已修复 guiconfig.py（添加缺失的导入）',
        'setup_complete': 'RT-Thread ENV 安装完成！',
        'next_steps': '后续步骤:',
        'activate_env': '1. 激活环境:',
        'add_to_profile': '2. 添加到配置文件:',
        'install_toolchain': '3. 安装工具链:',
        'install_toolchain_cmd': '   运行 `sdk` 命令安装所需的工具链',
        'after_activation': '4. 激活后可用命令:',
        'menuconfig': '     - menuconfig    : 配置项目',
        'menuconfig_s': '     - menuconfig -s : 配置 RT-Thread ENV',
        'pkgs': '     - pkgs          : 包管理器',
        'scons': '     - scons         : 编译项目',
        'sdk': '     - sdk           : 安装工具链',
        'clone_failed': 'Git 克隆失败: {0}',
        'invalid_git_repo': '无效的 git 仓库: {0}',
        'venv_not_found': '找不到虚拟环境',
        'package_install_failed': '包安装失败: {0}',
        'venv_creation_failed': '虚拟环境创建失败: {0}',
        'fix_guiconfig_failed': '修复 guiconfig.py 失败: {0}',
        'using_custom_repo': '使用自定义仓库: {0}',
        'using_custom_repo_branch': '使用自定义仓库: {0} (分支: {1})',
        'backup_config': '正在备份配置文件...',
        'no_config_to_restore': '没有需要恢复的配置',
        'env_root_exists': '检测到已存在的 RT-Thread ENV: {0}',
        'env_root_exists_prompt': '检测到已存在的RT-Thread ENV。是否要删除并重新安装？',
        'env_root_confirm': '确定要删除吗？[Y/A/b/D/C/n]: ',
        'env_root_confirm_help': '  Y/y: 保留配置和工具链(local_pkgs)，删除其他（默认）',
        'env_root_confirm_all': '  A/a: 备份后删除整个目录（包括配置和工具链）',
        'env_root_confirm_backup': '  B/b: 备份整个目录并保留',
        'env_root_confirm_delete': '  D/d: 立即删除整个目录（包括配置和工具链）',
        'env_root_confirm_new': '  C/c: 指定新的安装目录',
        'env_root_confirm_no': '  N/n: 取消安装',
        'use_arrow_keys': '使用 ↑/↓ 方向键选择，回车确认',
        'press_enter_confirm': '或直接按 Y/A/B/D/C/N 键',
        'installation_cancelled': '安装已取消',
        'installation_failed': '安装失败: {0}',
        'skipping_item': '跳过: {0}',
        'item_deleted': '已删除: {0}',
        'file_delete_failed': '删除文件失败: {0} - {1}',
        'dir_delete_failed': '删除目录失败: {0} - {1}',
        'deleting_env_root': '正在删除现有目录: {0}',
        'deleting_env_root_failed': '删除目录失败: {0}',
        'file_copy_failed': '复制文件失败: {0} - {1}',
        'dir_hardlink_failed': '硬链接目录失败: {0} - {1}',
        'restoring_local_pkgs_with_hardlink': '正在使用硬链接恢复工具链...',
        'local_pkgs_restored': '工具链已使用硬链接恢复',
        'backup_creating': '正在创建备份: {0}...',
        'backup_created': '备份已创建: {0}',
        'backup_restore_failed': '从备份恢复失败: {0}',
        'backup_kept_for_manual_recovery': '备份已保留，可供手动恢复，位置: {0}',
        'backup_create_failed': '创建备份失败: {0}',
        'manual_backup_required': '请手动备份并删除目录后重试',
        'manual_delete_required': '请手动删除目录: {0}，然后重试',
        'install_failed_options': '安装失败。您想要怎么做？',
        'option_restore_backup': '  R/r: 从备份恢复（回滚到之前的状态）',
        'option_keep_current': '  K/k: 保留当前状态（部分安装）',
        'option_delete_backup': '  D/d: 删除备份并退出',
        'install_failed_prompt': '您的选择 [R/k/d]: ',
        'restore_from_backup': '正在从备份恢复: {0}...',
        'backup_restored': '备份恢复成功',
        'backup_cleaned': '备份已清理: {0}',
        'no_space_for_backup': '磁盘空间不足以创建备份。需要: {0}, 可用: {1}',
        'checking_disk_space': '正在检查磁盘空间...',
        'auto_restoring_backup': '自动恢复备份中...',
        'keeping_current_state': '保持当前状态不变...',
        'start': '[PY]开始 RT-Thread ENV 安装...',
        'using_default_env_root': '使用默认 ENV_ROOT: {0}',
        'env_root_prompt': '请选择怎样处理现存目录(ENV_ROOT)',
        'env_root_default': '[默认: {0}]',
        'python_path_invalid': '路径包含 {0}（Python 路径中不允许）',
        'python_path_creating_dir': '正在创建目录: {0}',
        'python_path_no_permission': '没有目录的写入权限: {0}',
    }
        }

# ============================================================================
# Global Variables
# ============================================================================

# ============================================================================
# Message Functions
# ============================================================================


def get_message(key):
    """Get localized message using current language"""
    lang = get_language()
    return MESSAGES.get(lang, {}).get(key, key)


def log_info(key, *args):
    """Log info message to stdout"""
    msg = get_message(key)
    if args:
        msg = msg.format(*args)
    print(f"\033[0;36m[{get_message('info')}]\033[0m {msg}")


def log_success(key, *args):
    """Log success message to stdout"""
    msg = get_message(key)
    if args:
        msg = msg.format(*args)
    print(f"\033[0;32m[{get_message('success')}]\033[0m {msg}")


def log_error(key, *args):
    """Log error message to stderr"""
    msg = get_message(key)
    if args:
        msg = msg.format(*args)
    print(f"\033[0;31m[{get_message('error')}]\033[0m {msg}", file=sys.stderr)


def log_warning(key, *args):
    """Log warning message to stderr"""
    msg = get_message(key)
    if args:
        msg = msg.format(*args)
    print(f"\033[0;33m[{get_message('warning')}]\033[0m {msg}", file=sys.stderr)


def log_raw(key, *args, **kwargs):
    """Log raw message using current language"""
    msg = get_message(key)
    if args:
        msg = msg.format(*args)
    print(msg, **kwargs)

# ============================================================================
# Repository Functions
# ============================================================================


def clone_repository(config, repo_name, url, dest_rel, branch='', depth=1):
    """
    Clone Git repository with cleanup on failure

    Args:
        config: TouchEnvConfig instance
        repo_name: Repository name ('packages', 'sdk', or 'env')
        url: Repository URL
        dest_rel: Destination path relative to env_root
        branch: Optional branch name
        depth: Clone depth (default 1 for shallow clone)

    Raises:
        RuntimeError: If clone fails
    """
    dest_path = os.path.join(config.env_root, dest_rel)

    # If directory exists, verify it's a valid git repository
    if os.path.exists(dest_path):
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--git-dir'],
                cwd=dest_path,
                capture_output=True,
                text=True,
                check=True
            )
            log_success('dir_exists', dest_path)
            return
        except subprocess.CalledProcessError:
            # Invalid git repository, need to clean up
            log_error('invalid_git_repo', dest_path)
            shutil.rmtree(dest_path, ignore_errors=True)

    # Clone repository
    log_info('cloning', url, dest_path)

    clone_args = ['git', 'clone', '--depth', str(depth)]
    if branch:
        clone_args.extend(['--branch', branch])
    clone_args.extend([url, dest_path])

    try:
        # Run without capture to show verbose git output
        subprocess.run(clone_args, check=True)
        log_success('cloned', dest_path)
    except subprocess.CalledProcessError as e:
        # Clone failed, clean up partial clone
        log_error('clone_failed', str(e))
        shutil.rmtree(dest_path, ignore_errors=True)
        raise RuntimeError(f"Failed to clone {url}") from e


def setup_repositories(config):
    """
    Setup all repositories (packages, sdk, env)

    Args:
        config: TouchEnvConfig instance

    Raises:
        RuntimeError: If any repository setup fails
    """
    # Base repositories
    github_repos = {
        'packages': REPO_PACKAGES_GITHUB,
        'env': REPO_ENV_GITHUB,
        'sdk': REPO_SDK_GITHUB
    }

    gitee_repos = {
        'packages': REPO_PACKAGES_GITEE,
        'env': REPO_ENV_GITEE,
        'sdk': REPO_SDK_GITEE
    }

    # Select mirror
    repos_base = gitee_repos if config.use_cn else github_repos

    # Repository destinations
    repo_dests = {
        'packages': 'packages/packages',
        'env': 'tools/scripts',
        'sdk': 'packages/sdk'
    }

    # Clone all repositories
    for repo_name in ['packages', 'env', 'sdk']:
        # Check for custom repository
        if config.custom_repos and repo_name in config.custom_repos:
            repo_info = config.custom_repos[repo_name]
            url = repo_info['url']
            branch = repo_info.get('branch', '')

            if branch:
                log_info('using_custom_repo_branch', url, branch)
            else:
                log_info('using_custom_repo', url)
        else:
            url = repos_base[repo_name]
            branch = ''

        clone_repository(config, repo_name, url, repo_dests[repo_name], branch)

    # Generate Kconfig file
    generate_kconfig_file(config)

    # Copy env scripts
    copy_env_scripts(config)


def generate_kconfig_file(config):
    """Generate Kconfig configuration file"""
    packages_dir = os.path.join(config.env_root, 'packages')
    os.makedirs(packages_dir, exist_ok=True)

    kconfig_path = os.path.join(packages_dir, 'Kconfig')
    kconfig_content = 'source "$PKGS_DIR/packages/Kconfig"\n'

    with open(kconfig_path, 'w', encoding='utf-8') as f:
        f.write(kconfig_content)

    log_success('generating_kconfig', kconfig_path)

    # Create local_pkgs directory
    local_pkgs_dir = os.path.join(config.env_root, 'local_pkgs')
    os.makedirs(local_pkgs_dir, exist_ok=True)


def copy_env_scripts(config):
    """Copy env scripts to root directory"""
    scripts_dir = os.path.join(config.env_root, 'tools/scripts')

    # Copy appropriate script based on platform
    if platform.system() == 'Windows':
        src = os.path.join(scripts_dir, 'env.ps1')
        dst = os.path.join(config.env_root, 'env.ps1')
    else:
        src = os.path.join(scripts_dir, 'env.sh')
        dst = os.path.join(config.env_root, 'env.sh')

    if os.path.exists(src):
        shutil.copy2(src, dst)
        log_success('copied_env_script', dst)

# ============================================================================
# Virtual Environment Functions
# ============================================================================


def create_venv(config):
    """
    Create Python virtual environment

    Args:
        config: TouchEnvConfig instance

    Raises:
        RuntimeError: If venv creation fails
    """
    venv_path = config.venv_dir

    if os.path.exists(venv_path):
        log_success('venv_exists')
        return

    log_info('creating_venv', venv_path)

    try:
        import venv
        venv.create(venv_path, with_pip=True)
        log_success('venv_created')
    except (OSError, PermissionError, ValueError) as e:
        log_error('venv_creation_failed', str(e))
        raise RuntimeError(f"Failed to create virtual environment: {e}") from e


def get_python_executable(config):
    """
    Get virtual environment Python executable path

    Args:
        config: TouchEnvConfig instance

    Returns:
        Path to Python executable
    """
    if platform.system() == 'Windows':
        return os.path.join(config.venv_dir, 'Scripts', 'python.exe')
    else:
        return os.path.join(config.venv_dir, 'bin', 'python')

# ============================================================================
# Package Installation Functions
# ============================================================================


def install_packages(config):
    """
    Install Python packages

    Args:
        config: TouchEnvConfig instance

    Raises:
        RuntimeError: If package installation fails
    """
    python_exe = get_python_executable(config)

    if not os.path.exists(python_exe):
        log_error('venv_not_found')
        raise RuntimeError("Virtual environment not found")

    # Upgrade pip
    log_info('upgrading_pip')
    subprocess.run(
        [python_exe, '-m', 'pip', 'install', '--upgrade', 'pip'],
        check=True
    )

    # Build pip install arguments
    pip_args = [python_exe, '-m', 'pip', 'install']

    # Add mirror source
    if config.use_cn:
        log_info('using_cn_mirror')
        log_info('using_pypi_mirror', PYPI_MIRROR_CN)
        pip_args.extend(['--index-url', PYPI_MIRROR_CN])

    # Install rt-env package (editable mode)
    pip_args.extend(['-e', config.scripts_dir])

    # Optionally install pyocd
    if config.install_pyocd:
        pip_args.append('pyocd')

    # Execute installation
    log_info('installing_packages')
    try:
        subprocess.run(pip_args, check=True)
        log_success('installed_packages')
    except subprocess.CalledProcessError as e:
        log_error('package_install_failed', str(e))
        raise RuntimeError(f"Package installation failed: {e}") from e

    # Fix guiconfig.py missing import re issue
    fix_guiconfig_import(config)


def fix_guiconfig_import(config):
    """
    Fix guiconfig.py missing import re issue

    Args:
        config: TouchEnvConfig instance
    """
    # Direct path for Windows and Unix-like systems
    if platform.system() == 'Windows':
        guiconfig_path = os.path.join(
            config.venv_dir, 'Lib', 'site-packages', 'guiconfig.py')
    else:
        guiconfig_path = os.path.join(
            config.venv_dir, 'lib', f'python{sys.version_info.major}.{sys.version_info.minor}', 'site-packages', 'guiconfig.py')

    if not os.path.exists(guiconfig_path):
        return

    try:
        with open(guiconfig_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check if import re already exists
        if 'import re' not in content:
            # Insert import re at the appropriate location
            lines = content.split('\n')

            # Find the first non-comment, non-docstring line
            # Skip shebang, encoding, and docstring
            import_index = 0
            in_docstring = False
            docstring_delimiter = None

            for i, line in enumerate(lines):
                stripped = line.strip()

                # Skip empty lines and comments
                if not stripped or stripped.startswith('#'):
                    continue

                # Handle docstring
                if (stripped.startswith('"""') or stripped.startswith("'''")):
                    if in_docstring:
                        if stripped.startswith(docstring_delimiter) and len(stripped) > 3:
                            in_docstring = False
                    else:
                        in_docstring = True
                        docstring_delimiter = stripped[:3]
                    continue

                if in_docstring:
                    continue

                # Found first actual code line
                # Look for the first import or from statement
                if line.startswith('import ') or line.startswith('from '):
                    import_index = i + 1
                else:
                    import_index = i
                break

            # Insert import re at the calculated position
            lines.insert(import_index, 'import re')
            content = '\n'.join(lines)

            with open(guiconfig_path, 'w', encoding='utf-8') as f:
                f.write(content)

            log_success('fixed_guiconfig')
    except (IOError, PermissionError, UnicodeDecodeError, UnicodeEncodeError) as e:
        # Fix failure should not interrupt installation
        log_error('fix_guiconfig_failed', str(e))

# ============================================================================
# Configuration Backup/Restore Functions
# ============================================================================


def backup_config_file(config):
    """
    Backup configuration file

    Args:
        config: TouchEnvConfig instance
    """
    config_path = os.path.join(
        config.env_root, 'tools', 'scripts', 'cmds', '.config')

    if os.path.exists(config_path):
        log_info('backup_config')
        shutil.copy2(config_path, config.temp_config_path)


def restore_config(config):
    """
    Restore configuration file

    Args:
        config: TouchEnvConfig instance
    """
    if config.restore_config and os.path.exists(config.temp_config_path):
        config_path = os.path.join(
            config.env_root, 'tools', 'scripts', 'cmds', '.config')

        log_info('restoring_config')
        shutil.copy2(config.temp_config_path, config_path)
        os.remove(config.temp_config_path)
        log_success('config_restored')
    else:
        log_info('no_config_to_restore')

# ============================================================================
# Check Existing ENV Functions
# ============================================================================


def check_existing_env(config):
    """
    Check if existing ENV exists and handle backup

    Args:
        config: TouchEnvConfig instance

    Raises:
        SystemExit: If user cancels installation
    """
    if not os.path.exists(config.env_root):
        return

    log_raw(get_message('env_root_exists').format(config.env_root))
    print()

    # Check if backup strategy is specified via command line
    if config.backup_strategy:
        # Use specified strategy directly, skip interactive menu
        config.strategy = config.backup_strategy
        try:
            config.backup_path = create_backup_directory(config)
        except (OSError, RuntimeError) as e:
            log_error('backup_create_failed', str(e))
            log_warning('manual_backup_required')
            sys.exit(1)
    elif config.auto_mode:
        # Auto mode: use specified strategy or default to 'preserve'
        if config.backup_strategy:
            config.strategy = config.backup_strategy
        else:
            config.strategy = 'preserve'
        try:
            config.backup_path = create_backup_directory(config)
        except (OSError, RuntimeError) as e:
            log_error('backup_create_failed', str(e))
            sys.exit(1)
    else:
        # Interactive mode: ask user
        response = show_deletion_options(config)

        if response.lower() == 'y':
            # Preserve config and local_pkgs
            config.strategy = 'preserve'
            try:
                config.backup_path = create_backup_directory(config)
            except (OSError, RuntimeError) as e:
                log_error('backup_create_failed', str(e))
                log_warning('manual_backup_required')
                sys.exit(1)
        elif response.lower() == 'a':
            # Backup then delete everything
            config.strategy = 'delete_all'
            try:
                config.backup_path = create_backup_directory(config)
            except (OSError, RuntimeError) as e:
                log_error('backup_create_failed', str(e))
                log_warning('manual_backup_required')
                sys.exit(1)
        elif response.lower() == 'b':
            # Backup entire directory, then delete everything
            config.strategy = 'backup_all'
            try:
                config.backup_path = create_backup_directory(config)
            except (OSError, RuntimeError) as e:
                log_error('backup_create_failed', str(e))
                log_warning('manual_backup_required')
                sys.exit(1)
        elif response.lower() == 'd':
            # Delete everything immediately without backup
            config.strategy = 'delete_all_now'
            config.backup_path = None
            # Immediately delete the directory
            if os.path.exists(config.env_root):
                log_info('deleting_env_root', config.env_root)
                try:
                    _safe_remove_tree(config.env_root)
                except (OSError, PermissionError) as e:
                    log_error('deleting_env_root_failed', str(e))
                    log_warning('manual_delete_required', config.env_root)
                    sys.exit(1)
        elif response.lower() == 'c':
            # Specify new installation directory
            default_env_root = os.path.expanduser(DEFAULT_ENV_ROOT)
            config.env_root = prompt_env_root(default_env_root, config.language)
            config._compute_paths()
            # Re-check existing ENV with new path
            check_existing_env(config)  # 递归调用以检查新路径
            return  # 退出当前函数
        else:
            # Cancel installation
            log_info('installation_cancelled')
            sys.exit(0)


def show_deletion_options(config):
    """
    Show deletion options to user with interactive menu selection

    Args:
        config: TouchEnvConfig instance

    Returns:
        str: User response (y/a/b/n)
    """
    # Define options
    options = [
        {'key': 'Y', 'desc': get_message('env_root_confirm_help'), 'default': True},
        {'key': 'A', 'desc': get_message('env_root_confirm_all'), 'default': False},
        {'key': 'B', 'desc': get_message('env_root_confirm_backup'), 'default': False},
        {'key': 'D', 'desc': get_message('env_root_confirm_delete'), 'default': False},
        {'key': 'C', 'desc': get_message('env_root_confirm_new'), 'default': False},
        {'key': 'N', 'desc': get_message('env_root_confirm_no'), 'default': False},
    ]

    # Try interactive menu if msvcrt (Windows) or tty (Linux) is available
    if msvcrt is not None or HAS_TTY:
        try:
            return _interactive_menu(options)
        except Exception:
            # Fall back to simple input if interactive menu fails
            pass

    # Fallback to simple input
    log_raw('env_root_confirm', end='', flush=True)
    print()
    for opt in options:
        print(opt['desc'])
    print('> ', end='', flush=True)

    try:
        response = input().strip().lower()
        if not response:
            return 'y'  # Default is y (preserve)
        return response
    except KeyboardInterrupt:
        print()
        log_info('installation_cancelled')
        sys.exit(0)


def _get_key_linux():
    """Get single key press on Linux"""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        key = sys.stdin.read(1)
        if key == '\x1b':  # Escape sequence
            key += sys.stdin.read(2)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return key


def _interactive_menu(options):
    """
    Interactive menu with arrow key navigation

    Args:
        options: List of option dictionaries with 'key', 'desc', 'default'

    Returns:
        str: Selected option key (lowercase)
    """
    selected_index = 0

    # Find default option
    for i, opt in enumerate(options):
        if opt.get('default', False):
            selected_index = i
            break

    # Calculate lines to clear (prompt + blank + options + blank + 2 help lines = 5 + len(options))
    lines_to_clear = 5 + len(options)
    first_run = True

    while True:
        if first_run:
            # First run: print empty lines to overwrite previous output
            print('\n' * lines_to_clear, end='')
            # Move cursor up to the beginning of menu area
            print(f'\033[{lines_to_clear}A', end='')
        else:
            # Clear only the menu area
            print(f'\033[{lines_to_clear}M\033[{lines_to_clear}A', end='')
        first_run = False

        log_raw('env_root_exists_prompt')
        print()

        for i, opt in enumerate(options):
            if i == selected_index:
                # Highlight selected option
                print(f"\033[7m > {opt['desc']}\033[0m")
            else:
                print(f"   {opt['desc']}")

        print()
        log_raw('use_arrow_keys')
        log_raw('press_enter_confirm')

        # Read key - Windows (msvcrt)
        if msvcrt:
            key = msvcrt.getch()
            if key == b'\xe0':  # Special key prefix
                key = msvcrt.getch()
                if key == b'H':  # Up arrow
                    selected_index = (selected_index - 1) % len(options)
                elif key == b'P':  # Down arrow
                    selected_index = (selected_index + 1) % len(options)
            elif key == b'\r' or key == b'\n':  # Enter key
                return options[selected_index]['key'].lower()
            elif key == b'\x03':  # Ctrl+C
                print()
                log_info('installation_cancelled')
                sys.exit(0)
            elif key in [b'y', b'Y', b'a', b'A', b'b', b'B', b'c', b'C', b'n', b'N']:
                # Direct key press
                return key.decode('ascii').lower()
        # Read key - Linux
        elif HAS_TTY:
            key = _get_key_linux()
            if key == '\x1b[A':  # Up arrow
                selected_index = (selected_index - 1) % len(options)
            elif key == '\x1b[B':  # Down arrow
                selected_index = (selected_index + 1) % len(options)
            elif key == '\r' or key == '\n':  # Enter key
                return options[selected_index]['key'].lower()
            elif key == '\x03':  # Ctrl+C
                print()
                log_info('installation_cancelled')
                sys.exit(0)
            elif key.lower() in ['y', 'a', 'b', 'c', 'n']:
                # Direct key press
                return key.lower()


def get_backup_timestamp():
    """
    Generate timestamp for backup directory naming

    Returns:
        str: Timestamp in format YYYYMMDD_HHMMSS
    """
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def create_backup_directory(config):
    """
    Create backup directory with timestamp

    Args:
        config: TouchEnvConfig instance with env_root path

    Returns:
        str: Path to the backup directory

    Raises:
        OSError: If backup creation fails
        RuntimeError: If insufficient disk space
    """
    log_info('checking_disk_space')

    # Get backup directory size estimate (optimized for large directories)
    env_size = 0
    try:
        for dirpath, _, filenames in os.walk(config.env_root):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    env_size += os.path.getsize(filepath)
                except (OSError, PermissionError):
                    # Skip files we can't access
                    continue
    except OSError as e:
        log_error('backup_create_failed', f'Failed to calculate size: {e}')
        # Continue anyway, as size estimate is just a safety check
        env_size = 0

    # Check disk space
    disk_usage = shutil.disk_usage(os.path.dirname(config.env_root))
    available_space = disk_usage.free

    # If we couldn't calculate size, require minimum 1GB
    if env_size == 0:
        required_space = 1024 * 1024 * 1024  # 1GB
    else:
        # Require 20% extra space as safety margin
        required_space = int(env_size * 1.2)

    if available_space < required_space:
        log_error('no_space_for_backup',
                 f'{required_space // (1024*1024)} MB',
                 f'{available_space // (1024*1024)} MB')
        raise RuntimeError(f'Insufficient disk space for backup')

    # Generate backup path
    timestamp = get_backup_timestamp()
    backup_name = f"{os.path.basename(config.env_root)}.backup.{timestamp}"
    backup_path = os.path.join(os.path.dirname(config.env_root), backup_name)

    # Check if backup already exists
    if os.path.exists(backup_path):
        log_error('backup_create_failed', f'Backup directory already exists: {backup_path}')
        raise RuntimeError(f'Backup directory already exists: {backup_path}')

    # Create backup by renaming
    log_info('backup_creating', backup_path)

    try:
        shutil.move(config.env_root, backup_path)
        log_success('backup_created', backup_path)
    except (OSError, PermissionError) as e:
        log_error('backup_create_failed', str(e))
        raise

    return backup_path


def restore_backup(config, backup_path, preserve_items=True):
    """
    Restore items from backup directory

    Args:
        config: TouchEnvConfig instance with env_root path
        backup_path: Path to backup directory
        preserve_items: If True, restore preserved items (.config, local_pkgs)
                       If False, delete backup without restoring

    Returns:
        bool: True if operation succeeded, False otherwise
    """
    failed_items = []

    if not preserve_items:
        # Strategy A: Delete backup without restoring
        log_info('backup_cleaned', backup_path)
        _safe_remove_tree(backup_path)
        return True

    # Strategy Y: Restore preserved items
    # Check if env_root exists
    if not os.path.exists(config.env_root):
        log_error('backup_restore_failed', f'env_root does not exist: {config.env_root}')
        return False

    # 1. Restore .config with hardlink
    config_src = os.path.join(backup_path, 'tools', 'scripts', 'cmds', '.config')
    config_dst = os.path.join(config.env_root, 'tools', 'scripts', 'cmds', '.config')

    if os.path.exists(config_src):
        log_info('restoring_config')
        try:
            os.makedirs(os.path.dirname(config_dst), exist_ok=True)
            # Use hardlink for config file
            if os.path.exists(config_dst):
                os.remove(config_dst)
            os.link(config_src, config_dst)
            log_success('config_restored')
        except OSError:
            # Fallback to copy if hardlink fails (e.g., cross-device)
            shutil.copy2(config_src, config_dst)
            log_success('config_restored')
    else:
        log_info('skipping_item', '.config')

    # 2. Restore local_pkgs with hardlinks
    local_pkgs_src = os.path.join(backup_path, 'local_pkgs')
    local_pkgs_dst = os.path.join(config.env_root, 'local_pkgs')

    if os.path.exists(local_pkgs_src):
        log_info('restore_from_backup', 'local_pkgs')
        try:
            # Remove existing local_pkgs if any
            if os.path.exists(local_pkgs_dst):
                _safe_remove_tree(local_pkgs_dst)

            os.makedirs(local_pkgs_dst, exist_ok=True)

            # Create hardlinks for all files in local_pkgs
            _hardlink_directory(local_pkgs_src, local_pkgs_dst)
            log_success('backup_restored', 'local_pkgs')
        except (OSError, PermissionError) as e:
            log_error('backup_restore_failed', f'local_pkgs: {e}')
            failed_items.append('local_pkgs')
    else:
        log_info('skipping_item', 'local_pkgs')

    # 3. Delete backup directory
    log_info('backup_cleaned', backup_path)
    _safe_remove_tree(backup_path)

    # Report result
    if failed_items:
        log_warning('backup_restore_failed', ', '.join(failed_items))
        return False

    return True


def cleanup_backup_directory(backup_path):
    """
    Safely delete backup directory

    Args:
        backup_path: Path to backup directory
    """
    if os.path.exists(backup_path):
        log_info('backup_cleaned', backup_path)
        _safe_remove_tree(backup_path)


def restore_with_hardlink(config, backup_path):
    """
    Restore config and local_pkgs using hardlink for backup_all strategy

    This function:
    - Copies .config file
    - Creates hardlinks for local_pkgs
    - Keeps backup directory

    Args:
        config: TouchEnvConfig instance with env_root path
        backup_path: Path to backup directory

    Returns:
        bool: True if operation succeeded, False otherwise
    """
    if not os.path.exists(config.env_root):
        log_error('backup_restore_failed', f'env_root does not exist: {config.env_root}')
        return False

    if not os.path.exists(backup_path):
        log_warning('no_config_to_restore')
        return False

    # 1. Copy .config file
    config_src = os.path.join(backup_path, 'tools', 'scripts', 'cmds', '.config')
    config_dst = os.path.join(config.env_root, 'tools', 'scripts', 'cmds', '.config')

    if os.path.exists(config_src):
        log_info('restoring_config')
        try:
            os.makedirs(os.path.dirname(config_dst), exist_ok=True)
            shutil.copy2(config_src, config_dst)
            log_success('config_restored')
        except (OSError, PermissionError) as e:
            log_error('file_copy_failed', '.config', str(e))
    else:
        log_info('skipping_item', '.config')

    # 2. Hardlink local_pkgs
    local_pkgs_src = os.path.join(backup_path, 'local_pkgs')
    local_pkgs_dst = os.path.join(config.env_root, 'local_pkgs')

    if os.path.exists(local_pkgs_src):
        log_info('restoring_local_pkgs_with_hardlink')
        try:
            # Remove existing local_pkgs if any
            if os.path.exists(local_pkgs_dst):
                shutil.rmtree(local_pkgs_dst, ignore_errors=True)

            os.makedirs(local_pkgs_dst, exist_ok=True)

            # Create hardlinks for all files in local_pkgs
            _hardlink_directory(local_pkgs_src, local_pkgs_dst)
            log_success('local_pkgs_restored')
        except (OSError, PermissionError) as e:
            log_error('dir_hardlink_failed', 'local_pkgs', str(e))
            return False
    else:
        log_info('skipping_item', 'local_pkgs')

    log_info('backup_kept_for_manual_recovery', backup_path)
    return True


def _hardlink_directory(src_dir, dst_dir):
    """
    Recursively create hardlinks from src_dir to dst_dir

    Args:
        src_dir: Source directory path
        dst_dir: Destination directory path

    Raises:
        OSError: If hardlink creation fails
    """
    if not os.path.exists(src_dir):
        return

    for item in os.listdir(src_dir):
        src_path = os.path.join(src_dir, item)
        dst_path = os.path.join(dst_dir, item)

        if os.path.isdir(src_path):
            os.makedirs(dst_path, exist_ok=True)
            _hardlink_directory(src_path, dst_path)
        elif os.path.isfile(src_path):
            try:
                # Remove destination if it exists
                if os.path.exists(dst_path):
                    os.remove(dst_path)
                # Create hardlink
                os.link(src_path, dst_path)
            except OSError as e:
                # Fallback to copy if hardlink fails (e.g., cross-device)
                shutil.copy2(src_path, dst_path)


def handle_installation_failure(config, backup_path, strategy):
    """
    Handle installation failure by offering recovery options

    Args:
        config: TouchEnvConfig instance
        backup_path: Path to backup directory
        strategy: User's original strategy ('preserve' or 'delete_all' or 'backup_all')

    Returns:
        int: Exit code (0 for continue, 1 for exit)
    """
    # In auto mode, automatically restore backup if it exists
    if config.auto_mode:
        if backup_path and os.path.exists(backup_path):
            log_info('auto_restoring_backup')
            restore_backup(config, backup_path, preserve_items=True)
        return 1

    # Interactive mode: ask user what to do
    print()
    log_raw('install_failed_options')
    print()
    log_raw('option_restore_backup')
    log_raw('option_keep_current')
    log_raw('option_delete_backup')
    print()

    response = input(get_message('install_failed_prompt'))

    if not response:
        response = 'k'  # Default: keep current

    response = response.lower()

    if response == 'r':
        # Restore from backup
        if backup_path and os.path.exists(backup_path):
            log_info('restore_from_backup', backup_path)
            success = restore_backup(config, backup_path, preserve_items=True)
            if success:
                log_success('backup_restored')
            else:
                log_warning('backup_restore_failed')
        else:
            log_info('no_config_to_restore')
        return 1
    elif response == 'd':
        # Delete backup only
        if backup_path and os.path.exists(backup_path):
            cleanup_backup_directory(backup_path)
        log_info('installation_cancelled')
        return 1
    else:
        # Keep current state (default)
        log_info('keeping_current_state')
        if backup_path and os.path.exists(backup_path):
            log_warning('backup_kept_for_manual_recovery', backup_path)
        return 1


def _safe_remove(path, name):
    """
    Safely remove a file or directory with error handling

    Args:
        path: Full path to the file or directory
        name: Name of the item (for logging)

    Returns:
        bool: True if removal succeeded, False otherwise
    """
    try:
        if os.path.isfile(path) or os.path.islink(path):
            os.remove(path)
        elif os.path.isdir(path):
            shutil.rmtree(path)
        log_info('item_deleted', name)
        return True
    except (OSError, PermissionError) as e:
        if os.path.isfile(path) or os.path.islink(path):
            log_error('file_delete_failed', name, str(e))
        else:
            log_error('dir_delete_failed', name, str(e))
        return False


def _safe_remove_tree(path):
    """
    Safely remove a directory tree, trying multiple methods

    Args:
        path: Path to directory to remove
    """
    if not os.path.exists(path):
        return

    # Method 1: Try rmtree with ignore_errors first
    shutil.rmtree(path, ignore_errors=True)

    # Method 2: If still exists, retry with onerror handler
    if os.path.exists(path):
        def onerror(func, path, exc_info):
            # Try to change permissions and retry
            try:
                os.chmod(path, 0o700)
                if os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
                else:
                    os.remove(path)
            except Exception:
                pass  # Ignore if still fails

        shutil.rmtree(path, onerror=onerror)

    # Method 3: If still exists, list and delete individually
    if os.path.exists(path):
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            try:
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.chmod(item_path, 0o700)
                    os.remove(item_path)
                elif os.path.isdir(item_path):
                    _safe_remove_tree(item_path)
            except Exception:
                pass  # Ignore if fails

        # Finally try to remove the directory itself
        try:
            os.rmdir(path)
        except Exception:
            pass  # Ignore if fails


# ============================================================================
# User Interaction Functions
# ============================================================================


def prompt_pyocd(config):
    """
    Prompt user for pyocd installation

    Args:
        config: TouchEnvConfig instance

    Returns:
        bool: Whether to install pyocd
    """
    # Skip in auto mode
    if config.auto_mode:
        return False

    # Only prompt on Windows and macOS
    if platform.system() not in ['Windows', 'Darwin']:
        return False

    print()
    log_raw('pyocd_install_prompt')
    response = input(get_message('pyocd_install_confirm'))

    install_pyocd = response.lower() == 'y'
    if install_pyocd:
        log_info('installing_pyocd')
    else:
        log_info('skipping_pyocd')

    return install_pyocd


def show_next_steps(config):
    """
    Show installation completion and next steps

    Args:
        config: TouchEnvConfig instance
    """
    print()
    print("=" * 60)
    log_success('setup_complete')
    print("=" * 60)
    print()
    log_info('next_steps')
    print()

    # Activate environment
    log_raw('activate_env')
    if platform.system() == 'Windows':
        print(f"   . {config.env_root}\\env.ps1")
    else:
        print(f"   source {config.env_root}/env.sh")
    print()

    # Add to profile
    log_raw('add_to_profile')
    if platform.system() == 'Windows':
        print(f"   echo '. {config.env_root}\\env.ps1' >> $PROFILE")
        print(f"   . $PROFILE")
    else:
        shell = os.path.basename(os.getenv('SHELL', 'bash'))
        profile_file = '~/.zshrc' if 'zsh' in shell else '~/.bashrc'
        print(f"   echo 'source {config.env_root}/env.sh' >> {profile_file}")
        print(f"   source {profile_file}")
    print()

    # Install toolchain
    log_raw('install_toolchain')
    print(f"   {get_message('install_toolchain_cmd')}")
    print()

    # Available commands
    log_raw('after_activation')
    print(f"{get_message('menuconfig')}")
    print(f"{get_message('menuconfig_s')}")
    print(f"{get_message('pkgs')}")
    print(f"{get_message('scons')}")
    print(f"{get_message('sdk')}")
    print()

    # Install pyocd if it was skipped
    if not config.install_pyocd:
        log_raw('install_pyocd_method')
        print()

# ============================================================================
# Argument Parsing
# ============================================================================


def parse_repo_url(url):
    """
    Parse repository URL and extract branch from fragment (#branch)
    
    Args:
        url: Repository URL with optional branch fragment (e.g., https://github.com/user/repo.git#branch1)
    
    Returns:
        dict: {'url': 'https://github.com/user/repo.git', 'branch': 'branch1'}
              or {'url': 'https://github.com/user/repo.git'} if no branch specified
    """
    from urllib.parse import urlparse, urlunparse
    
    parsed = urlparse(url)
    repo_info = {'url': urlunparse(parsed._replace(fragment=''))}
    
    if parsed.fragment:
        repo_info['branch'] = parsed.fragment
    
    return repo_info


def prompt_env_root(default_env_root, language='en'):
    """
    Prompt user to enter env-root directory
    
    Args:
        default_env_root: Default installation directory
        language: Language code ('en' or 'zh')
    
    Returns:
        str: User input env-root directory
    """
    # Set language for messages
    set_language(language)
    
    env_root = ""
    is_valid = False
    
    while not is_valid:
        # Display prompt with default value
        prompt_msg = get_message('env_root_prompt')
        default_msg = get_message('env_root_default').format(default_env_root)
        print(f"{prompt_msg} {default_msg}", end=' ')
        env_root = input().strip()
        
        # Use default if input is empty
        if not env_root:
            env_root = default_env_root
        
        # Expand user home directory
        env_root = os.path.expanduser(env_root)
        
        # Check path format (spaces, non-ASCII characters)
        if ' ' in env_root:
            log_error('python_path_invalid', 'spaces')
            continue
        if any(ord(c) > 127 for c in env_root):
            log_error('python_path_invalid', 'non-ASCII characters')
            continue
        
        # Check if parent directory exists or can be created
        parent_dir = os.path.dirname(env_root)
        if parent_dir and not os.path.exists(parent_dir):
            log_info('python_path_creating_dir', parent_dir)
            try:
                os.makedirs(parent_dir, exist_ok=True)
            except Exception:
                log_error('python_path_no_permission', parent_dir)
                continue
        
        # Check write permission
        if parent_dir:
            test_file = os.path.join(parent_dir, '.__write_test__')
            try:
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
            except Exception:
                log_error('python_path_no_permission', parent_dir)
                continue
        
        is_valid = True
    
    return env_root


def prompt_env_root_if_needed(config, args):
    """
    Prompt for env-root if needed (interactive mode, not explicitly specified)
    
    Args:
        config: TouchEnvConfig instance
        args: Parsed command line arguments
    """
    if not config.auto_mode:
        # Check if --env-root was explicitly provided
        import sys
        has_explicit_env_root = False
        for i in range(len(sys.argv)):
            if sys.argv[i] == '--env-root' and i + 1 < len(sys.argv):
                has_explicit_env_root = True
                break
            elif sys.argv[i].startswith('--env-root='):
                has_explicit_env_root = True
                break
        
        if not has_explicit_env_root:
            default_env_root = os.path.expanduser(DEFAULT_ENV_ROOT)
            config.env_root = prompt_env_root(default_env_root, config.language)
            # Recompute paths with new env_root
            config._compute_paths()


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='RT-Thread ENV Setup Script',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--env-root',
        required=False,
        default=os.path.expanduser(DEFAULT_ENV_ROOT),
        help='Installation root directory (default: ~/.rt-env)'
    )
    parser.add_argument(
        '--use-cn',
        action='store_true',
        help='Use China mirror (Gitee, TUNA PyPI)'
    )
    parser.add_argument(
        '--language',
        choices=['en', 'zh'],
        default='en',
        help='Language (en/zh)'
    )
    parser.add_argument(
        '--auto-mode',
        action='store_true',
        help='Auto-install without prompts'
    )
    parser.add_argument(
        '--install-pyocd',
        action='store_true',
        help='Install pyocd for debugging'
    )
    parser.add_argument(
        '--restore-config',
        action='store_true',
        help='Restore preserved configuration'
    )
    parser.add_argument(
        '--repo-env',
        type=str,
        default='',
        help='Custom env repository URL'
    )
    parser.add_argument(
        '--repo-packages',
        type=str,
        default='',
        help='Custom packages repository URL'
    )
    parser.add_argument(
        '--repo-sdk',
        type=str,
        default='',
        help='Custom sdk repository URL'
    )
    parser.add_argument(
        '--backup',
        choices=['preserve', 'delete_all', 'backup_all'],
        help='Backup strategy: preserve (keep config and local_pkgs), delete_all (delete all), backup_all (hardlink restore)'
    )

    args = parser.parse_args()

    # Build custom_repos dictionary from individual arguments
    args.custom_repos = {}
    if args.repo_env:
        args.custom_repos['env'] = parse_repo_url(args.repo_env)
    if args.repo_packages:
        args.custom_repos['packages'] = parse_repo_url(args.repo_packages)
    if args.repo_sdk:
        args.custom_repos['sdk'] = parse_repo_url(args.repo_sdk)

    return args

# ============================================================================
# Main Execution Function
# ============================================================================


def run_touch_env(args):
    """
    Main execution function

    Args:
        args: Parsed command line arguments

    Returns:
        int: Exit code (0 for success, non-zero for failure)
    """
    config = None

    try:
        # Step 0: Initialize configuration
        config = TouchEnvConfig(args)

        # Step 1: Interactive mode: prompt for env-root if needed
        prompt_env_root_if_needed(config, args)

        # Step 2: Check existing ENV and create backup
        check_existing_env(config)

        # Step 3: Backup configuration file (from old installation if any)
        backup_config_file(config)

        # Step 4: Setup repositories
        setup_repositories(config)

        # Step 5: Create virtual environment
        create_venv(config)

        # Step 6: Prompt for pyocd installation
        if not config.install_pyocd:
            config.install_pyocd = prompt_pyocd(config)

        # Step 7: Install packages
        install_packages(config)

        # Step 8: Restore configuration
        restore_config(config)

        # Step 9: Handle backup based on strategy
        if config.backup_path and os.path.exists(config.backup_path):
            if config.strategy == 'preserve':
                # Restore preserved items (.config and local_pkgs)
                restore_backup(config, config.backup_path, preserve_items=True)
            elif config.strategy == 'delete_all':
                # Delete backup without restoring
                cleanup_backup_directory(config.backup_path)
            elif config.strategy == 'backup_all':
                # Copy config and hardlink local_pkgs, keep backup
                restore_with_hardlink(config, config.backup_path)

        # Step 10: Show next steps
        show_next_steps(config)

        return 0

    except KeyboardInterrupt:
        print()
        log_info('installation_cancelled')
        return 1
    except Exception as e:
        print()
        log_error('installation_failed', str(e))

        # Handle backup if installation failed
        if config and config.backup_path and os.path.exists(config.backup_path):
            handle_installation_failure(config, config.backup_path, config.strategy)

        return 1


def main():
    """Main entry point"""
    try:
        args = parse_arguments()
        # Set language before logging
        set_language(args.language)
        log_info('start')
        result = run_touch_env(args)
        sys.exit(result)
    except KeyboardInterrupt:
        print()
        log_info('installation_cancelled')
        sys.exit(1)
    except Exception as e:
        print()
        log_error('installation_failed', str(e))
        sys.exit(1)

# ============================================================================
if __name__ == '__main__':
    main()
