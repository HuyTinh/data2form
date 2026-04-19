/**
 * Data2Form Pro - Dashboard Logic
 * Handles real-time monitoring, pagination, and automation control.
 */

const fileInput = document.getElementById('excel-file');
const dropZone = document.getElementById('drop-zone');
const fileNameDisplay = document.getElementById('file-name');
const previewCard = document.getElementById('preview-card');
const mappingCard = document.getElementById('mapping-card');
const mappingContainer = document.getElementById('mapping-container');
const loadingOverlay = document.getElementById('loading-overlay');
const loadingText = document.getElementById('loading-text');

let uploadedFileName = '';
let currentPreviewPage = 1;
let currentPreviewPageSize = 10;
let currentSearchQuery = '';
let totalFilteredRows = 0;
let previewColumns = [];
let currentLang = localStorage.getItem('lang') || 'vi';
let currentlyViewingLogId = null;
let lastHistoryData = [];

const TRANSLATIONS = {
    vi: {
        nav_upload: "Tải file & Cấu hình",
        nav_monitoring: "Giám sát & Logs",
        nav_history: "Lịch sử thực thi",
        setup_title: "Thiết lập Tự động hóa",
        setup_desc: "Tải file Excel và ánh xạ các trường dữ liệu lên Form Web",
        upload_title: "Tải file Excel của bạn",
        upload_desc: "Kéo thả file vào đây hoặc nhấn để chọn",
        btn_reset: "Đặt lại toàn bộ",
        btn_change_file: "Chỉ đổi file",
        label_url: "URL Trang Web Đích",
        label_use_session: "Duy trì phiên đăng nhập (Persistent)",
        label_submit: "CSS Selector Nút Gửi (Submit)",
        label_trigger: "⚡ Trigger mở Popup/Modal (tùy chọn)",
        preview_title: "Xem trước",
        search_placeholder: "Lọc nhanh...",
        mapping_title: "Ánh xạ cột Excel (Mapping)",
        btn_run: "Bắt đầu Chạy Tự động",
        status_stopped: "Đang dừng",
        status_running: "Đang chạy...",
        progress_label: "Tiến độ",
        logs_title: "Live Console Logs",
        screenshots_title: "Ảnh chụp màn hình lỗi (nếu có)",
        history_time: "Thời gian",
        history_filename: "Tên file",
        history_rows: "Số dòng",
        history_status: "Trạng thái",
        history_actions: "Hành động",
        toast_upload_success: "✅ Tải file Excel thành công!",
        toast_reset_success: "Đã đặt lại trạng thái về ban đầu!",
        toast_file_cleared: "Đã xóa file. Cấu hình URL và Mapping được giữ nguyên.",
        toast_running_error: "⚠️ Không thể thực hiện khi đang chạy tự động hóa!",
        msg_analyzing: "Đang phân tích cấu trúc file Excel...",
        msg_resetting: "Đang đặt lại...",
        msg_clearing: "Đang dọn dẹp file cũ...",
        modal_title: "⚠️ Xác nhận Đặt lại",
        modal_body: "Bạn có chắc chắn muốn <strong>ĐẶT LẠI TOÀN BỘ</strong>?",
        modal_sub: "Tất cả URL, file Excel và cấu hình Mapping hiện tại sẽ bị xóa sạch và không thể khôi phục.",
        btn_cancel: "Hủy bỏ",
        btn_confirm_delete: "Xác nhận Xóa",
        history_empty: "Chưa có lịch sử thực thi",
        btn_view_logs: "👁️ Xem Logs",
        btn_download_zip: "📦 Tải Zip",
        logs_cleared: "Logs đã được xóa.",
        toast_preset_loaded: "✨ Đã nạp cấu hình cũ cho URL này",
        default_loading: "Đang xử lý...",
        logs_start: "--- Bắt đầu nhật ký ---",
        logs_empty: "Không có dữ liệu nhật ký cho lần chạy này.",
        page: "Trang",
        prev: "Trước",
        next: "Sau",
        rows_per_page: "dòng",
        monitor_title: "Giám sát Tiến độ",
        monitor_desc: "Theo dõi quá trình nhập liệu thời gian thực",
        search_logs: "Tìm trong log...",
        btn_clear_log: "Xóa log",
        status_ready: "Sẵn sàng.",
        history_title: "Lịch sử thực thi",
        history_desc: "Danh sách các lần chạy tự động hóa trước đó",
        expanded_logs: "Nhật ký chi tiết",
        search_history: "Tìm trong lịch sử...",
        btn_close: "Đóng x",
        loading: "Đang tải...",
        wait_start: "Chờ bắt đầu...",
        msg_file_deleted: "Đã xóa file cũ. Vui lòng chọn file mới."
    },
    en: {
        nav_upload: "Upload & Config",
        nav_monitoring: "Monitoring & Logs",
        nav_history: "Execution History",
        setup_title: "Automation Setup",
        setup_desc: "Upload Excel file and map data fields to Web Form",
        upload_title: "Upload your Excel file",
        upload_desc: "Drag and drop file here or click to select",
        btn_reset: "Full Reset",
        btn_change_file: "Change File Only",
        label_url: "Target Website URL",
        label_use_session: "Keep login session (Persistent)",
        label_submit: "Submit Button CSS Selector",
        label_trigger: "⚡ Open Popup/Modal Trigger (optional)",
        preview_title: "Preview",
        search_placeholder: "Quick filter...",
        mapping_title: "Excel Column Mapping",
        btn_run: "Start Automation",
        status_stopped: "Stopped",
        status_running: "Running...",
        progress_label: "Progress",
        logs_title: "Live Console Logs",
        screenshots_title: "Error Screenshots (if any)",
        history_time: "Time",
        history_filename: "Filename",
        history_rows: "Rows",
        history_status: "Status",
        history_actions: "Actions",
        toast_upload_success: "✅ Excel file uploaded successfully!",
        toast_reset_success: "System state reset to initial!",
        toast_file_cleared: "File cleared. URL and Mappings preserved.",
        toast_running_error: "⚠️ Cannot perform this action while automation is running!",
        msg_analyzing: "Analyzing Excel structure...",
        msg_resetting: "Resetting...",
        msg_clearing: "Cleaning up old file...",
        modal_title: "⚠️ Confirm Reset",
        modal_body: "Are you sure you want to <strong>RESET EVERYTHING</strong>?",
        modal_sub: "All URLs, files, and mapping configurations will be permanently cleared.",
        btn_cancel: "Cancel",
        btn_confirm_delete: "Confirm Delete",
        history_empty: "No execution history yet",
        btn_view_logs: "👁️ View Logs",
        btn_download_zip: "📦 Download Zip",
        logs_cleared: "Logs cleared.",
        toast_preset_loaded: "✨ Old configuration loaded for this URL",
        default_loading: "Processing...",
        logs_start: "--- Log started ---",
        logs_empty: "No log data for this run.",
        page: "Page",
        prev: "Prev",
        next: "Next",
        rows_per_page: "rows",
        monitor_title: "Progress Monitoring",
        monitor_desc: "Track real-time data entry process",
        search_logs: "Search in logs...",
        btn_clear_log: "Clear logs",
        status_ready: "Ready.",
        history_title: "Execution History",
        history_desc: "List of previous automation runs",
        expanded_logs: "Detailed Logs",
        search_history: "Search in history...",
        btn_close: "Close x",
        loading: "Loading...",
        wait_start: "Waiting to start...",
        msg_file_deleted: "Old file deleted. Please select a new one."
    }
};

