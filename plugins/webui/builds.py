"""Background SCons task management for the local WebUI."""

import os
import secrets
import struct
import subprocess
import threading
import time

from ..errors import UsageError


ACTIVE_STATUSES = frozenset(('queued', 'running'))
TERMINAL_STATUSES = frozenset(('succeeded', 'failed', 'cancelled'))
MAX_LOG_LINES = 2000
MAX_SUMMARY_LINES = 20
MAX_RETAINED_TASKS = 20


class BuildTaskManager(object):
    """Run at most one build operation and expose immutable task snapshots."""

    def __init__(self, workspace, popen=subprocess.Popen):
        self.workspace = os.path.abspath(workspace)
        self._popen = popen
        self._lock = threading.Lock()
        self._tasks = {}
        self._task_order = []
        self._processes = {}
        self._threads = {}
        self._closed = False

    def start(self, clean=False):
        operation = 'clean' if clean else 'build'
        with self._lock:
            if self._closed:
                raise UsageError('build task manager is closed')
            self._prune_tasks()
            active = next(
                (task for task in self._tasks.values() if task['status'] in ACTIVE_STATUSES),
                None,
            )
            if active:
                return self._snapshot(active)

            task_id = self._new_task_id()
            task = {
                'task_id': task_id,
                'status': 'queued',
                'progress': 0,
                'stage': 'queued',
                'message': '等待构建启动',
                'summary': [],
                'logs': [],
                'elf_files': [],
                'returncode': None,
                'operation': operation,
            }
            self._tasks[task_id] = task
            self._task_order.append(task_id)
            thread = threading.Thread(
                target=self._run,
                args=(task_id, clean),
                name='env-build-%s' % task_id,
                daemon=True,
            )
            self._threads[task_id] = thread
            thread.start()
            return self._snapshot(task)

    def get(self, task_id):
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise UsageError('build task was not found')
            return self._snapshot(task)

    def close(self):
        with self._lock:
            self._closed = True
            processes = list(self._processes.values())
            threads = list(self._threads.values())
            for task in self._tasks.values():
                if task['status'] in ACTIVE_STATUSES:
                    task.update(
                        status='cancelled',
                        progress=100,
                        stage='cancelled',
                        message='构建已停止',
                    )

        for process in processes:
            self._terminate(process)

        deadline = time.monotonic() + 2.0
        for thread in threads:
            remaining = max(0.0, deadline - time.monotonic())
            thread.join(remaining)

    def _run(self, task_id, clean):
        cpu_count = max(1, os.cpu_count() or 1)
        command = ['scons', '-c'] if clean else ['scons', '-j', str(cpu_count)]
        lines = []
        process = None
        if not self._mark_running(task_id, clean, cpu_count):
            return
        try:
            process = self._popen(
                command,
                cwd=self.workspace,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                errors='replace',
            )
            with self._lock:
                self._processes[task_id] = process
                cancelled = self._tasks[task_id]['status'] == 'cancelled'
            if cancelled:
                self._terminate(process)

            for raw_line in process.stdout or ():
                line = raw_line.rstrip('\r\n')
                if line:
                    lines.append(line)
                    self._record_output(task_id, lines)
            returncode = process.wait()
            self._finish(task_id, clean, returncode, lines)
        except OSError as exc:
            self._fail(task_id, lines, '无法启动 scons：%s' % exc)
        finally:
            if process is not None:
                if process.poll() is None:
                    self._terminate(process)
                if process.stdout is not None:
                    try:
                        process.stdout.close()
                    except OSError:
                        pass
            with self._lock:
                self._processes.pop(task_id, None)
                self._threads.pop(task_id, None)

    def _mark_running(self, task_id, clean, cpu_count):
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task['status'] == 'cancelled':
                return False
            task.update(
                status='running',
                progress=5,
                stage='building',
                message=(
                    '正在清除构建产物'
                    if clean
                    else '正在构建（%d 个并行任务）' % cpu_count
                ),
            )
            return True

    def _record_output(self, task_id, lines):
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task['status'] != 'running':
                return
            task['logs'] = lines[-MAX_LOG_LINES:]
            task['progress'] = min(90, task['progress'] + 1)

    def _finish(self, task_id, clean, returncode, lines):
        succeeded = returncode == 0
        elf_files = self._elf_files() if succeeded and not clean else []
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return
            if task['status'] == 'cancelled':
                task.update(
                    summary=lines[-MAX_SUMMARY_LINES:],
                    logs=lines[-MAX_LOG_LINES:],
                    returncode=returncode,
                )
                return

            task.update(
                status='succeeded' if succeeded else 'failed',
                progress=100,
                stage='completed' if succeeded else 'failed',
                message=self._result_message(clean, returncode),
                summary=lines[-MAX_SUMMARY_LINES:],
                logs=lines[-MAX_LOG_LINES:],
                elf_files=elf_files,
                returncode=returncode,
            )

    def _fail(self, task_id, lines, message):
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task['status'] == 'cancelled':
                return
            task.update(
                status='failed',
                progress=100,
                stage='failed',
                message=message,
                summary=lines[-MAX_SUMMARY_LINES:],
                logs=lines[-MAX_LOG_LINES:],
                returncode=None,
            )

    @staticmethod
    def _result_message(clean, returncode):
        if returncode == 0:
            return '清除构建完成' if clean else '构建完成'
        operation = '清除构建' if clean else '构建'
        return '%s失败（退出码 %d）' % (operation, returncode)

    def _elf_files(self):
        result = []
        for root, directories, names in os.walk(self.workspace):
            directories[:] = [
                name for name in directories
                if name not in ('.git', '.env', '__pycache__')
            ]
            for name in names:
                path = os.path.join(root, name)
                try:
                    with open(path, 'rb') as source:
                        header = source.read(18)
                    if not self._is_linked_elf(header):
                        continue
                    result.append({
                        'path': os.path.relpath(path, self.workspace),
                        'size': os.path.getsize(path),
                        'mtime': int(os.path.getmtime(path)),
                    })
                except (OSError, ValueError):
                    continue
        return sorted(result, key=lambda item: item['path'])[:100]

    @staticmethod
    def _is_linked_elf(header):
        if len(header) < 18 or header[:4] != b'\x7fELF':
            return False
        if header[5] == 1:
            elf_type = struct.unpack('<H', header[16:18])[0]
        elif header[5] == 2:
            elf_type = struct.unpack('>H', header[16:18])[0]
        else:
            return False
        return elf_type in (2, 3)

    def _new_task_id(self):
        task_id = secrets.token_urlsafe(12)
        while task_id in self._tasks:
            task_id = secrets.token_urlsafe(12)
        return task_id

    def _prune_tasks(self):
        retained = 0
        for task_id in reversed(self._task_order):
            task = self._tasks.get(task_id)
            if task is None or task['status'] not in TERMINAL_STATUSES:
                continue
            retained += 1
            if retained > MAX_RETAINED_TASKS:
                self._tasks.pop(task_id, None)
        self._task_order[:] = [task_id for task_id in self._task_order if task_id in self._tasks]

    @staticmethod
    def _snapshot(task):
        result = dict(task)
        result['summary'] = list(task['summary'])
        result['logs'] = list(task['logs'])
        result['elf_files'] = [dict(item) for item in task['elf_files']]
        return result

    @staticmethod
    def _terminate(process):
        if process.poll() is not None:
            return
        try:
            process.terminate()
        except OSError:
            return
