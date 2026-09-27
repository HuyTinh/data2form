"""Compatibility facade for automation runner imports."""

from automation_runtime import (
    AutomationStatus,
    _PersistentPlaywrightSession,
    _click_after_action,
    _get_persistent_browser_context,
    _persistent_browser_contexts,
    setup_encoding,
)
from mapping_plan_runner import (
    _apply_mapping_plan_fields,
    _click_plan_selector,
    run_mapping_plan_core,
)
from single_form_runner import run_automation_core