function t(key) {
    return TRANSLATIONS[currentLang][key] || key;
}

function setLanguage(lang) {
    currentLang = lang;
    localStorage.setItem('lang', lang);
    updateUIStrings();

    document.querySelectorAll('.lang-btn').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('onclick').includes(lang));
    });
}

function updateUIStrings() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        el.innerHTML = t(key);
    });

    // Update placeholders
    const searchInput = document.getElementById('preview-search');
    if (searchInput) searchInput.placeholder = t('search_placeholder');

    const logSearchInput = document.getElementById('log-search');
    if (logSearchInput) logSearchInput.placeholder = t('search_logs');

    const histSearchInput = document.getElementById('hist-log-search');
    if (histSearchInput) histSearchInput.placeholder = t('search_history');

    // Update dynamic pagination elements
    updatePaginationUI();

    // Update select options manually (since they can't contain spans well)
    document.querySelectorAll('[data-i18n-rows]').forEach(opt => {
        const val = opt.getAttribute('data-i18n-rows');
        opt.textContent = `${val} ${t('rows_per_page')}`;
    });

    // Re-render history table if we have data
    if (lastHistoryData.length > 0) {
        displayHistory(lastHistoryData);
    }

    // Update expanded logs title if open
    const expandedTitle = document.getElementById('expanded-logs-title');
    if (expandedTitle && currentlyViewingLogId) {
        expandedTitle.innerHTML = `${t('expanded_logs')} (ID: ${currentlyViewingLogId})`;
    }

    // Update modal static parts
    const modalTitle = document.querySelector('#confirm-modal .modal-header h3');
    if (modalTitle) modalTitle.innerHTML = t('modal_title');
}

