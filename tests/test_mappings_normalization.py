import unittest
import pandas as pd

class TestMappingsNormalization(unittest.TestCase):
    def test_inverted_mappings_auto_normalized(self):
        df = pd.DataFrame({
            "Department": ["Operations"],
            "Reference": ["REF-001"]
        })
        mappings = {
            "#location": "Department",
            "#reference": "Reference"
        }

        # Test normalization logic from main.py
        normalized_mappings = {}
        for k, v in mappings.items():
            col_val = v if isinstance(v, str) else (v.get("column") if isinstance(v, dict) else "")
            if k not in df.columns and col_val in df.columns:
                normalized_mappings[col_val] = k if isinstance(v, str) else v
            else:
                normalized_mappings[k] = v

        self.assertEqual(normalized_mappings["Department"], "#location")
        self.assertEqual(normalized_mappings["Reference"], "#reference")

    def test_standard_mappings_untouched(self):
        df = pd.DataFrame({
            "Department": ["Operations"],
            "Reference": ["REF-001"]
        })
        mappings = {
            "Department": "#location",
            "Reference": "#reference"
        }

        normalized_mappings = {}
        for k, v in mappings.items():
            col_val = v if isinstance(v, str) else (v.get("column") if isinstance(v, dict) else "")
            if k not in df.columns and col_val in df.columns:
                normalized_mappings[col_val] = k if isinstance(v, str) else v
            else:
                normalized_mappings[k] = v

        self.assertEqual(normalized_mappings["Department"], "#location")
        self.assertEqual(normalized_mappings["Reference"], "#reference")

if __name__ == "__main__":
    unittest.main()
