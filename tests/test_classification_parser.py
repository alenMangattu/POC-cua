import sys
import os
import unittest

# Get the absolute path to the directory containing this test file (e.g., /path/to/altra/tests)
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# Get the absolute path to the project's src directory (e.g., /path/to/altra/src)
_SRC_DIR = os.path.abspath(os.path.join(_CURRENT_DIR, '../src'))

# Add the src directory to Python's module search path if it's not already there
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

# Now, the import should work correctly as `calling_tools` is in `_SRC_DIR`
from calling_tools.classificaition import parse_llm_classification_output

class TestClassificationParser(unittest.TestCase):

    def test_simple_classification(self):
        input_str = '{\n    "classification": "SIMPLE"\n}'
        expected = {"classification": "SIMPLE"}
        self.assertEqual(parse_llm_classification_output(input_str), expected)

    def test_htn_classification_with_markdown(self):
        input_str = '```json\n{\n    "classification": "HTN"\n}\n```'
        expected = {"classification": "HTN"}
        self.assertEqual(parse_llm_classification_output(input_str), expected)

    def test_refused_classification(self):
        input_str = '{\n    "classification": "REFUSED",\n    "reason": "This is not allowed."\n}'
        expected = {"classification": "REFUSED", "reason": "This is not allowed."}
        self.assertEqual(parse_llm_classification_output(input_str), expected)

    def test_conversational_classification(self):
        input_str = '{\n    "classification": "CONVERSATIONAL",\n    "response": "Hello there!"\n}'
        expected = {"classification": "CONVERSATIONAL", "response": "Hello there!"}
        self.assertEqual(parse_llm_classification_output(input_str), expected)

    def test_scan_omni_parser_with_scanner_tags(self):
        # This test relies on the fallback brace finding since scanner tag handling is commented out in the main script
        input_str = '<scanner>\n{\n    "classification": "SCAN",\n    "method": "Omni Parser"\n}\n</scanner>'
        expected = {"classification": "SCAN", "method": "Omni Parser"}
        self.assertEqual(parse_llm_classification_output(input_str), expected)

    def test_scan_omni_parser_vision_model_with_markdown_and_leading_text(self):
        input_str = 'Some leading text from LLM...\n```json\n{\n    "classification": "SCAN",\n    "method": "Omni Parser + Vision Model",\n    "vision_model_query": "Describe the cat."\n}\n```'
        expected = {"classification": "SCAN", "method": "Omni Parser + Vision Model", "vision_model_query": "Describe the cat."}
        self.assertEqual(parse_llm_classification_output(input_str), expected)
    
    def test_scan_vision_model_simple_markdown(self):
        input_str = '```\n{\n    "classification": "SCAN",\n    "method": "Omni Parser + Vision Model",\n    "vision_model_query": "Describe the dog."\n}\n```'
        expected = {"classification": "SCAN", "method": "Omni Parser + Vision Model", "vision_model_query": "Describe the dog."}
        self.assertEqual(parse_llm_classification_output(input_str), expected)

    def test_plain_json_no_wrappers(self):
        input_str = '{"classification": "SIMPLE"}'
        expected = {"classification": "SIMPLE"}
        self.assertEqual(parse_llm_classification_output(input_str), expected)
    
    def test_json_with_surrounding_text_fallback_extraction(self):
        input_str = 'User said: click the button\n{"classification": "SIMPLE"}\nThanks!'
        expected = {"classification": "SIMPLE"} # Fallback extracts the JSON
        self.assertEqual(parse_llm_classification_output(input_str), expected)

    def test_invalid_json_string(self):
        input_str = 'this is not json'
        expected = {"classification": "ERROR", "error": "Invalid JSON output from LLM: Expecting value: line 1 column 1 (char 0)", "raw_output": input_str}
        self.assertEqual(parse_llm_classification_output(input_str), expected)

    def test_missing_classification_key(self):
        input_str = '{\n    "foo": "bar"\n}'
        expected = {"classification": "ERROR", "error": "Missing 'classification' key in LLM output.", "raw_output": input_str}
        self.assertEqual(parse_llm_classification_output(input_str), expected)

    def test_scan_missing_method_key(self):
        input_str = '{\n    "classification": "SCAN"\n}'
        expected = {"classification": "ERROR", "error": "Missing 'method' key for SCAN classification.", "raw_output": input_str}
        self.assertEqual(parse_llm_classification_output(input_str), expected)

    def test_scan_vision_model_missing_query_key(self):
        input_str = '{\n    "classification": "SCAN",\n    "method": "Omni Parser + Vision Model"\n}'
        expected = {"classification": "ERROR", "error": "Missing 'vision_model_query' for SCAN with Vision Model.", "raw_output": input_str}
        self.assertEqual(parse_llm_classification_output(input_str), expected)

    def test_empty_string_input(self):
        input_str = ''
        expected = {"classification": "ERROR", "error": "Invalid JSON output from LLM: Expecting value: line 1 column 1 (char 0)", "raw_output": input_str}
        self.assertEqual(parse_llm_classification_output(input_str), expected)

    def test_malformed_json_trailing_comma(self):
        input_str = '{"classification": "SIMPLE", '
        result = parse_llm_classification_output(input_str)
        self.assertEqual(result["classification"], "ERROR")
        self.assertTrue("Invalid JSON output from LLM" in result["error"])
        self.assertEqual(result["raw_output"], input_str)


if __name__ == '__main__':
    unittest.main()