let statusInterval = null;

// --- Section Navigation ---
function showSection(sectionId) {
    document.querySelectorAll('.content-section').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

    document.getElementById(`section-${sectionId}`).classList.add('active');
    document.getElementById(`nav-${sectionId}`).classList.add('active');

    if (sectionId === 'history') {
        fetchHistory();
    }
}

// --- Event Listeners ---
dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    if (e.dataTransfer.files.length) {
        fileInput.files = e.dataTransfer.files;
        handleFileUpload();
    }
});
fileInput.addEventListener('change', handleFileUpload);

/**
 * Handle File Upload
 */
async function handleFileUpload() {
    if (!fileInput.files.length) return;

    const file = fileInput.files[0];
    fileNameDisplay.textContent = `File: ${file.name}`;

    const formData = new FormData();
    formData.append('file', file);

    showLoading(t('msg_analyzing'));
    try {
        const response = await fetch('/api/upload', { method: 'POST', body: formData });
        const data = await response.json();

        if (response.ok) {
            // --- Preserve existing mappings before re-rendering ---
            const currentMappings = {};
            document.querySelectorAll('#mapping-container .mapping-row').forEach((row, i) => {
                const input = row.querySelector(`input[id^="map-input-"]`);
                const select = row.querySelector(`select[id^="map-type-"]`);
                if (input) {
                    const col = input.getAttribute('data-col');
                    const val = input.value.trim();
                    if (val) currentMappings[col] = {
                        selector: val,
                        type: select ? select.value : 'text'
                    };
                }
            });

            uploadedFileName = data.filename;
            previewColumns = data.columns;

            renderMappingRows(data.columns, currentMappings);

            // --- Enable inputs after upload ---
            document.getElementById('target-url').disabled = false;
            document.getElementById('use-session').disabled = false;
            document.getElementById('submit-selector').disabled = false;
            document.getElementById('pick-submit-btn').disabled = false;
            document.getElementById('open-form-trigger').disabled = false;
            document.getElementById('pick-trigger-btn').disabled = false;

            // Reset Preview State
            currentPreviewPage = 1;
            currentSearchQuery = '';
            document.getElementById('preview-search').value = '';
            await fetchPreviewData();

            // --- Load Presets for this URL if already entered ---
            await handleUrlInput();

            // Show Cards
            previewCard.style.display = 'block';
            mappingCard.style.display = 'block';
            document.getElementById('reset-btn').style.display = 'block';
            document.getElementById('change-file-btn').style.display = 'block';

            showToast(t('toast_upload_success'), 'success');
        } else {
            showToast(data.detail, 'error');
        }
    } catch (err) {
        showToast('❌ Connection Error', 'error');
    }
    hideLoading();
}

