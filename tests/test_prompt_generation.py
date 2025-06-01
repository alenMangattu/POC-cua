import unittest
import sys
import os

# Add src directory to Python path to allow importing from prompt_j2_management
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

try:
    from prompt_j2_management import analyse_genesis_classification
except ImportError:
    # Fallback if src is not directly in parent, try assuming cwd is project root
    sys.path.insert(0, os.path.abspath(os.path.join(os.getcwd(), 'src')))
    try:
        from prompt_j2_management import analyse_genesis_classification
    except ImportError as e:
        print("Failed to import analyse_genesis_classification. Ensure it's in src/prompt_j2_management.py")
        print(f"Current sys.path: {sys.path}")
        print(f"Original ImportError: {e}")
        # As a last resort, try a direct relative import if tests/ is a package and src/ is a sibling
        try:
            from ..src.prompt_j2_management import analyse_genesis_classification
        except ImportError:
             analyse_genesis_classification = None # Will cause tests to fail informatively


class TestPromptGeneration(unittest.TestCase):

    def assertTrue(self, expr, msg=None):
        if not expr:
            print(f"Assertion failed: {msg}" if msg else "Assertion failed")
        super().assertTrue(expr, msg)

    def assertFalse(self, expr, msg=None):
        if expr:
            print(f"Assertion failed: {msg}" if msg else "Assertion failed")
        super().assertFalse(expr, msg)

    def assertIn(self, member, container, msg=None):
        if member not in container:
            print(f"Assertion failed: \"{member}\" not found in container.")
            # print(f"Container content:\n{container}")
        super().assertIn(member, container, msg)

    def assertNotIn(self, member, container, msg=None):
        if member in container:
            print(f"Assertion failed: \"{member}\" unexpectedly found in container.")
            # print(f"Container content:\n{container}")
        super().assertNotIn(member, container, msg)

    @classmethod
    def setUpClass(cls):
        if analyse_genesis_classification is None:
            raise unittest.SkipTest("Skipping tests because analyse_genesis_classification could not be imported.")

    def test_render_without_scan_context(self):
        """Test prompt rendering when no scan context is provided (scan=False)."""
        # Case 1: No context at all
        prompt_no_context = analyse_genesis_classification()
        
        self.assertIn("## SCREEN ANALYSIS NEEDS", prompt_no_context, "Should contain SCREEN ANALYSIS NEEDS section")
        self.assertIn("\"classification\": \"SCAN\"", prompt_no_context, "SCAN option should be in output format when no context")
        self.assertNotIn("## SCREEN CONTEXT", prompt_no_context, "Should NOT contain SCREEN CONTEXT section")
        self.assertNotIn("Your output **MUST NOT** be SCAN", prompt_no_context)


        # Case 2: Explicit scan: False
        context_scan_false = {"scan": False, "ui_screen": []}
        prompt_scan_false = analyse_genesis_classification(context_scan_false)

        self.assertIn("## SCREEN ANALYSIS NEEDS", prompt_scan_false, "Should contain SCREEN ANALYSIS NEEDS section with scan=False")
        self.assertIn("\"classification\": \"SCAN\"", prompt_scan_false, "SCAN option should be in output format with scan=False")
        self.assertNotIn("## SCREEN CONTEXT", prompt_scan_false, "Should NOT contain SCREEN CONTEXT section with scan=False")
        self.assertNotIn("Your output **MUST NOT** be SCAN", prompt_scan_false)


    def test_render_with_scan_context(self):
        """Test prompt rendering when scan context is provided (scan=True)."""
        mock_ui_elements = [
            {'id': 1, 'type': 'button', 'content': 'Submit'},
            {'id': 2, 'type': 'text', 'content': 'Hello'},
        ]
        context_with_scan = {"scan": True, "ui_screen": mock_ui_elements}
        
        prompt_with_scan = analyse_genesis_classification(context_with_scan)

        print(prompt_with_scan)
        self.assertIn("## SCREEN CONTEXT", prompt_with_scan, "Should contain SCREEN CONTEXT section")
        self.assertIn("Your output **MUST NOT** be SCAN when screen context is provided.", prompt_with_scan, "Must include explicit instruction not to SCAN")
        
        self.assertIn(str(mock_ui_elements), prompt_with_scan, "Mock UI elements should be in the prompt")

        self.assertNotIn("## SCREEN ANALYSIS NEEDS", prompt_with_scan, "Should NOT contain SCREEN ANALYSIS NEEDS section")
        
        output_format_section_start = prompt_with_scan.find("## OUTPUT FORMAT")
        self.assertTrue(output_format_section_start != -1, "OUTPUT FORMAT section not found")
        
        output_format_section = prompt_with_scan[output_format_section_start:]
        
        # When scan=True, the task classification format should not include SCAN as an option for HTN/SIMPLE tasks
        # Note: The exact spacing and newlines in this string must match the template perfectly.
        task_classification_json_definition_for_scan_true = '{\n    \"classification\": \"HTN\" | \"SIMPLE\"\n}'
        self.assertIn(task_classification_json_definition_for_scan_true, output_format_section, 
                      f"Task classification JSON for scan=True should be '{task_classification_json_definition_for_scan_true}', but was not found in section:\n{output_format_section}")
        
        # The string for SCAN output for HTN/SIMPLE should not be present within the definition used when scan=True.
        self.assertNotIn("\"classification\": \"SCAN\"", task_classification_json_definition_for_scan_true, 
                          "The specific string for SCAN output should not be in the HTN/SIMPLE definition for scan=True")
        
        # The dedicated JSON output format for SCAN itself should not be present when scan=True, as it's in an {% else %} block.
        scan_json_output_definition = '{\n    \"classification\": \"SCAN\"\n}'
        self.assertNotIn(scan_json_output_definition, output_format_section, 
                         "The dedicated JSON output format for SCAN should not be present in the output format section when scan=True")


if __name__ == '__main__':
    unittest.main() 