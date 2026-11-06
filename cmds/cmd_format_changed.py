"""Format changed C/C++ files with clang-format 22.1.8."""

import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys

from env_paths import get_env_root


CLANG_FORMAT_VERSION = '22.1.8'
EXTENSIONS = {'.c', '.h', '.cc', '.hh', '.cpp', '.hpp', '.cxx', '.hxx', '.c++', '.h++', '.inl', '.ipp', '.tpp'}
DIFF_OPTIONS = ['-z', '--diff-filter=ACMRT', '--no-ext-diff', '--ignore-submodules=all']


class CommandError(Exception):
    pass


def find_tool(name):
    filenames = [name]
    if os.name == 'nt':
        extensions = (os.environ.get('PATHEXT') or '.COM;.EXE;.BAT;.CMD').split(os.pathsep)
        filenames = [name + extension for extension in extensions if re.fullmatch(r'\.[a-zA-Z0-9]+', extension)]
    directories = [Path(get_env_root()) / 'tools' / 'bin']
    directories.extend(Path(entry.strip('"')) for entry in os.environ.get('PATH', '').split(os.pathsep) if entry)
    for directory in directories:
        if not directory.is_absolute():
            continue
        # An absolute candidate prevents Windows/Python 3.11 from searching cwd first.
        for filename in filenames:
            command = shutil.which(str(directory / filename))
            if command:
                return os.path.abspath(command)
    return None


def git(*args, cwd=None):
    command = find_tool('git')
    if not command:
        raise CommandError('Git was not found in Env tools or absolute PATH directories.')
    result = subprocess.run([command, *args], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise CommandError(result.stderr.decode('utf-8', errors='replace').strip())
    return result.stdout


def filenames(data):
    return {os.fsdecode(name) for name in data.split(b'\0') if name}


def changed_files(root, base):
    tracked = set()
    symlinks = set()
    submodules = set()
    for entry in git('ls-files', '--stage', '-z', cwd=root).split(b'\0'):
        if not entry:
            continue
        metadata, _, name = entry.partition(b'\t')
        mode, _, stage = metadata.split()
        if stage != b'0':
            raise CommandError('Resolve merge conflicts before running format-changed.')
        name = os.fsdecode(name)
        tracked.add(name)
        if mode == b'120000':
            symlinks.add(name)
        elif mode == b'160000':
            submodules.add(name)

    names = set()
    # Disable rename detection so each NUL-delimited status has exactly one path.
    unstaged = git('diff', '--name-status', '--no-renames', *DIFF_OPTIONS, '--', cwd=root).split(b'\0')
    for status, name in zip(unstaged[::2], unstaged[1::2]):
        name = os.fsdecode(name)
        names.add(name)
        if status == b'T':
            # Use the worktree type after replacement, retaining Windows placeholder filtering.
            symlinks.discard(name)
    names.update(filenames(git('diff', '--cached', '--name-only', *DIFF_OPTIONS, '--', cwd=root)))
    names.update(filenames(git('ls-files', '--others', '--exclude-standard', '-z', cwd=root)))

    if base:
        revision = git('rev-parse', '--verify', '--end-of-options', base + '^{commit}', cwd=root).strip().decode('ascii')
        ancestor = git('merge-base', 'HEAD', revision, cwd=root).strip().decode('ascii')
        historical = filenames(git('diff', '--name-only', *DIFF_OPTIONS, ancestor, 'HEAD', '--', cwd=root))
        names.update(historical & tracked)

    selected = []
    for name in sorted(names - symlinks):
        # Historical diffs can name files now owned by a submodule in the index.
        if any(name == submodule or name.startswith(submodule + '/') for submodule in submodules):
            continue
        path = root / name
        if path.suffix.lower() not in EXTENSIONS or not path.is_file() or has_link_component(path, root):
            continue
        try:
            path.resolve().relative_to(root)
        except ValueError:
            continue
        selected.append(path)
    return selected


def has_link_component(path, root):
    current = root
    for part in path.relative_to(root).parts:
        current = current / part
        metadata = current.lstat()
        # Reparse points include Windows junctions; Path.is_junction needs Python 3.12.
        if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            return True
    return False


def has_project_style(path, root):
    directory = path.parent
    while True:
        if any((directory / name).is_file() for name in ('.clang-format', '_clang-format')):
            return True
        if directory == root:
            return False
        directory = directory.parent


def find_clang_format():
    command = find_tool('clang-format')
    if not command:
        raise CommandError('clang-format 22.1.8 was not found. Install it and add it to PATH, or use Env for Windows with it bundled.')
    result = subprocess.run([command, '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    version = result.stdout.decode('utf-8', errors='replace').strip()
    match = re.search(r'\bversion\s+(\d+\.\d+\.\d+)\b', version)
    if result.returncode or not match or match.group(1) != CLANG_FORMAT_VERSION:
        raise CommandError('clang-format 22.1.8 is required; %s reported: %s' % (command, version or 'unknown version'))
    return command


def printable(text, stream):
    encoding = getattr(stream, 'encoding', None) or 'utf-8'
    return str(text).encode(encoding, errors='backslashreplace').decode(encoding)


def cmd(args):
    try:
        root = Path(os.fsdecode(git('rev-parse', '--show-toplevel').rstrip(b'\r\n'))).resolve()
        files = changed_files(root, args.base)
        if not files:
            print('No changed C/C++ files to process.')
            return 0

        missing = [path.relative_to(root).as_posix() for path in files if not has_project_style(path, root)]
        if missing:
            raise CommandError(
                'No .clang-format or _clang-format found inside the repository for:\n  '
                + '\n  '.join(missing)
                + "\nAdd the project's formatting configuration and run again. No files were formatted."
            )

        clang_format = find_clang_format()
        options = ['--style=file', '--fallback-style=none', '--Werror']
        options += ['--dry-run'] if args.check else ['-i']
        action = 'Checking' if args.check else 'Formatting'
        print('Selected %d changed C/C++ file(s).' % len(files), flush=True)
        failed = False
        for path in files:
            print('%s: %s' % (action, printable(path.relative_to(root).as_posix(), sys.stdout)), flush=True)
            result = subprocess.run([clang_format, *options, str(path)], cwd=root)
            if result.returncode:
                failed = True
                if not args.check:
                    return result.returncode if result.returncode > 0 else 1
        if failed:
            return 1
        if args.check:
            print('Formatting check passed.')
        else:
            print('Done. Review git diff and git add the files you want to commit.')
        return 0
    except (CommandError, OSError) as error:
        print(printable('Error: %s' % error, sys.stderr), file=sys.stderr)
        return 1


def add_parser(sub):
    parser = sub.add_parser(
        'format-changed',
        help=__doc__,
        description=(
            'Format whole changed C/C++ files with clang-format 22.1.8. '
            'Includes unstaged, staged and untracked files; leaves the Git index unchanged.'
        ),
    )
    parser.add_argument('--base', metavar='REF', help='also include committed changes since the merge base of HEAD and REF')
    parser.add_argument('--check', action='store_true', help='check formatting without modifying files (nonzero exit on violations)')
    parser.set_defaults(func=cmd)
