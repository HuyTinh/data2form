import unittest
from datetime import date, datetime
import os
import tempfile

from playwright.sync_api import sync_playwright
from form_fields import (
    apply_field_value,
    infer_field_type,
    is_populated_cell_value,
    normalize_field_type,
    normalize_date_value,
    parse_boolean_value,
    validate_target_url,
    validate_mappings,
)


class FormFieldTests(unittest.TestCase):
    def test_legacy_selection_type_normalizes_to_select(self):
        self.assertEqual(normalize_field_type("selection"), "select")
        self.assertEqual(normalize_field_type("SELECT"), "select")

    def test_supported_general_field_types_are_recognized(self):
        for field_type in ("text", "number", "email", "textarea", "select", "checkbox", "radio", "date", "upload", "click"):
            with self.subTest(field_type=field_type):
                self.assertEqual(normalize_field_type(field_type), field_type)

    def test_unknown_field_type_fails_with_actionable_error(self):
        with self.assertRaisesRegex(ValueError, "Unsupported field type: color-picker"):
            normalize_field_type("color-picker")

    def test_checkbox_values_accept_common_true_and_false_strings(self):
        for value in ("true", "YES", "1", "x", "checked", True, 1):
            with self.subTest(value=value):
                self.assertIs(parse_boolean_value(value), True)
        for value in ("false", "no", "0", "unchecked", False, 0):
            with self.subTest(value=value):
                self.assertIs(parse_boolean_value(value), False)

    def test_checkbox_rejects_ambiguous_value(self):
        with self.assertRaisesRegex(ValueError, "not a recognized boolean"):
            parse_boolean_value("maybe")

    def test_date_values_normalize_to_html_date_format(self):
        self.assertEqual(normalize_date_value("24/09/2026"), "2026-09-24")
        self.assertEqual(normalize_date_value("2026-09-24 00:00:00"), "2026-09-24")
        self.assertEqual(normalize_date_value(date(2026, 9, 24)), "2026-09-24")
        self.assertEqual(normalize_date_value(datetime(2026, 9, 24, 10, 30)), "2026-09-24")

    def test_date_rejects_ambiguous_or_invalid_value(self):
        with self.assertRaisesRegex(ValueError, "Expected an unambiguous date"):
            normalize_date_value("09/24/2026")

    def test_mapping_validation_reports_invalid_selector_column_and_type(self):
        errors = validate_mappings(
            {
                "Customer": {"selector": "", "type": "text"},
                "Status": {"selector": "#status", "type": "selection", "column": "Missing"},
                "Color": {"selector": "#color", "type": "color-picker", "column": "Color"},
            },
            ["Customer", "Status", "Color"],
        )
        self.assertEqual(len(errors), 3)
        self.assertIn("Customer", errors[0])
        self.assertIn("Missing", errors[1])
        self.assertIn("color-picker", errors[2])

    def test_legacy_mapping_shape_remains_valid(self):
        self.assertEqual(validate_mappings({"Email": "#email"}, ["Email"]), [])

    def test_empty_mapping_configuration_is_rejected(self):
        self.assertTrue(validate_mappings({}, ["Email"]))

    def test_target_url_validation_requires_http_or_https_host(self):
        self.assertEqual(validate_target_url("https://example.test/form"), [])
        self.assertEqual(validate_target_url("http://127.0.0.1:8000/form"), [])
        self.assertTrue(validate_target_url("javascript:alert(1)"))
        self.assertTrue(validate_target_url("not a URL"))

    def test_zero_and_false_are_valid_cell_values_but_blank_and_nan_are_empty(self):
        self.assertTrue(is_populated_cell_value(0))
        self.assertTrue(is_populated_cell_value(False))
        self.assertFalse(is_populated_cell_value("  "))
        self.assertFalse(is_populated_cell_value(float("nan")))

    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)
        cls.page = cls.browser.new_page()
        cls.page.set_default_timeout(3000)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.page.set_content("""
          <form>
            <input id="name" type="text"><input id="count" type="number">
            <input id="email" type="email"><textarea id="notes"></textarea>
            <input id="date" type="date"><label id="active-label"><input id="active" type="checkbox"></label>
            <fieldset id="gender">
              <label><input type="radio" name="gender" value="female">Female</label>
              <label><input type="radio" name="gender" value="male">Male</label>
            </fieldset>
            <fieldset id="interests">
              <label><input type="checkbox" value="music">Music</label>
              <label><input type="checkbox" value="travel">Travel</label>
            </fieldset>
            <select id="countries" multiple><option value="jp">Japan</option><option value="vn">Vietnam</option></select>
            <select id="country"><option>Vietnam</option><option>Japan</option><option value="us">United States</option></select>
            <input id="custom" role="combobox" aria-controls="options" readonly>
            <input id="custom-multiple" role="combobox" aria-controls="options-multiple" readonly multiple>
            <div id="options" role="listbox" hidden>
              <div role="option" onclick="custom.value=this.textContent; options.hidden=true">Japan</div>
              <div role="option" onclick="custom.value=this.textContent; options.hidden=true">Vietnam</div>
            </div>
            <div id="options-multiple" role="listbox" hidden>
              <div role="option" onclick="const input=document.getElementById('custom-multiple'); input.value=[input.value,this.textContent].filter(Boolean).join(' | ')">Japan</div>
              <div role="option" onclick="const input=document.getElementById('custom-multiple'); input.value=[input.value,this.textContent].filter(Boolean).join(' | ')">Vietnam</div>
            </div>
            <label id="upload-label">Choose file<input id="file" type="file"></label>
            <input id="hidden-file" type="file" style="display:none">
          </form>
          <script>
            custom.addEventListener('click', () => { options.hidden = false; });
            document.getElementById('custom-multiple').addEventListener('click', () => { document.getElementById('options-multiple').hidden = false; });
          </script>
        """)

    def test_applies_text_number_email_and_textarea_values(self):
        cases = [("#name", "text", "Ada"), ("#count", "number", "42"),
                 ("#email", "email", "ada@example.test"), ("#notes", "textarea", "Line one")]
        for selector, field_type, value in cases:
            with self.subTest(field_type=field_type):
                locator = self.page.locator(selector)
                self.assertEqual(apply_field_value(self.page, locator, field_type, value), value)

    def test_applies_date_and_checkbox_values(self):
        date_field = self.page.locator("#date")
        self.assertEqual(apply_field_value(self.page, date_field, "date", "24/09/2026"), "2026-09-24")
        checkbox = self.page.locator("#active")
        self.assertEqual(apply_field_value(self.page, checkbox, "checkbox", "yes"), "true")
        self.assertEqual(apply_field_value(self.page, checkbox, "checkbox", "no"), "false")

    def test_selects_radio_and_native_select_options(self):
        self.assertEqual(apply_field_value(self.page, self.page.locator("#gender"), "radio", "Female"), "Female")
        self.assertTrue(self.page.get_by_label("Female").is_checked())
        self.assertEqual(apply_field_value(self.page, self.page.locator("#country"), "selection", "Japan"), "Japan")

    def test_supports_direct_radio_and_wrapping_checkbox_selectors(self):
        apply_field_value(self.page, self.page.locator("#gender input[value='male']"), "radio", "Male")
        self.assertTrue(self.page.get_by_label("Male", exact=True).is_checked())
        self.assertEqual(apply_field_value(self.page, self.page.locator("#active-label"), "checkbox", "true"), "true")

    def test_direct_radio_selector_can_choose_another_option_in_its_group(self):
        apply_field_value(self.page, self.page.locator("#gender input[value='male']"), "radio", "Female")
        self.assertTrue(self.page.get_by_label("Female", exact=True).is_checked())

    def test_selects_multiple_custom_dropdown_options(self):
        result = apply_field_value(self.page, self.page.locator("#custom-multiple"), "select", "Japan|Vietnam", multiple=True)
        self.assertEqual(result, "Japan | Vietnam")

    def test_selects_multiple_native_options_independent_of_excel_order(self):
        result = apply_field_value(self.page, self.page.locator("#countries"), "select", "Vietnam|Japan", multiple=True)
        self.assertEqual(self.page.locator("#countries").evaluate("node => Array.from(node.selectedOptions).map(option => option.value)"), ["jp", "vn"])
        self.assertEqual(result, "Japan | Vietnam")

    def test_sets_checkbox_group_from_pipe_separated_values(self):
        result = apply_field_value(self.page, self.page.locator("#interests"), "checkbox", "Music|Travel", multiple=True)
        self.assertEqual(result, "Music | Travel")
        self.assertTrue(self.page.get_by_label("Music", exact=True).is_checked())
        self.assertTrue(self.page.get_by_label("Travel", exact=True).is_checked())

    def test_native_select_accepts_option_value_as_well_as_label(self):
        self.assertEqual(apply_field_value(self.page, self.page.locator("#country"), "select", "us"), "United States")

    def test_selects_option_from_custom_accessible_dropdown(self):
        result = apply_field_value(self.page, self.page.locator("#custom"), "select", "Japan")
        self.assertEqual(result, "Japan")
        self.assertEqual(self.page.locator("#custom").input_value(), "Japan")

    def test_legacy_text_mapping_auto_detects_native_control_types(self):
        for selector, expected in (("#count", "number"), ("#email", "email"), ("#date", "date"),
                                   ("#active", "checkbox"), ("input[name='gender']", "radio"),
                                   ("#country", "select"), ("#file", "upload"), ("#notes", "textarea")):
            with self.subTest(selector=selector):
                self.assertEqual(infer_field_type(self.page.locator(selector), "text"), expected)

    def test_uploads_a_user_supplied_file_path(self):
        scratch = os.environ.get("TMPDIR") or os.getcwd()
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".txt", dir=scratch, delete=False) as file:
            file.write("fixture")
            path = file.name
        try:
            result = apply_field_value(self.page, self.page.locator("#upload-label"), "upload", path)
            self.assertTrue(result.endswith(".txt"))
            self.assertEqual(self.page.locator("#file").evaluate("node => node.files.length"), 1)
        finally:
            os.unlink(path)

    def test_uploads_to_hidden_file_input_directly(self):
        scratch = os.environ.get("TMPDIR") or os.getcwd()
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".txt", dir=scratch, delete=False) as file:
            file.write("fixture")
            path = file.name
        try:
            result = apply_field_value(self.page, self.page.locator("#hidden-file"), "upload", path)
            self.assertTrue(result.endswith(".txt"))
            self.assertEqual(self.page.locator("#hidden-file").evaluate("node => node.files.length"), 1)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
