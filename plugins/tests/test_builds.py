import io
import os
import struct
import tempfile
import time
import unittest

from plugins.webui.builds import BuildTaskManager


class FakeProcess(object):
    def __init__(self, output='', returncode=0):
        self.stdout = io.StringIO(output)
        self.returncode = returncode
        self.terminated = False

    def poll(self):
        return None if self.returncode is None else self.returncode

    def wait(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -15


class BuildTaskManagerTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.processes = []
        self.commands = []

    def tearDown(self):
        self.temporary.cleanup()

    def popen(self, command, **kwargs):
        self.commands.append((command, kwargs))
        process = FakeProcess('compile\nlink\n')
        self.processes.append(process)
        return process

    def wait_for_status(self, manager, task_id):
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            task = manager.get(task_id)
            if task['status'] not in ('queued', 'running'):
                return task
            time.sleep(0.01)
        self.fail('build task did not finish')

    def test_build_collects_logs_and_linked_elf_files(self):
        elf = b'\x7fELF' + b'\x02\x01' + b'\x00' * 10 + struct.pack('<H', 2)
        with open(os.path.join(self.temporary.name, 'firmware.elf'), 'wb') as output:
            output.write(elf)
        manager = BuildTaskManager(self.temporary.name, popen=self.popen)
        try:
            task = manager.start()
            result = self.wait_for_status(manager, task['task_id'])
        finally:
            manager.close()

        self.assertEqual(result['status'], 'succeeded')
        self.assertEqual(result['logs'], ['compile', 'link'])
        self.assertEqual(result['elf_files'][0]['path'], 'firmware.elf')
        self.assertEqual(self.commands[0][0][0], 'scons')
        self.assertEqual(self.commands[0][1]['cwd'], self.temporary.name)

    def test_failed_process_is_reported_without_stale_elf_outputs(self):
        def failing_popen(command, **kwargs):
            return FakeProcess('error\n', returncode=1)

        with open(os.path.join(self.temporary.name, 'stale.elf'), 'wb') as output:
            output.write(b'\x7fELF' + b'\x02\x01' + b'\x00' * 10 + struct.pack('<H', 2))
        manager = BuildTaskManager(self.temporary.name, popen=failing_popen)
        try:
            task = manager.start()
            result = self.wait_for_status(manager, task['task_id'])
        finally:
            manager.close()

        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['returncode'], 1)
        self.assertEqual(result['elf_files'], [])


if __name__ == '__main__':
    unittest.main()