async function resetAll(e) {
    if (e) {
        e.preventDefault();
        e.stopPropagation();
    }

    // Check if automation is running
    const statusResp = await fetch('/api/status');
    const statusData = await statusResp.json();
    if (statusData.is_running) {
        showToast(t('toast_running_error'), 'warning');
        return;
    }

    // Show Custom Modal
    const modal = document.getElementById('confirm-modal');
    modal.style.display = 'flex';

    // Temporary event for the confirm button
    const confirmBtn = document.getElementById('confirm-reset-btn');
    confirmBtn.onclick = async () => {
        closeConfirmModal();
        await performReset();
    };
}

function closeConfirmModal() {
    document.getElementById('confirm-modal').style.display = 'none';
}

async function performReset() {
    showLoading(t('msg_resetting'));

    if (uploadedFileName) {
        await fetch(`/api/clear-cache?filename=${encodeURIComponent(uploadedFileName)}`, { method: 'POST' });
    }

    // Reset Data State
    uploadedFileName = '';
    fileInput.value = '';
    fileNameDisplay.textContent = '';

    // Reset Config State
    document.getElementById('target-url').value = '';
    document.getElementById('submit-selector').value = '';
    document.getElementById('open-form-trigger').value = '';
    document.getElementById('use-session').checked = false;

    // Reset Mapping State
    mappingContainer.innerHTML = '';

    // Hide Cards
    previewCard.style.display = 'none';
    mappingCard.style.display = 'none';
    document.getElementById('reset-btn').style.display = 'none';
    document.getElementById('change-file-btn').style.display = 'none';

    // --- Re-lock inputs ---
    document.getElementById('target-url').disabled = true;
    document.getElementById('use-session').disabled = true;
    document.getElementById('submit-selector').disabled = true;
    document.getElementById('pick-submit-btn').disabled = true;
    document.getElementById('open-form-trigger').disabled = true;
    document.getElementById('pick-trigger-btn').disabled = true;

    hideLoading();
    showToast(t('toast_reset_success'), 'info');
}

async function changeFileOnly(e) {
    if (e) {
        e.preventDefault();
        e.stopPropagation();
    }

    // Check if automation is running
    const statusResp = await fetch('/api/status');
    const statusData = await statusResp.json();
    if (statusData.is_running) {
        showToast(t('toast_running_error'), 'warning');
        return;
    }

    showLoading(t('msg_clearing'));

    if (uploadedFileName) {
        await fetch(`/api/clear-cache?filename=${encodeURIComponent(uploadedFileName)}`, { method: 'POST' });
    }

    uploadedFileName = '';
    fileInput.value = '';
    fileNameDisplay.textContent = t('msg_file_deleted');

    // Hide Data Cards but keep Config
    previewCard.style.display = 'none';
    mappingCard.style.display = 'none';

    hideLoading();
    showToast(t('toast_file_cleared'), 'info');
}

/**
 * Preview Logic
 */
async function handlePageSizeChange() {
    currentPreviewPageSize = parseInt(document.getElementById('page-size').value);
    currentPreviewPage = 1;
    await fetchPreviewData();
}

async function fetchPreviewData() {
    try {
        const url = `/api/preview?filename=${encodeURIComponent(uploadedFileName)}&page=${currentPreviewPage}&page_size=${currentPreviewPageSize}&query=${encodeURIComponent(currentSearchQuery)}`;
        const response = await fetch(url);
        const result = await response.json();

        if (response.ok) {
            totalFilteredRows = result.total;
            renderPreviewTable(previewColumns, result.data);
            updatePaginationUI();
        }
    } catch (err) { }
}

function renderPreviewTable(columns, dataRows) {
    const thead = document.getElementById('preview-thead');
    const tbody = document.getElementById('preview-tbody');

    thead.innerHTML = `<tr>${columns.map(c => `<th>${c}</th>`).join('')}</tr>`;
    tbody.innerHTML = dataRows.map(row => `
        <tr>${columns.map(c => `<td>${row[c] || ''}</td>`).join('')}</tr>
    `).join('');
}

