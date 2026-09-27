"""Generic field-type normalization and input validation for web-form automation."""

from datetime import date, datetime
import os
from typing import Any
from urllib.parse import urlsplit

SUPPORTED_FIELD_TYPES = frozenset(
    {"text", "number", "email", "textarea", "select", "checkbox", "radio", "date", "upload", "click"}
)
FIELD_TYPE_ALIASES = {"selection": "select"}
_TRUE_VALUES = {"1", "true", "yes", "y", "on", "checked", "x", "v"}
_FALSE_VALUES = {"0", "false", "no", "n", "off", "unchecked"}


def is_populated_cell_value(value: Any) -> bool:
    """Treat zero and False as data while skipping empty strings and NaN-like cells."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    try:
        return not bool(value != value)
    except (TypeError, ValueError):
        return False


def normalize_field_type(field_type: Any) -> str:
    """Normalize current and legacy mapping field types to a supported type."""
    normalized = str(field_type or "text").strip().lower()
    normalized = FIELD_TYPE_ALIASES.get(normalized, normalized)
    if normalized not in SUPPORTED_FIELD_TYPES:
        raise ValueError(f"Unsupported field type: {normalized}")
    return normalized


def parse_boolean_value(value: Any) -> bool:
    """Parse explicit checkbox values without treating arbitrary text as truthy."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    normalized = str(value).strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ValueError(f"Checkbox value is not a recognized boolean: {value}")


def infer_field_type(locator, configured_type: Any = "text") -> str:
    """Infer native control semantics for old text mappings without overriding explicit types."""
    normalized_type = normalize_field_type(configured_type)
    if normalized_type != "text":
        return normalized_type
    return locator.first.evaluate("""node => {
        const control = node.matches('input, textarea, select') ? node :
            (node.querySelector('input, textarea, select') || node);
        if (control.tagName === 'SELECT' || control.getAttribute('role') === 'combobox' ||
            control.classList.contains('ant-select-selection-search-input') ||
            control.closest('[role="combobox"], .ant-select, .MuiSelect-root')) return 'select';
        if (control.tagName === 'TEXTAREA') return 'textarea';
        if (control.type === 'checkbox' || control.getAttribute('role') === 'checkbox') return 'checkbox';
        if (control.type === 'radio' || control.getAttribute('role') === 'radio' ||
            control.closest('[role="radiogroup"]')) return 'radio';
        if (control.type === 'file') return 'upload';
        if (control.type === 'date' || control.type === 'datetime-local') return 'date';
        if (control.type === 'number') return 'number';
        if (control.type === 'email') return 'email';
        return 'text';
    }""")


def normalize_date_value(value: Any) -> str:
    """Convert supported, unambiguous date values to the HTML input[type=date] format."""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()

    normalized = str(value).strip()
    formats = (
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d.%m.%Y",
        "%Y/%m/%d",
    )
    for date_format in formats:
        try:
            return datetime.strptime(normalized, date_format).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"Expected an unambiguous date (YYYY-MM-DD or DD/MM/YYYY), received: {value}")


def _field_current_value(locator) -> str:
    try:
        value = locator.input_value().strip()
        return value or locator.inner_text().strip()
    except Exception:
        return locator.inner_text().strip()


def _find_open_option(page, control, value: str):
    control_ids = " ".join(filter(None, (control.get_attribute("aria-controls"), control.get_attribute("aria-owns"))))
    if control_ids:
        popup = page.locator(", ".join(f'[id="{control_id}"]' for control_id in control_ids.split()))
    else:
        popup = page.locator(
            ".ant-select-dropdown:visible, [role='listbox']:visible, [role='menu']:visible, "
            "[role='dialog']:visible, [data-radix-popper-content-wrapper]:visible, .dropdown-menu:visible"
        ).last

    option = popup.get_by_role("option", name=value, exact=True)
    if option.count() == 0:
        option = popup.get_by_role("menuitem", name=value, exact=True)
    if option.count() == 0:
        option = popup.get_by_text(value, exact=True)
    return option.first


def _select_custom_option(page, locator, value: str) -> None:
    locator.click()
    try:
        locator.fill(value)
    except Exception:
        try:
            search_input = locator.locator("input:visible").first
            if search_input.count():
                search_input.fill(value)
        except Exception:
            pass

    option = _find_open_option(page, locator, value)
    option.wait_for(state="visible", timeout=3000)
    option.click()


