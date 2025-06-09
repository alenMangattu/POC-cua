from typing import Dict, List, Any

from src.agent.screen import VM
from src.agent.execution_management import ExecutionContext
from src.agent.success_checker import SuccessChecker

class PrimitiveExecutor:
    def __init__(self, vm: VM, execution_context: ExecutionContext, success_checker: SuccessChecker):
        self.vm = vm
        self.execution_context = execution_context
        self.success_checker = success_checker

    def execute_primitive_step(self, step: Dict[str, Any]) -> bool:
        """Executes a single primitive step, including action, success check, and error recovery."""
        step_id = step.get("step_id", "unknown_step")
        print(f"  Executing primitive step: {step_id} - {step.get('description')}")

        action = step.get("action")
        if not action:
            print(f"    Warning: Step {step_id} has no action defined. Skipping.")
            return False

        action_type = action.get("type")
        action_details = action.get("details", {})
        vm_success = False
        vm_result = None

        try:
            if action_type == "VM_TOOLS":
                operations = action_details.get("operations", [])
                if operations:
                    vm_result = self.vm.run_operations(operations)
                    vm_success = all(op.get("success", False) for op in vm_result) 
                else:
                    print(f"    Warning: VM_TOOLS action for step {step_id} has no operations.")
                    vm_success = False

            elif action_type == "SCAN":
                method = action_details.get("method")
                area = action_details.get("area", {})
                area_type = area.get("type")
                coordinates = area.get("coordinates")
                window_id = area.get("window_id")
                vision_model_query = action_details.get("vision_model_query")

                vm_result = self.vm.scan_screen(
                    method=method,
                    area_type=area_type,
                    coordinates=coordinates,
                    window_id=window_id,
                    vision_model_query=vision_model_query
                )
                vm_success = vm_result.get("success", False)
                self.execution_context.current_screen_state = vm_result

            else:
                print(f"    Error: Unknown action type {action_type} for step {step_id}.")
                return False

            if vm_success:
                print(f"    Action for step {step_id} executed. Checking success indicators...")
                if self.success_checker.check_indicators(step.get("expected_success_indicators", [])):
                    print(f"    Step {step_id} succeeded.")
                    return True
                else:
                    print(f"    Step {step_id} action executed, but success indicators not met.")
            else:
                print(f"    Action for step {step_id} failed: {vm_result.get('error', 'Unknown error')}")

        except Exception as e:
            print(f"    Exception during step {step_id} execution: {e}")

        error_recovery_strategies = step.get("error_recovery_strategies", [])
        if error_recovery_strategies:
            print(f"    Attempting error recovery for step {step_id}...")
            for strategy in error_recovery_strategies:
                print(f"      Recovery strategy: {strategy.get('recovery_action')}")
                recovery_steps = strategy.get("recovery_steps", [])
                recovery_success = True
                for r_step in recovery_steps:
                    r_action = r_step.get("action")
                    if r_action:
                        r_action_type = r_action.get("type")
                        r_action_details = r_action.get("details", {})
                        try:
                            if r_action_type == "VM_TOOLS":
                                r_operations = r_action_details.get("operations", [])
                                if r_operations:
                                    r_vm_result = self.vm.run_operations(r_operations)
                                    if not all(op.get("success", False) for op in r_vm_result):
                                        recovery_success = False
                                        print(f"        Recovery operation failed: {r_vm_result}")
                                        break
                                else:
                                    recovery_success = False
                                    print("        Recovery VM_TOOLS action has no operations.")
                                    break
                            elif r_action_type == "SCAN":
                                r_method = r_action_details.get("method")
                                r_area = r_action_details.get("area", {})
                                r_area_type = r_area.get("type")
                                r_coordinates = r_area.get("coordinates")
                                r_window_id = r_area.get("window_id")
                                r_vision_model_query = r_action_details.get("vision_model_query")

                                r_vm_result = self.vm.scan_screen(
                                    method=r_method,
                                    area_type=r_area_type,
                                    coordinates=r_coordinates,
                                    window_id=r_window_id,
                                    vision_model_query=r_vision_model_query
                                )
                                if not r_vm_result.get("success", False):
                                    recovery_success = False
                                    print(f"        Recovery scan failed: {r_vm_result.get('error', 'Unknown error')}")
                                    break
                                self.execution_context.current_screen_state = r_vm_result
                            else:
                                recovery_success = False
                                print(f"        Unknown recovery action type: {r_action_type}")
                                break
                        except Exception as r_e:
                            recovery_success = False
                            print(f"        Exception during recovery operation: {r_e}")
                            break
                    else:
                        recovery_success = False
                        print("      Recovery step has no action defined.")
                        break

                if recovery_success:
                    print(f"      Recovery strategy {strategy.get('recovery_action')} executed successfully. Re-checking original success indicators...")
                    if self.success_checker.check_indicators(step.get("expected_success_indicators", [])):
                        print(f"      Step {step_id} succeeded after recovery.")
                        return True
                    else:
                        print(f"      Step {step_id} still failed after recovery, success indicators not met.")
                else:
                    print(f"      Recovery strategy {strategy.get('recovery_action')} failed.")
        else:
            print(f"    No error recovery strategies defined for step {step_id}.")

        print(f"  Step {step_id} ultimately failed.")
        return False 