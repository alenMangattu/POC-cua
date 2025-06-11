import unittest
from unittest.mock import Mock, patch
import os

from src.agent.tasks.success_checker import SuccessChecker
from src.agent.screen import VM
from src.agent.tasks.execution_management import ExecutionContext

class TestSuccessChecker(unittest.TestCase):
    def setUp(self):
        self.mock_vm = Mock(spec=VM)
        self.mock_execution_context = Mock(spec=ExecutionContext)
        self.success_checker = SuccessChecker(self.mock_vm, self.mock_execution_context)

        self.mock_execution_context.wmctrl_info = {
            "active_window": {
                "desktop": 0,
                "geometry": {
                    "height": 721,
                    "width": 1298,
                    "x": 132,
                    "y": 64
                },
                "id": "0x02a0000a",
                "title": "user@user: ~"
            },
            "default_applications": [
                {
                    "application": "firefox_firefox.desktop",
                    "mime_type": "text/html"
                },
                {
                    "application": "firefox_firefox.desktop",
                    "mime_type": "x-scheme-handler/mailto"
                },
                {
                    "application": "",
                    "mime_type": "text/calendar"
                },
                {
                    "application": "",
                    "mime_type": "audio/mpeg"
                },
                {
                    "application": "",
                    "mime_type": "video/mp4"
                },
                {
                    "application": "org.gnome.eog.desktop",
                    "mime_type": "image/jpeg"
                }
            ],
            "success": True,
            "system_info": {
                "free": "total        used        free      shared  buff/cache   available\nMem:           960Mi       704Mi        62Mi        19Mi       350Mi       255Mi\nSwap:          2.9Gi       403Mi       2.5Gi",
                "lscpu": "Architecture:                         x86_64\nCPU op-mode(s):                       32-bit, 64-bit\nAddress sizes:                        48 bits physical, 48 bits virtual\nByte Order:                           Little Endian\nCPU(s):                               2\nOn-line CPU(s) list:                  0,1\nVendor ID:                            AuthenticAMD\nModel name:                           AMD Athlon Silver 3050U with Radeon Graphics\nCPU family:                           23\nModel:                                24\nThread(s) per core:                   1\nCore(s) per socket:                   2\nSocket(s):                            1\nStepping:                             1\nBogoMIPS:                             4591.35\nFlags:                                fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov pat pse36 clflush mmx fxsr sse sse2 ht syscall nx mmxext fxsr_opt pdpe1gb rdtscp lm rep_good nopl cpuid extd_apicid tsc_known_freq pni pclmulqdq ssse3 fma cx16 sse4_1 sse4_2 x2apic movbe popcnt tsc_deadline_timer aes xsave avx f16c rdrand hypervisor lahf_lm cmp_legacy svm cr8_legacy abm sse4a misalignsse 3dnowprefetch osvw perfctr_core ssbd ibpb vmmcall fsgsbase tsc_adjust bmi1 avx2 smep bmi2 rdseed adx smap clflushopt sha_ni xsaveopt xsavec xgetbv1 clzero xsaveerptr virt_ssbd arat npt lbrv nrip_save tsc_scale vmcb_clean flushbyasid pausefilter pfthreshold v_vmsave_vmload vgif overflow_recov succor arch_capabilities\nVirtualization:                       AMD-V\nHypervisor vendor:                    KVM\nVirtualization type:                  full\nL1d cache:                            128 KiB (2 instances)",
                "uname": "Linux user 6.14.0-15-generic #15-Ubuntu SMP PREEMPT_DYNAMIC Sun Apr  6 15:05:05 UTC 2025 x86_64 x86_64 x86_64 GNU/Linux"
            },
            "window_list": [
                {
                    "desktop": 0,
                    "geometry": {
                        "height": 721,
                        "width": 1298,
                        "x": 132,
                        "y": 64
                    },
                    "id": "0x02a0000a",
                    "title": "user@user: ~"
                }
            ]
        }


    def test_no_indicators(self):
        self.assertTrue(self.success_checker.check_indicators([]))

    def test_window_appeared_success(self):
        indicators = [{"type": "window_appeared", "details": {"window_title_contains": "user@user: ~"}}]
        self.assertTrue(self.success_checker.check_indicators(indicators))

    def test_window_appeared_fail(self):
        indicators = [{"type": "window_appeared", "details": {"window_title_contains": "NonExistentWindow"}}]
        self.assertFalse(self.success_checker.check_indicators(indicators))

    def test_active_window_title_contains_success(self):
        indicators = [{"type": "active_window_title_contains", "details": {"window_title_contains": "user@user: ~"}}]
        self.assertTrue(self.success_checker.check_indicators(indicators))

    def test_active_window_title_contains_fail(self):
        indicators = [{"type": "active_window_title_contains", "details": {"window_title_contains": "AnotherTitle"}}]
        self.assertFalse(self.success_checker.check_indicators(indicators))

    def test_ui_element_visible_text_success(self):
        self.mock_vm.scan_screen.return_value = {"success": True, "ui_elements": [{"text": "Hello World"}]}
        indicators = [{"type": "ui_element_visible", "details": {"element_text": "Hello World"}}]
        self.assertTrue(self.success_checker.check_indicators(indicators))

    def test_ui_element_visible_description_success(self):
        self.mock_vm.scan_screen.return_value = {"success": True, "ui_elements": [{"description": "A button"}]}
        indicators = [{"type": "ui_element_visible", "details": {"element_description": "A button"}}]
        self.assertTrue(self.success_checker.check_indicators(indicators))

    def test_ui_element_visible_fail(self):
        self.mock_vm.scan_screen.return_value = {"success": True, "ui_elements": [{"text": "Something Else"}]}
        indicators = [{"type": "ui_element_visible", "details": {"element_text": "NonExistent"}}]
        self.assertFalse(self.success_checker.check_indicators(indicators))

    def test_text_on_screen_success(self):
        self.mock_vm.scan_screen.return_value = {"success": True, "ui_classification": {"text_content": "This is some text on screen."}}
        indicators = [{"type": "text_on_screen", "details": {"text_to_find": "some text"}}]
        self.assertTrue(self.success_checker.check_indicators(indicators))

    def test_text_on_screen_fail(self):
        self.mock_vm.scan_screen.return_value = {"success": True, "ui_classification": {"text_content": "This is some text on screen."}}
        indicators = [{"type": "text_on_screen", "details": {"text_to_find": "NonExistent Text"}}]
        self.assertFalse(self.success_checker.check_indicators(indicators))

    @patch('os.path.exists')
    def test_file_exists_success(self, mock_exists):
        mock_exists.return_value = True
        indicators = [{"type": "file_exists", "details": {"file_path": "/tmp/test_file.txt"}}]
        self.assertTrue(self.success_checker.check_indicators(indicators))

    @patch('os.path.exists')
    def test_file_exists_fail(self, mock_exists):
        mock_exists.return_value = False
        indicators = [{"type": "file_exists", "details": {"file_path": "/tmp/non_existent_file.txt"}}]
        self.assertFalse(self.success_checker.check_indicators(indicators))

    def test_no_error_dialog_visible_success(self):
        self.mock_execution_context.last_error = None
        self.mock_vm.scan_screen.return_value = {"success": True, "message": "No errors", "ui_classification": {"text_content": "All good"}}
        indicators = [{"type": "no_error_dialog_visible"}]
        self.assertTrue(self.success_checker.check_indicators(indicators))

    def test_no_error_dialog_visible_with_last_error(self):
        self.mock_execution_context.last_error = "An error occurred"
        indicators = [{"type": "no_error_dialog_visible"}]
        self.assertFalse(self.success_checker.check_indicators(indicators))

    def test_no_error_dialog_visible_scan_failure(self):
        self.mock_execution_context.last_error = None
        self.mock_vm.scan_screen.return_value = {"success": False, "message": "scan failed"}
        indicators = [{"type": "no_error_dialog_visible"}]
        self.assertFalse(self.success_checker.check_indicators(indicators))

    def test_no_error_dialog_visible_error_in_message(self):
        self.mock_execution_context.last_error = None
        self.mock_vm.scan_screen.return_value = {"success": True, "message": "An error occurred", "ui_classification": {"text_content": "No error"}}
        indicators = [{"type": "no_error_dialog_visible"}]
        self.assertFalse(self.success_checker.check_indicators(indicators))

    def test_no_error_dialog_visible_error_in_text_content(self):
        self.mock_execution_context.last_error = None
        self.mock_vm.scan_screen.return_value = {"success": True, "message": "All good", "ui_classification": {"text_content": "This has an error"}}
        indicators = [{"type": "no_error_dialog_visible"}]
        self.assertFalse(self.success_checker.check_indicators(indicators))

    def test_custom_condition(self):
        indicators = [{"type": "custom_condition"}]
        self.assertFalse(self.success_checker.check_indicators(indicators))


if __name__ == '__main__':
    unittest.main() 