function updatePaginationUI() {
    const totalPages = Math.ceil(totalFilteredRows / currentPreviewPageSize) || 1;
    document.getElementById('page-info').textContent = `${t('page')} ${currentPreviewPage} / ${totalPages}`;
    document.getElementById('total-count').textContent = totalFilteredRows;
    document.getElementById('prev-btn').disabled = currentPreviewPage <= 1;
    document.getElementById('next-btn').disabled = currentPreviewPage >= totalPages;
}

function changePage(delta) {
    currentPreviewPage += delta;
    fetchPreviewData();
}

let searchTimeout;
function handleSearch() {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        currentSearchQuery = document.getElementById('preview-search').value;
        currentPreviewPage = 1;
        fetchPreviewData();
    }, 400);
}

/**
 * Mapping Logic
 */
function renderMappingRows(columns, existingMappings = {}) {
    mappingContainer.innerHTML = columns.map((col, i) => {
        let val = '';
        let type = 'text';
        if (existingMappings[col]) {
            if (typeof existingMappings[col] === 'string') {
                val = existingMappings[col];
            } else {
                val = existingMappings[col].selector || '';
                type = existingMappings[col].type || 'text';
            }
        }
        return `
        <div class="mapping-row">
            <div class="col-name"><strong>${col}</strong></div>
            <div class="selector-wrapper" style="display: flex; gap: 0.5rem; width: 100%; align-items: center;">
                <select id="map-type-${i}" data-col="${col}" class="type-select" style="padding: 0.85rem; border-radius: 8px; border: 1px solid var(--border-color); background: var(--bg-dark); color: var(--text-main); font-weight: 500; font-family: inherit; min-width: 110px;">
                    <option value="text" ${type === 'text' ? 'selected' : ''}>Text</option>
                    <option value="selection" ${type === 'selection' ? 'selected' : ''}>Selection</option>
                    <option value="click" ${type === 'click' ? 'selected' : ''}>Click</option>
                    <option value="upload" ${type === 'upload' ? 'selected' : ''}>Upload</option>
                </select>
                <input type="text" id="map-input-${i}" data-col="${col}" placeholder="CSS Selector..." value="${val}" style="flex: 1;">
                <button class="icon-btn" onclick="pickSelector('map-input-${i}')" title="Chọn selector">🎯</button>
            </div>
        </div>
    `}).join('');
}

/**
 * Selector Picker
 */
async function pickSelector(inputId) {
    const url = document.getElementById('target-url').value;
    if (!url) { showToast(t('label_url'), 'warning'); return; }

    const useSession = document.getElementById('use-session').checked;

    showLoading(t('msg_analyzing'));
    try {
        const response = await fetch('/api/pick-selector', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, use_session: useSession })
        });
        const data = await response.json();
        if (response.ok && data.selector) {
            document.getElementById(inputId).value = data.selector;
            showToast(t('toast_upload_success'), 'success');
        }
    } catch (err) { showToast(t('nav_monitoring'), 'error'); }
    hideLoading();
}

/**
 * Automation Control
 */
document.getElementById('run-btn').addEventListener('click', async () => {
    const targetUrl = document.getElementById('target-url').value;
    const submitSelector = document.getElementById('submit-selector').value;

    if (!targetUrl) { showToast(t('label_url'), 'warning'); return; }

    const mappings = {};
    document.querySelectorAll('#mapping-container .mapping-row').forEach((row, i) => {
        const input = row.querySelector(`input[id="map-input-${i}"]`);
        const select = row.querySelector(`select[id="map-type-${i}"]`);
        if (input) {
            const col = input.getAttribute('data-col');
            const val = input.value.trim();
            if (val) mappings[col] = {
                selector: val,
                type: select ? select.value : 'text'
            };
        }
    });

    try {
        const response = await fetch('/api/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                filename: uploadedFileName,
                url: targetUrl,
                submit_selector: submitSelector,
                open_form_trigger: document.getElementById('open-form-trigger').value.trim(),
                mappings: mappings,
                use_session: document.getElementById('use-session').checked
            })
        });

        if (response.ok) {
            showSection('monitoring');
            startStatusPolling();
            showToast('Bắt đầu quá trình tự động hóa...', 'info');
        } else {
            const err = await response.json();
            showToast(err.detail, 'error');
        }
    } catch (err) { showToast('Lỗi kết nối', 'error'); }
});