def _set_checkbox_state(locator, checked: bool) -> None:
    is_checkbox = locator.evaluate(
        "node => node.matches('input[type=checkbox], [role=checkbox]')"
    )
    if not is_checkbox:
        locator = locator.locator("input[type=checkbox], [role=checkbox]").first
    role = locator.get_attribute("role")
    if role == "checkbox":
        current = locator.get_attribute("aria-checked") == "true"
        if current != checked:
            locator.click()
        return
    current = locator.is_checked()
    if current != checked:
        if checked:
            locator.check()
        else:
            locator.uncheck()


def _set_checkbox_group(locator, value: str) -> str:
    requested = {part.strip().casefold() for part in value.split("|") if part.strip()}
    controls = locator.get_by_role("checkbox")
    if controls.count() == 0:
        controls = locator.locator("input[type=checkbox], [role=checkbox]")
    if controls.count() == 0:
        raise ValueError("No checkbox controls were found in the configured group")

    available_labels = set()
    selected_labels = []
    entries = []
    for index in range(controls.count()):
        control = controls.nth(index)
        labels = control.evaluate("""node => {
            if (node.getAttribute('role') === 'checkbox') {
                return [node.getAttribute('aria-label') || node.innerText.trim()];
            }
            return [node.getAttribute('aria-label'),
                ...Array.from(node.labels || []).map(label => label.textContent.trim()), node.value].filter(Boolean);
        }""")
        normalized_labels = {label.strip().casefold() for label in labels}
        available_labels.update(normalized_labels)
        entries.append((control, labels, normalized_labels))

    missing = requested - available_labels
    if missing:
        raise ValueError(f"Checkbox options were not found: {', '.join(sorted(missing))}")

    for control, labels, normalized_labels in entries:
        should_check = bool(normalized_labels & requested)
        _set_checkbox_state(control, should_check)
        is_checked = control.get_attribute("role") == "checkbox" and control.get_attribute("aria-checked") == "true"
        if control.get_attribute("role") != "checkbox":
            is_checked = control.is_checked()
        if is_checked:
            selected_labels.append(next((label for label in labels if label.strip().casefold() in requested), labels[0]))
    return " | ".join(selected_labels)


def _select_radio_option(page, locator, value: str) -> None:
    is_direct_radio = locator.evaluate("node => node.matches('input[type=radio], [role=radio]')")
    if is_direct_radio:
        current_values = [locator.get_attribute("value"), locator.get_attribute("aria-label"), locator.inner_text().strip()]
        if locator.get_attribute("role") == "radio" and locator.get_attribute("aria-labelledby"):
            current_values.extend(locator.evaluate(
                "node => (node.getAttribute('aria-labelledby') || '').split(/\\s+/).map(id => document.getElementById(id)?.textContent.trim())"
            ))
        else:
            current_values.extend(locator.evaluate("node => Array.from(node.labels || []).map(label => label.textContent.trim())"))
        if value in current_values:
            if not locator.is_checked():
                if locator.get_attribute("role") == "radio":
                    locator.click()
                else:
                    locator.check()
            return

        group = locator.locator("xpath=ancestor::fieldset[1]")
        if group.count() == 0:
            group = locator.locator("xpath=ancestor::*[@role='radiogroup'][1]")
        if group.count() == 0:
            group_name = locator.get_attribute("name")
            if not group_name:
                raise ValueError(f"Radio option '{value}' was not found in the configured group")
            candidate = page.get_by_label(value, exact=True).first
            if candidate.count() and candidate.get_attribute("name") == group_name:
                if not candidate.is_checked():
                    candidate.check()
                return
            raise ValueError(f"Radio option '{value}' was not found in the configured group")
        locator = group

    option = locator.get_by_label(value, exact=True)
    if option.count() == 0:
        option = locator.get_by_role("radio", name=value, exact=True)
    if option.count() == 0:
        option = locator.get_by_text(value, exact=True)
    if option.count() == 0:
        raise ValueError(f"Radio option '{value}' was not found in the configured group")
    if option.evaluate("node => node.matches('input[type=radio]')"):
        option.check()
        return
    option.first.click()


