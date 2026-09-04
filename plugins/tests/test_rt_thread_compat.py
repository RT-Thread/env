import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]


class RtThreadCompatScriptTest(unittest.TestCase):
    def test_compatibility_uses_the_sdk_toolchain_flow(self):
        text = (REPOSITORY / '.github/scripts/rt_thread_compat.sh').read_text(encoding='utf-8')
        self.assertIn('CONFIG_PKG_USING_ARM_NONE_EABI_GCC', text)
        self.assertIn('pkgs --update-force', text)
        self.assertIn('arm-none-eabi-gcc-$SDK_TOOLCHAIN_VERSION', text)
        self.assertNotIn('RTT_EXEC_PATH', text)
        self.assertNotIn('/opt/', text)

    def test_workflow_does_not_install_a_toolchain_outside_the_sdk(self):
        text = (REPOSITORY / '.github/workflows/rt-thread-compat.yml').read_text(encoding='utf-8')
        self.assertIn('Checkout SDK index', text)
        self.assertNotIn('RTT_EXEC_PATH', text)
        self.assertNotIn('/opt/', text)
        self.assertNotIn('toolchains-ci/releases', text)

    def test_compat_script_covers_qemu_and_rt_spark(self):
        text = (REPOSITORY / '.github/scripts/rt_thread_compat.sh').read_text(encoding='utf-8')
        self.assertIn('bsp/qemu-vexpress-a9', text)
        self.assertIn('bsp/stm32/stm32f407-rt-spark', text)