/**
 * Status Polling & UI Updates
 */
function startStatusPolling() {
    if (statusInterval) clearInterval(statusInterval);

    statusInterval = setInterval(async () => {
        try {
            const response = await fetch('/api/status');
            const status = await response.json();

            updateStatusUI(status);

            if (!status.is_running && status.logs.length > 0) {
                const lastLog = status.logs[status.logs.length - 1];
                if (lastLog.level === 'success' || lastLog.level === 'error' && status.current_row >= status.total_rows) {
                    clearInterval(statusInterval);
                    showToast('Tiến trình hoàn thành!', 'info');
                    fetchHistory();
                }
            }
        } catch (err) { }
    }, 1000);
}

/**
 * History Logic
 */
async function fetchHistory() {
    try {
        const response = await fetch('/api/history');
        const history = await response.json();
        displayHistory(history);
    } catch (err) { }
}

function displayHistory(history) {
    lastHistoryData = history || [];
    const tbody = document.getElementById('history-tbody');
    if (!history || history.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;">${t('history_empty')}</td></tr>`;
        return;
    }

    tbody.innerHTML = history.map((item) => {
        return `
            <tr>
                <td>${item.start_time}</td>
                <td>${item.filename}</td>
                <td>${item.total_rows}</td>
                <td><span class="badge ${item.status === 'Success' ? 'success' : 'warning'}">${item.status}</span></td>
                <td>
                    <button class="log-viewer-btn btn-small" onclick="viewHistoryLogs(${item.id})">${t('btn_view_logs')}</button>
                    <button class="btn-zip btn-small" onclick="downloadHistoryFile(${item.id})">${t('btn_download_zip')}</button>
                </td>
            </tr>
        `;
    }).join('');
}