def apply_field_value(page, locator, field_type: Any, value: Any, multiple: bool = False) -> str:
    """Apply one spreadsheet value using generic native/custom web-form control semantics."""
    normalized_type = normalize_field_type(field_type)
    string_value = str(value).strip()

    if normalized_type in {"text", "number", "email", "textarea"}:
        locator.fill(string_value)
        actual = _field_current_value(locator)
        if actual != string_value:
            raise RuntimeError(f"Field value did not persist: expected '{string_value}', got '{actual}'")
        return actual

    if normalized_type == "date":
        date_value = normalize_date_value(value)
        locator.fill(date_value)
        actual = _field_current_value(locator)
        if actual != date_value:
            raise RuntimeError(f"Date value did not persist: expected '{date_value}', got '{actual}'")
        return actual

    if normalized_type == "checkbox":
        is_direct_checkbox = locator.evaluate("node => node.matches('input[type=checkbox], [role=checkbox]')")
        if multiple and not is_direct_checkbox:
            return _set_checkbox_group(locator, string_value)
        checked = parse_boolean_value(value)
        _set_checkbox_state(locator, checked)
        actual = locator.is_checked() if locator.get_attribute("role") != "checkbox" else locator.get_attribute("aria-checked") == "true"
        if actual != checked:
            raise RuntimeError(f"Checkbox state did not persist: expected {checked}, got {actual}")
        return str(actual).lower()

    if normalized_type == "radio":
        _select_radio_option(page, locator, string_value)
        return string_value

    if normalized_type == "select":
        is_native = locator.evaluate("node => node.tagName === 'SELECT'")
        values = [part.strip() for part in string_value.split("|")] if multiple else [string_value]
        if is_native:
            try:
                locator.select_option(label=values if multiple else values[0])
            except Exception:
                locator.select_option(value=values if multiple else values[0])
            selected = locator.evaluate("node => Array.from(node.selectedOptions).map(option => ({label: option.label, value: option.value}))")
            missing = [expected for expected in values if not any(
                expected in (option["label"], option["value"]) for option in selected
            )]
            if len(selected) != len(values) or missing:
                raise RuntimeError(f"Select value did not persist: expected {values}, got {selected}")
            return " | ".join(option["label"] for option in selected)

        for option_value in values:
            _select_custom_option(page, locator, option_value)
        actual = _field_current_value(locator)
        if any(option_value not in actual for option_value in values):
            raise RuntimeError(f"Custom select value did not persist: expected {values}, got '{actual}'")
        return actual

    if normalized_type == "upload":
        file_path = os.path.abspath(os.path.expanduser(string_value))
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"Upload file does not exist: {string_value}")
        is_file_input = locator.evaluate("node => node.matches('input[type=file]')")
        file_input = locator if is_file_input else locator.locator("input[type=file]").first
        file_input.set_input_files(file_path)
        count = file_input.evaluate("node => node.files ? node.files.length : 0")
        if count < 1:
            raise RuntimeError("Browser did not attach the selected file")
        return os.path.basename(file_path)

    if normalized_type == "click":
        locator.click()
        return "clicked"

    raise ValueError(f"Unsupported field type: {normalized_type}")


def validate_mappings(mappings: dict, columns: list[str]) -> list[str]:
    """Return preflight configuration errors while retaining legacy selector mappings."""
    errors = []
    if not mappings:
        return ["At least one field mapping is required"]
    column_names = set(columns)
    for name, mapping in (mappings or {}).items():
        if isinstance(mapping, dict):
            selector = str(mapping.get("selector") or "").strip()
            try:
                field_type = normalize_field_type(mapping.get("type", "text"))
            except ValueError as exc:
                errors.append(f"{name}: {exc}")
                continue
            source_column = str(mapping.get("column") or name).strip()
        else:
            selector = str(mapping or "").strip()
            field_type = "text"
            source_column = str(name).strip()

        if not selector:
            errors.append(f"{name}: selector is required")
        if field_type != "click" and source_column not in column_names:
            errors.append(f"{name}: Excel column '{source_column}' was not found")
    return errors


def validate_target_url(url: str) -> list[str]:
    parsed = urlsplit(str(url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return ["Target URL must be an absolute HTTP or HTTPS URL"]
    return []
