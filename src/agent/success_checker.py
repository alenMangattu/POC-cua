import os
from typing import Dict, List, Any

from src.agent.screen import VM
from src.agent.execution_management import ExecutionContext

class SuccessChecker:
    def __init__(self, vm: VM, execution_context: ExecutionContext):
        self.vm = vm
        self.execution_context = execution_context

    def check_indicators(self, indicators: List[Dict[str, Any]]) -> bool:
        """Checks if any of the given success indicators are met."""
        if not indicators:
            return True

        self.execution_context.wmctrl_info = self.vm.get_wmctrl_info()

        for indicator in indicators:
            ind_type = indicator.get("type")
            details = indicator.get("details", {})

            if ind_type == "window_appeared":
                title_contains = details.get("window_title_contains")
                if title_contains and self.execution_context.wmctrl_info and self.execution_context.wmctrl_info.get("window_list"):
                    if any(title_contains in w.get("title", "") for w in self.execution_context.wmctrl_info["window_list"]):
                        print(f"    Success indicator met: window_appeared (title contains: {title_contains})")
                        return True

            elif ind_type == "active_window_title_contains":
                title_contains = details.get("window_title_contains")
                if title_contains and self.execution_context.wmctrl_info and self.execution_context.wmctrl_info.get("active_window") and self.execution_context.wmctrl_info["active_window"].get("title"):
                    if title_contains in self.execution_context.wmctrl_info["active_window"]["title"]:
                        print(f"    Success indicator met: active_window_title_contains (title contains: {title_contains})")
                        return True

            elif ind_type == "ui_element_visible":
                element_text = details.get("element_text")
                element_description = details.get("element_description")
                scan_result = self.vm.scan_screen(method="Omni Parser", area_type="full")
                if scan_result.get("success") and scan_result.get("ui_elements"):
                    for element in scan_result["ui_elements"]:
                        if element_text and element_text in element.get("text", ""):
                            print(f"    Success indicator met: ui_element_visible (text: {element_text})")
                            return True
                        if element_description and element_description in element.get("description", ""):
                            print(f"    Success indicator met: ui_element_visible (description: {element_description})")
                            return True

            elif ind_type == "text_on_screen":
                text_to_find = details.get("text_to_find")
                scan_result = self.vm.scan_screen(method="Omni Parser", area_type="full")
                if scan_result.get("success") and scan_result.get("ui_classification") and scan_result["ui_classification"].get("text_content"):
                    if text_to_find in scan_result["ui_classification"]["text_content"]:
                        print(f"    Success indicator met: text_on_screen (text: {text_to_find})")
                        return True

            elif ind_type == "file_exists":
                file_path = details.get("file_path")
                if file_path and os.path.exists(file_path):
                    print(f"    Success indicator met: file_exists (path: {file_path})")
                    return True

            elif ind_type == "no_error_dialog_visible":
                if not self.execution_context.last_error:
                    scan_result = self.vm.scan_screen(method="Omni Parser", area_type="full")
                    if not scan_result.get("success") or "error" in scan_result.get("message", "").lower():
                        continue
                    if not any(err_text in scan_result.get("ui_classification", {}).get("text_content", "").lower() for err_text in ["error", "fail", "exception"]):
                        print(f"    Success indicator met: no_error_dialog_visible")
                        return True

            elif ind_type == "custom_condition":
                print(f"    Warning: Custom condition indicator not fully implemented. Assuming False.")
                return False

        return False 