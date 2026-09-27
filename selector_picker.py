import json
import logging
import os

from fastapi import HTTPException
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)


def run_selector_picker(url: str, use_session: bool, target_fields: list[dict], allow_any_target: bool = False):
    target_fields = [
        {"id": str(target["id"]), "label": str(target["label"])}
        for target in target_fields
    ]
    if not target_fields:
        target_fields = [{"id": "field-1", "label": "Trường cần chọn"}]
    target_count = len(target_fields)
    inject_script = r"""
    () => {
        const ui = document.createElement('div');
        ui.id = 'd2f-picker-ui';
        Object.assign(ui.style, {
            position: 'fixed', top: '20px', left: '50%', transform: 'translateX(-50%)',
            zIndex: '2147483647', background: 'rgba(255, 255, 255, 0.95)',
            padding: '12px 20px', borderRadius: '12px', boxShadow: '0 8px 32px rgba(0,0,0,0.2)',
            display: 'flex', gap: '15px', alignItems: 'center',
            fontFamily: '"Outfit", sans-serif', border: '1px solid #3498db',
            backdropFilter: 'blur(10px)', transition: 'all 0.3s ease'
        });
        const isNarrowViewport = window.innerWidth <= 520;
        Object.assign(ui.style, {
            top: isNarrowViewport ? '12px' : '20px',
            width: isNarrowViewport ? 'calc(100vw - 32px)' : 'auto',
            maxWidth: isNarrowViewport ? '420px' : 'none',
            boxSizing: 'border-box',
            flexDirection: isNarrowViewport ? 'column' : 'row',
            alignItems: isNarrowViewport ? 'stretch' : 'center',
            gap: isNarrowViewport ? '8px' : '15px',
            padding: isNarrowViewport ? '12px 16px' : '12px 20px'
        });

        const statusInfo = document.createElement('div');
        statusInfo.style.fontSize = '14px';
        statusInfo.style.width = isNarrowViewport ? '100%' : 'auto';
        const pickerTitle = document.createElement('strong');
        pickerTitle.style.color = '#2c3e50';
        pickerTitle.textContent = 'D2F Picker:';
        const statusLabel = document.createElement('span');
        statusLabel.id = 'picker-mode-text';
        statusLabel.style.color = '#e67e22';
        statusInfo.append(pickerTitle, document.createTextNode(' '), statusLabel);

        const targetSelect = document.createElement('select');
        targetSelect.id = 'd2f-picker-target-select';
        targetSelect.setAttribute('aria-label', 'Field đích cần ghép');
        Object.assign(targetSelect.style, {
            display: __ALLOW_ANY_TARGET__ ? 'block' : 'none',
            width: isNarrowViewport ? '100%' : '220px',
            maxWidth: '100%', boxSizing: 'border-box', padding: '8px 10px',
            border: '1px solid #d9d9d9', borderRadius: '6px', background: 'white',
            color: '#2c3e50', fontSize: '14px'
        });

        const pickBtn = document.createElement('button');
        pickBtn.innerText = '🎯 Bắt đầu chọn';
        Object.assign(pickBtn.style, {
            padding: '8px 16px', background: '#3498db', color: 'white',
            border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 'bold'
        });

        const cancelBtn = document.createElement('button');
        cancelBtn.innerText = 'Đóng';
        Object.assign(cancelBtn.style, {
            padding: '8px 16px', background: '#95a5a6', color: 'white',
            border: 'none', borderRadius: '6px', cursor: 'pointer'
        });

        const finishBtn = document.createElement('button');
        finishBtn.innerText = 'Hoàn tất (0)';
        Object.assign(finishBtn.style, {
            padding: '8px 16px', background: '#52c41a', color: 'white',
            border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 'bold'
        });
        [pickBtn, finishBtn, cancelBtn].forEach((button) => {
            button.style.width = isNarrowViewport ? '100%' : 'auto';
            button.style.boxSizing = 'border-box';
        });

        ui.appendChild(statusInfo);
        ui.appendChild(targetSelect);
        ui.appendChild(pickBtn);
        ui.appendChild(finishBtn);
        ui.appendChild(cancelBtn);
        document.body.appendChild(ui);

        const overlay = document.createElement('div');
        Object.assign(overlay.style, {
            position: 'fixed', top: '0', left: '0', width: '100vw', height: '100vh',
            zIndex: '2147483646', cursor: 'crosshair', pointerEvents: 'none',
            border: '4px solid #e67e22', boxSizing: 'border-box', display: 'none'
        });
        document.body.appendChild(overlay);

        let isPicking = false;
        const selections = [];
        const availableTargets = __TARGET_FIELDS__;
        const targetCount = __TARGET_COUNT__;
        const statusText = document.getElementById('picker-mode-text');
        const updateTargetStatus = () => {
            const selected = availableTargets.find(target => target.id === targetSelect.value);
            if (selected) {
                statusText.innerText = isPicking
                    ? `Đang chọn field: ${selected.label} (${selections.length}/${targetCount})`
                    : `Field đích: ${selected.label} (${selections.length}/${targetCount})`;
            } else {
                statusText.innerText = `Đã chọn ${selections.length}/${targetCount} ô`;
            }
            finishBtn.innerText = `Hoàn tất (${selections.length})`;
        };
        const refreshTargetOptions = () => {
            const previousTargetId = targetSelect.value;
            targetSelect.replaceChildren();
            availableTargets.forEach(target => {
                const option = document.createElement('option');
                option.value = target.id;
                option.textContent = target.label;
                targetSelect.appendChild(option);
            });
            if (availableTargets.some(target => target.id === previousTargetId)) {
                targetSelect.value = previousTargetId;
            } else if (availableTargets.length > 0) {
                targetSelect.value = availableTargets[0].id;
            }
            updateTargetStatus();
        };
        targetSelect.onchange = updateTargetStatus;
        refreshTargetOptions();
        let lastHovered = null;
        let originalOutline = '';

        const getPath = (el) => {
            if (el.id) return `#${CSS.escape(el.id)}`;
            if (el.name) return `[name="${CSS.escape(el.name)}"]`;
            if (el.className && typeof el.className === 'string') {
                const classes = el.className.trim().split(/\s+/).filter(c => c && !c.includes(':'));
                for (let cls of classes) {
                    try {
                        const selector = `.${CSS.escape(cls)}`;
                        if (document.querySelectorAll(selector).length === 1) return selector;
                    } catch(e) {}
                }
            }
            let path = el.tagName.toLowerCase();
            let parent = el.parentNode;
            if (parent && parent !== document) {
                let children = Array.from(parent.children).filter(c => c.tagName === el.tagName);
                if (children.length > 1) {
                    let index = children.indexOf(el) + 1;
                    if (el.tagName.toLowerCase() === 'tr' && parent.tagName && parent.tagName.toLowerCase() === 'tbody') {
                        path += `:nth-of-type({row})`;
                    } else {
                        path += `:nth-of-type(${index})`;
                    }
                }
                path = getPath(parent) + ' > ' + path;
            }
            return path;
        };

        const mouseMoveHandler = (e) => {
            if (!isPicking) return;
            const el = document.elementFromPoint(e.clientX, e.clientY);
            if (el && el !== overlay && !ui.contains(el) && el !== lastHovered) {
                if (lastHovered) lastHovered.style.outline = originalOutline;
                lastHovered = el;
                originalOutline = el.style.outline;
                el.style.outline = '3px solid #e74c3c';
            }
        };

        const clickHandler = (e) => {
            if (!isPicking) return;
            if (ui.contains(e.target)) return;

            try {
                e.preventDefault(); e.stopPropagation();
                let el = document.elementFromPoint(e.clientX, e.clientY);
                if (el && el !== overlay && !ui.contains(el)) {
                    const tagName = el.tagName ? el.tagName.toUpperCase() : '';
                    if (!['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON'].includes(tagName)) {
                        const innerInput = el.querySelector('input, textarea, select, button');
                        if (innerInput) el = innerInput;
                    }

                    const target = availableTargets.find(item => item.id === targetSelect.value);
                    if (!target) {
                        document.getElementById('picker-mode-text').innerText = 'Hãy chọn field đích trước.';
                        return;
                    }
                    const selector = getPath(el);
                    selections.push({ target_id: target.id, label: target.label, selector });
                    const targetIndex = availableTargets.findIndex(item => item.id === target.id);
                    if (targetIndex >= 0) availableTargets.splice(targetIndex, 1);
                    refreshTargetOptions();
                    if (selections.length >= targetCount) {
                        cleanup();
                        resolve(selections);
                    }
                }
            } catch (err) { console.error('Picker Error:', err); }
        };

        const cleanup = () => {
            if (lastHovered) lastHovered.style.outline = originalOutline;
            window.removeEventListener('mousemove', mouseMoveHandler);
            window.removeEventListener('click', clickHandler, true);
            if (document.body.contains(overlay)) document.body.removeChild(overlay);
            if (document.body.contains(ui)) document.body.removeChild(ui);
        };

        pickBtn.onclick = () => {
            isPicking = !isPicking;
            if (isPicking) {
                pickBtn.innerText = '⏸️ Đang chọn (Click để dừng)';
                pickBtn.style.background = '#e67e22';
                overlay.style.display = 'block';
                document.getElementById('picker-mode-text').style.color = '#e74c3c';
            } else {
                pickBtn.innerText = '🎯 Bắt đầu chọn';
                pickBtn.style.background = '#3498db';
                overlay.style.display = 'none';
                document.getElementById('picker-mode-text').style.color = '#e67e22';
                if (lastHovered) lastHovered.style.outline = originalOutline;
            }
            updateTargetStatus();
        };

        cancelBtn.onclick = () => {
            cleanup();
            resolve(null);
        };

        finishBtn.onclick = () => {
            cleanup();
            resolve(selections);
        };

        window.addEventListener('mousemove', mouseMoveHandler);
        window.addEventListener('click', clickHandler, true);
    });
}
"""
    inject_script = inject_script.replace("__TARGET_COUNT__", str(target_count))
    inject_script = inject_script.replace("__TARGET_FIELDS__", json.dumps(target_fields))
    inject_script = inject_script.replace("__ALLOW_ANY_TARGET__", "true" if allow_any_target else "false")

    user_data_dir = os.path.join(os.getcwd(), ".browser_session")

    with sync_playwright() as playwright:
        browser = None
        context = None
        try:
            if use_session:
                logger.info(f"Khởi động bộ chọn (Persistent Context) cho URL: {url}")
                context = playwright.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    headless=False,
                    no_viewport=True,
                )
                page = context.pages[0] if context.pages else context.new_page()
            else:
                logger.info(f"Khởi động bộ chọn (Clean Context) cho URL: {url}")
                browser = playwright.chromium.launch(headless=False)
                context = browser.new_context()
                page = context.new_page()

            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            logger.info("Đã tải xong trang. Chờ người dùng chọn phần tử...")
            selection_result = page.evaluate(inject_script)
            if isinstance(selection_result, str):
                selection_result = [selection_result]
            selections = []
            targets_by_id = {target["id"]: target for target in target_fields}
            for index, selected in enumerate(selection_result or []):
                if isinstance(selected, str):
                    target = target_fields[min(index, len(target_fields) - 1)]
                    selections.append({"target_id": target["id"], "label": target["label"], "selector": selected})
                elif isinstance(selected, dict) and selected.get("selector"):
                    target = targets_by_id.get(str(selected.get("target_id", "")))
                    if target is None:
                        raise ValueError("Picker returned an unknown target id")
                    selections.append({
                        "target_id": target["id"],
                        "label": target["label"],
                        "selector": str(selected["selector"]),
                    })
            logger.info(f"Người dùng đã chọn {len(selections)} selector.")
            return selections
        except Exception as exc:
            logger.error(f"Lỗi bộ chọn: {exc}")
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        finally:
            if context:
                context.close()
            if browser:
                browser.close()
            logger.info("Đã đóng phiên trình duyệt bộ chọn.")