async function viewHistoryLogs(historyId) {
    // Toggle logic: If clicking the same ID, close it
    if (currentlyViewingLogId === historyId) {
        closeExpandedLogs();
        return;
    }

    try {
        const response = await fetch(`/api/history/${historyId}/logs`);
        if (!response.ok) throw new Error("Could not load logs");

        const logs = await response.json();
        histSearcher.reset(); // Reset search state for new logs

        const container = document.getElementById('expanded-logs-container');
        const consoleLogs = document.getElementById('expanded-console');
        const title = document.getElementById('expanded-logs-title');

        currentlyViewingLogId = historyId;
        title.innerHTML = `${t('expanded_logs')} (ID: ${historyId})`;
        container.style.display = 'block';

        if (logs && Array.isArray(logs) && logs.length > 0) {
            consoleLogs.innerHTML = `<div class="log-line system">${t('logs_start')}</div>` +
                logs.map(log => {
                    const msg = typeof log === 'string' ? log : (log.msg || JSON.stringify(log));
                    const level = log.level || 'info';
                    return `<div class="log-line ${level}">${msg}</div>`;
                }).join('');
        } else {
            consoleLogs.innerHTML = `<div class="log-line warning">${t('logs_empty')}</div>`;
        }

        container.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (err) {
        showToast("❌ Lỗi: " + err.message, "error");
    }
}

function closeExpandedLogs() {
    document.getElementById('expanded-logs-container').style.display = 'none';
    currentlyViewingLogId = null;
}

function downloadHistoryFile(itemId) {
    window.open(`/api/download/${itemId}`, '_blank');
}

// --- Enhanced Log Search Engine ---
class LogSearcher {
    constructor(inputId, infoId, consoleId) {
        this.inputId = inputId;
        this.infoId = infoId;
        this.consoleId = consoleId;
        this.matches = [];
        this.currentIndex = -1;
        this.originalContents = new Map(); // Store original text to prevent double-wrapping
    }

    handleSearch() {
        const query = document.getElementById(this.inputId).value.trim().toLowerCase();
        const consoleEl = document.getElementById(this.consoleId);
        const lines = consoleEl.querySelectorAll('.log-line');

        this.matches = [];
        this.currentIndex = -1;

        lines.forEach((line, index) => {
            // Restore original text if we've modified it before
            if (!this.originalContents.has(line)) {
                this.originalContents.set(line, line.textContent);
            }
            const originalText = this.originalContents.get(line);

            line.classList.remove('highlight', 'active-highlight');
            line.innerHTML = originalText; // Reset to text only

            if (query && originalText.toLowerCase().includes(query)) {
                line.classList.add('highlight');
                this.matches.push(index);

                // Word-level highlight
                const regex = new RegExp(`(${query})`, 'gi');
                line.innerHTML = originalText.replace(regex, '<span class="match-text">$1</span>');
            }
        });

        if (this.matches.length > 0) {
            this.currentIndex = 0;
            this.highlightActiveMatch(true);
        } else {
            this.updateInfo();
        }
    }

    navSearch(delta) {
        if (this.matches.length === 0) return;
        this.currentIndex += delta;
        if (this.currentIndex < 0) this.currentIndex = this.matches.length - 1;
        if (this.currentIndex >= this.matches.length) this.currentIndex = 0;
        this.highlightActiveMatch(true);
    }

    highlightActiveMatch(scroll = false) {
        const consoleEl = document.getElementById(this.consoleId);
        const lines = consoleEl.querySelectorAll('.log-line');
        lines.forEach(l => l.classList.remove('active-highlight'));

        const targetIndex = this.matches[this.currentIndex];
        const targetLine = lines[targetIndex];
        targetLine.classList.add('active-highlight');

        if (scroll) {
            targetLine.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
        this.updateInfo();
    }

    updateInfo() {
        const info = document.getElementById(this.infoId);
        info.textContent = this.matches.length === 0 ? '0/0' : `${this.currentIndex + 1}/${this.matches.length}`;
    }

    reset() {
        this.originalContents.clear();
        this.matches = [];
        this.currentIndex = -1;
        const input = document.getElementById(this.inputId);
        if (input) input.value = '';
        this.updateInfo();
    }
}

// Instantiate searchers
const liveSearcher = new LogSearcher('log-search', 'log-search-info', 'console-logs');
const histSearcher = new LogSearcher('hist-log-search', 'hist-log-search-info', 'expanded-console');

// Bridging functions for HTML
function handleLogSearch() { liveSearcher.handleSearch(); }
function navLogSearch(delta) { liveSearcher.navSearch(delta); }
function handleHistLogSearch() { histSearcher.handleSearch(); }
function navHistLogSearch(delta) { histSearcher.navSearch(delta); }

function updateStatusUI(status) {
    const led = document.getElementById('status-led');
    const text = document.getElementById('status-text');
    const progressFill = document.getElementById('progress-fill');
    const progressPercent = document.getElementById('progress-percent');
    const progressInfo = document.getElementById('progress-info');
    const consoleLogs = document.getElementById('console-logs');

    if (status.is_running) {
        led.classList.add('active');
        text.textContent = t('status_running');
    } else {
        led.classList.remove('active');
        text.textContent = t('status_stopped');
    }

    if (status.total_rows > 0) {
        const percent = Math.round((status.current_row / status.total_rows) * 100);
        progressFill.style.width = `${percent}%`;
        progressPercent.textContent = `${percent}%`;
        progressInfo.textContent = `${t('progress_label')} ${status.current_row} / ${status.total_rows}`;
    }

    // Render Logs
    consoleLogs.innerHTML = status.logs.map(log => `
        <div class="log-line ${log.level}">${log.msg}</div>
    `).join('');
    consoleLogs.scrollTop = consoleLogs.scrollHeight;

    // Render Screenshots
    const screenContainer = document.getElementById('screenshots-container');
    screenContainer.innerHTML = status.screenshots.map(src => `
        <div class="screenshot-item" onclick="window.open('/${src}', '_blank')">
            <img src="/${src}" alt="Error screenshot">
        </div>
    `).join('');
}

function clearLogs() {
    document.getElementById('console-logs').innerHTML = `<div class="log-line system">${t('logs_cleared')}</div>`;
}

/**
 * UI Utilities
 */
function showLoading(text = t('default_loading')) {
    loadingText.textContent = text;
    loadingOverlay.style.display = 'flex';
}

function hideLoading() {
    loadingOverlay.style.display = 'none';
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('fade-out');
        setTimeout(() => toast.remove(), 500);
    }, 3000);
}

// --- Config Presets (SQLite via API) ---
async function handleUrlInput() {
    const url = document.getElementById('target-url').value.trim();
    if (!url) return;

    const response = await fetch(`/api/presets?url=${encodeURIComponent(url)}`);
    const config = await response.json();

    if (config) {
        document.getElementById('submit-selector').value = config.submit_selector || '';
        document.getElementById('open-form-trigger').value = config.open_form_trigger || '';
        if (config.use_session !== undefined) {
            document.getElementById('use-session').checked = !!config.use_session;
        }

        // Load mapping data including type
        document.querySelectorAll('#mapping-container .mapping-row').forEach((row, i) => {
            const input = row.querySelector(`input[id^="map-input-"]`);
            const select = row.querySelector(`select[id^="map-type-"]`);
            if (input) {
                const col = input.getAttribute('data-col');
                if (config.mappings && config.mappings[col]) {
                    const m = config.mappings[col];
                    if (typeof m === 'string') {
                        input.value = m;
                    } else {
                        input.value = m.selector || '';
                        if (select) select.value = m.type || 'text';
                    }
                } else {
                    input.value = '';
                    if (select) select.value = 'text';
                }
            }
        });

        showToast(t('toast_preset_loaded'), "success");
    }
}

async function saveCurrentConfig() {
    const url = document.getElementById('target-url').value.trim();
    if (!url) return;

    const mappings = {};
    document.querySelectorAll('#mapping-container .mapping-row').forEach((row, i) => {
        const input = row.querySelector(`input[id^="map-input-"]`);
        const select = row.querySelector(`select[id^="map-type-"]`);
        if (input) {
            const col = input.getAttribute('data-col');
            const val = input.value.trim();
            if (val) mappings[col] = {
                selector: val,
                type: select ? select.value : 'text'
            };
        }
    });

    const config = {
        url: url,
        submit_selector: document.getElementById('submit-selector').value.trim(),
        open_form_trigger: document.getElementById('open-form-trigger').value.trim(),
        use_session: document.getElementById('use-session').checked,
        mappings: mappings,
        saved_at: new Date().toLocaleString()
    };

    await fetch('/api/presets', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
    });
}

// Update the Run button click handler to save config
document.getElementById('run-btn').addEventListener('click', () => {
    saveCurrentConfig();
});

function showSection(sectionId) {
    document.querySelectorAll('.content-section').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

    document.getElementById(`section-${sectionId}`).classList.add('active');
    document.getElementById(`nav-${sectionId}`).classList.add('active');

    // Save current section to localStorage
    localStorage.setItem('activeSection', sectionId);

    if (sectionId === 'history') {
        fetchHistory();
    }
}

// Initial setup
document.addEventListener('DOMContentLoaded', () => {
    // Restore active language button state
    document.querySelectorAll('.lang-btn').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('onclick').includes(currentLang));
    });

    updateUIStrings();

    // Restore active section
    const savedSection = localStorage.getItem('activeSection') || 'upload';
    showSection(savedSection);

    startStatusPolling();
    fetchHistory();
});
