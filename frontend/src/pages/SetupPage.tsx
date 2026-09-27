import React, { useState, useEffect, useRef } from 'react';
import {
  Row,
  Col,
  Card,
  Upload,
  Input,
  Checkbox,
  Button,
  Table,
  Select,
  Tabs,
  Space,
  Typography,
  message,
  Modal,
  Tag,
  Tooltip,
  Alert,
  Divider,
  Grid,
} from 'antd';
import {
  InboxOutlined,
  AimOutlined,
  PlusOutlined,
  DeleteOutlined,
  SaveOutlined,
  RocketOutlined,
  FileExcelOutlined,
  ReloadOutlined,
  SearchOutlined,
  TableOutlined,
  InfoCircleOutlined,
} from '@ant-design/icons';
import type { UploadProps } from 'antd';
import { HybridMappingPlanEditor } from '../components/HybridMappingPlanEditor';
import {
  uploadExcelFile,
  getExcelPreview,
  getPreset,
  savePreset,
  pickSelector,
  pickSelectorsForTargets,
  runAutomation,
  clearCache,
} from '../services/api';
import type { MappingItem, MappingPlanDraft, PickerSelection, PickerTarget, UploadResponse } from '../types';
import { translations, type Language } from '../i18n';
import { createMappingPlanDraft, draftToMappingPlan, mappingPlanToDraft, validateMappingPlanDraft } from '../utils/mappingPlan';

const { Text } = Typography;

interface SetupPageProps {
  lang: Language;
  onNavigateToMonitoring: () => void;
  onAutomationStarted: () => void;
}

export const SetupPage: React.FC<SetupPageProps> = ({
  lang,
  onNavigateToMonitoring,
  onAutomationStarted,
}) => {
  const t = translations[lang];
  const screens = Grid.useBreakpoint();
  const isMobile = !screens.md;

  // Excel state
  const [uploadedData, setUploadedData] = useState<UploadResponse | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  // Form Config state
  const [targetUrl, setTargetUrl] = useState('');
  const [useSession, setUseSession] = useState(false);
  const [submitSelector, setSubmitSelector] = useState('');
  const [openFormTrigger, setOpenFormTrigger] = useState('');
  const [isPickingSubmit, setIsPickingSubmit] = useState(false);
  const [isPickingTrigger, setIsPickingTrigger] = useState(false);
  const [isPickingFieldId, setIsPickingFieldId] = useState<string | null>(null);
  const [isPickingAfterFieldId, setIsPickingAfterFieldId] = useState<string | null>(null);
  const [isPickingBatch, setIsPickingBatch] = useState(false);

  // Mapping state
  const [mappingItems, setMappingItems] = useState<MappingItem[]>([]);

  // Preview Table state
  const [previewRows, setPreviewRows] = useState<Record<string, any>[]>([]);
  const [previewTotal, setPreviewTotal] = useState(0);
  const [previewPage, setPreviewPage] = useState(1);
  const [previewPageSize, setPreviewPageSize] = useState(10);
  const [previewQuery, setPreviewQuery] = useState('');
  const [previewSheetName, setPreviewSheetName] = useState('');
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);

  // Loading indicator for running automation
  const [isStarting, setIsStarting] = useState(false);

  // Table Mode state
  const [tableMode, setTableMode] = useState(false);
  const [hybridMode, setHybridMode] = useState(false);
  const [mappingPlanDraft, setMappingPlanDraft] = useState<MappingPlanDraft>(createMappingPlanDraft());

  // Debounce ref for URL preset fetch
  const urlDebounceTimer = useRef<any>(null);


  // Handle URL change & auto load preset
  const handleUrlChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const url = e.target.value.trim();
    setTargetUrl(url);

    if (urlDebounceTimer.current) {
      clearTimeout(urlDebounceTimer.current);
    }

    if (!url) return;

    urlDebounceTimer.current = setTimeout(async () => {
      try {
        const preset = await getPreset(url);
        if (preset) {
          if (preset.submit_selector) setSubmitSelector(preset.submit_selector);
          if (preset.use_session !== undefined) setUseSession(Boolean(preset.use_session));
          if (preset.open_form_trigger !== undefined)
            setOpenFormTrigger(preset.open_form_trigger || '');

          if (preset.mapping_plan) {
            setHybridMode(true);
            setTableMode(false);
            setMappingPlanDraft(mappingPlanToDraft(preset.mapping_plan, uploadedData?.sheets || []));
          } else {
            setHybridMode(false);
          }

          if (preset.mappings && typeof preset.mappings === 'object') {
            const loadedItems: MappingItem[] = Object.entries(preset.mappings).map(
              ([key, val], idx) => {
                let selector = '';
                let type: NonNullable<MappingItem['type']> = 'text';
                let column = '';

                if (typeof val === 'string') {
                  const isKeySelector =
                    key.startsWith('#') ||
                    key.startsWith('.') ||
                    key.startsWith('[') ||
                    key.includes('>') ||
                    key.includes(':nth-');
                  column = isKeySelector ? val : key;
                  selector = isKeySelector ? key : val;
                } else if (val && typeof val === 'object') {
                  selector = (val as any).selector || '';
                  const savedType = (val as any).type || 'text';
                  type = savedType === 'selection' ? 'select' : savedType;
                  column = key;
                }

                return {
                  id: `preset-${Date.now()}-${idx}`,
                  field_name: column || `Trường ${idx + 1}`,
                  selector,
                  column,
                  type,
                  after_selector: (val && typeof val === 'object') ? ((val as any).after_selector || '') : '',
                  multiple: (val && typeof val === 'object') ? Boolean((val as any).multiple) : false,
                };
              }
            );
            if (loadedItems.length > 0) {
              setMappingItems(loadedItems);
            }
          }
          message.success(t.preset_loaded_notify);
        }
      } catch (err) {
        console.error('Error loading preset:', err);
      }
    }, 600);
  };

  // Upload props for Upload.Dragger
  const uploadProps: UploadProps = {
    name: 'file',
    multiple: false,
    showUploadList: false,
    customRequest: async (options) => {
      const file = options.file as File;
      try {
        setIsUploading(true);
        const res = await uploadExcelFile(file);
        setUploadedData(res);
        const firstSheet = res.sheets?.[0];
        setPreviewSheetName(firstSheet?.name || '');
        setMappingPlanDraft((current) => hybridMode && current.parent_sheet_name
          ? current
          : createMappingPlanDraft(res.sheets || []));
        message.success(`${t.uploaded_file}: ${res.filename} (${res.total_rows} ${t.total_records})`);

        // Auto init mapping items if empty
        if (mappingItems.length === 0 && res.columns.length > 0) {
          const initialItems: MappingItem[] = res.columns.slice(0, 5).map((col, idx) => ({
            id: `map-${Date.now()}-${idx}`,
            field_name: col,
            selector: '',
            column: col,
          }));
          setMappingItems(initialItems);
        }


      } catch (err: any) {
        message.error(err.response?.data?.detail || 'Lỗi khi tải file Excel');
      } finally {
        setIsUploading(false);
      }
    },
  };

  // Fetch preview data
  const fetchPreviewData = async (
    filename: string,
    page: number,
    pageSize: number,
    query: string,
    sheetName?: string
  ) => {
    if (!filename) return;
    try {
      setIsPreviewLoading(true);
      const res = await getExcelPreview(filename, page, pageSize, query, sheetName || undefined);
      setPreviewRows(res.data);
      setPreviewTotal(res.total);
    } catch (err) {
      console.error('Error fetching preview:', err);
    } finally {
      setIsPreviewLoading(false);
    }
  };

  // Effect to re-fetch preview when page or query changes
  useEffect(() => {
    if (uploadedData?.filename) {
      fetchPreviewData(uploadedData.filename, previewPage, previewPageSize, previewQuery, previewSheetName || undefined);
    }
  }, [uploadedData?.filename, previewPage, previewPageSize, previewQuery, previewSheetName]);

  // Reset entire form
  const handleResetAll = () => {
    Modal.confirm({
      title: t.confirm_reset_title,
      content: t.confirm_reset_content,
      okText: 'Xác nhận xóa',
      okType: 'danger',
      cancelText: 'Hủy',
      onOk: async () => {
        if (uploadedData?.filename) {
          await clearCache(uploadedData.filename);
        }
        setUploadedData(null);
        setTargetUrl('');
        setSubmitSelector('');
        setOpenFormTrigger('');
        setUseSession(false);
        setMappingItems([]);
        setMappingPlanDraft(createMappingPlanDraft());
        setHybridMode(false);
        setTableMode(false);
        setPreviewSheetName('');
        setPreviewRows([]);
        setPreviewTotal(0);
        message.info('Đã đặt lại toàn bộ trạng thái');
      },
    });
  };

  // Reset file only
  const handleChangeFileOnly = async () => {
    if (uploadedData?.filename) {
      await clearCache(uploadedData.filename);
    }
    setUploadedData(null);
    setPreviewSheetName('');
    setMappingPlanDraft(createMappingPlanDraft());
    setHybridMode(false);
    setPreviewRows([]);
    setPreviewTotal(0);
    message.info('Đã gỡ file Excel. Bạn có thể chọn file mới.');
  };

  // Pick selector handlers
  const handlePickSubmitSelector = async () => {
    if (!targetUrl) {
      message.warning('Vui lòng nhập URL trang web trước khi chọn phần tử!');
      return;
    }
    try {
      setIsPickingSubmit(true);
      message.loading({ content: t.picking_loading, key: 'picking' });
      const selector = await pickSelector(targetUrl, useSession);
      if (selector) {
        setSubmitSelector(selector);
        message.success({ content: `Đã chọn: ${selector}`, key: 'picking' });
      } else {
        message.info({ content: 'Đã hủy thao tác chọn', key: 'picking' });
      }
    } catch (err: any) {
      message.error({ content: err.response?.data?.detail || 'Lỗi khi mở bộ chọn', key: 'picking' });
    } finally {
      setIsPickingSubmit(false);
    }
  };

  const handlePickTriggerSelector = async () => {
    if (!targetUrl) {
      message.warning('Vui lòng nhập URL trang web trước khi chọn phần tử!');
      return;
    }
    try {
      setIsPickingTrigger(true);
      message.loading({ content: t.picking_loading, key: 'picking' });
      const selector = await pickSelector(targetUrl, useSession);
      if (selector) {
        setOpenFormTrigger(selector);
        message.success({ content: `Đã chọn: ${selector}`, key: 'picking' });
      } else {
        message.info({ content: 'Đã hủy thao tác chọn', key: 'picking' });
      }
    } catch (err: any) {
      message.error({ content: err.response?.data?.detail || 'Lỗi khi mở bộ chọn', key: 'picking' });
    } finally {
      setIsPickingTrigger(false);
    }
  };

  const handlePickAfterSelector = async (id: string) => {
    if (!targetUrl) {
      message.warning('Vui lòng nhập URL trang web trước khi chọn phần tử!');
      return;
    }
    try {
      setIsPickingAfterFieldId(id);
      message.loading({ content: t.picking_loading, key: 'picking' });
      const selector = await pickSelector(targetUrl, useSession);
      if (selector) {
        let finalSelector = selector;
        if (tableMode) {
          finalSelector = selector.replace(/(tr(?::[a-z0-9_-]+)*):(nth-child|nth-of-type)\(\d+\)/gi, '$1:$2({row})');
        }
        setMappingItems((prev) =>
          prev.map((item) => (item.id === id ? { ...item, after_selector: finalSelector } : item))
        );
        message.success({ content: `Đã chọn after: ${finalSelector}`, key: 'picking' });
      } else {
        message.info({ content: 'Đã hủy thao tác chọn', key: 'picking' });
      }
    } catch (err: any) {
      message.error({ content: err.response?.data?.detail || 'Lỗi khi mở bộ chọn', key: 'picking' });
    } finally {
      setIsPickingAfterFieldId(null);
    }
  };

  const handlePickFieldSelector = async (id: string) => {
    if (!targetUrl) {
      message.warning('Vui lòng nhập URL trang web trước khi chọn phần tử!');
      return;
    }
    try {
      setIsPickingFieldId(id);
      message.loading({ content: t.picking_loading, key: 'picking' });
      const selector = await pickSelector(targetUrl, useSession);
      if (selector) {
        let finalSelector = selector;
        if (tableMode) {
          finalSelector = selector.replace(/(tr(?::[a-z0-9_-]+)*):(nth-child|nth-of-type)\(\d+\)/gi, '$1:$2({row})');
        }
        setMappingItems((prev) =>
          prev.map((item) => (item.id === id ? { ...item, selector: finalSelector } : item))
        );
        message.success({ content: `Đã chọn: ${finalSelector}`, key: 'picking' });
      } else {
        message.info({ content: 'Đã hủy thao tác chọn', key: 'picking' });
      }
    } catch (err: any) {
      message.error({ content: err.response?.data?.detail || 'Lỗi khi mở bộ chọn', key: 'picking' });
    } finally {
      setIsPickingFieldId(null);
    }
  };

  const handlePickRemainingFieldSelectors = async () => {
    if (!targetUrl) {
      message.warning('Vui lòng nhập URL trang web trước khi chọn phần tử!');
      return;
    }
    const targetItems = mappingItems.filter((item) => !item.selector.trim());
    if (targetItems.length === 0) {
      message.info('Tất cả các trường đã có selector.');
      return;
    }
    const targetIds = targetItems.map((item) => item.id);
    try {
      setIsPickingBatch(true);
      message.loading({ content: t.picking_all_fields, key: 'picking' });
      const targets = targetItems.map((item) => ({
        id: item.id,
        label: item.field_name || 'Trường chưa đặt tên',
      }));
      const selections = await pickSelectorsForTargets(targetUrl, useSession, targets);
      const selectedCount = Math.min(selections.length, targetIds.length);
      const selectorById = new Map(selections.map((selection) => [
        selection.target_id,
        toRowScopedSelector(selection.selector, tableMode),
      ]));
      setMappingItems((prev) => prev.map((item) => {
        const selector = selectorById.get(item.id);
        return selector ? { ...item, selector } : item;
      }));
      if (selectedCount > 0) {
        message.success({ content: `Đã chọn ${selectedCount}/${targetIds.length} ô.`, key: 'picking' });
      } else {
        message.info({ content: 'Đã hủy thao tác chọn', key: 'picking' });
      }
    } catch (err: any) {
      message.error({ content: err.response?.data?.detail || 'Lỗi khi mở bộ chọn', key: 'picking' });
    } finally {
      setIsPickingBatch(false);
    }
  };

  const toRowScopedSelector = (selector: string, rowScoped: boolean) => rowScoped
    ? selector.replace(/(tr(?::[a-z0-9_-]+)*):(nth-child|nth-of-type)\(\d+\)/gi, '$1:$2({row})')
    : selector;

  const handlePickPlanSelector = async (label: string, rowScoped: boolean): Promise<string | null> => {
    if (!targetUrl) {
      message.warning('Vui lòng nhập URL trang web trước khi chọn phần tử!');
      return null;
    }
    try {
      const selector = await pickSelector(targetUrl, useSession);
      return selector ? toRowScopedSelector(selector, rowScoped) : null;
    } catch (err: any) {
      message.error(err.response?.data?.detail || `Không chọn được selector cho ${label}`);
      return null;
    }
  };

  const handlePickPlanSelectors = async (targets: PickerTarget[], rowScoped: boolean): Promise<PickerSelection[]> => {
    if (!targetUrl) {
      message.warning('Vui lòng nhập URL trang web trước khi chọn phần tử!');
      return [];
    }
    try {
      setIsPickingBatch(true);
      const selections = await pickSelectorsForTargets(targetUrl, useSession, targets);
      return selections.map((selection) => ({
        ...selection,
        selector: toRowScopedSelector(selection.selector, rowScoped),
      }));
    } catch (err: any) {
      message.error(err.response?.data?.detail || 'Lỗi khi mở bộ chọn');
      return [];
    } finally {
      setIsPickingBatch(false);
    }
  };

  // Mapping Item row manipulation
  const handleAddMappingRow = () => {
    const newItem: MappingItem = {
      id: `map-${Date.now()}`,
      field_name: `Trường mới ${mappingItems.length + 1}`,
      selector: '',
      column: uploadedData?.columns?.[0] || '',
      type: 'text',
    };
    setMappingItems([...mappingItems, newItem]);
  };

  const handleRemoveMappingRow = (id: string) => {
    setMappingItems(mappingItems.filter((item) => item.id !== id));
  };

  function handleUpdateMappingRow<K extends keyof MappingItem>(id: string, key: K, val: MappingItem[K]) {
    setMappingItems((prev) =>
      prev.map((item) => (item.id === id ? { ...item, [key]: val } : item))
    );
  }

  // Save Preset
  const handleSavePreset = async () => {
    if (!targetUrl) {
      message.warning('Vui lòng nhập URL!');
      return;
    }
    const mappingsDict: Record<string, any> = {};
    mappingItems.forEach((item) => {
      const colKey = item.column.trim() || (item.type === 'click' ? item.field_name.trim() : '');
      if (item.selector.trim() && colKey) {
        mappingsDict[colKey] = {
          selector: item.selector.trim(),
          type: item.type || 'text',
          ...(item.multiple ? { multiple: true } : {}),
          ...(item.after_selector?.trim() ? { after_selector: item.after_selector.trim() } : {}),
        };
      }
    });

    try {
      await savePreset({
        url: targetUrl,
        submit_selector: submitSelector,
        use_session: useSession,
        mappings: mappingsDict,
        mapping_plan: hybridMode ? draftToMappingPlan(mappingPlanDraft, openFormTrigger, submitSelector) : null,
        open_form_trigger: openFormTrigger,
        saved_at: new Date().toISOString(),
      });
      message.success(t.preset_saved_notify);
    } catch {
      message.error('Lỗi khi lưu preset!');
    }
  };

  // Validation: submit_selector optional in table_mode
  const handleStartAutomation = async () => {
    if (!uploadedData?.filename) {
      message.warning('Vui lòng tải file Excel lên trước!');
      return;
    }
    if (!targetUrl) {
      message.warning('Vui lòng nhập URL trang web đích!');
      return;
    }
    if (activeMappingIssues.length > 0) {
      message.warning(activeMappingIssues[0]);
      return;
    }

    const mappingsDict: Record<string, any> = {};
    mappingItems.forEach((item) => {
      const colKey = item.column.trim() || (item.type === 'click' ? item.field_name.trim() : '');
      if (item.selector.trim() && colKey) {
        mappingsDict[colKey] = {
          selector: item.selector.trim(),
          type: item.type || 'text',
          ...(item.multiple ? { multiple: true } : {}),
          ...(item.after_selector?.trim() ? { after_selector: item.after_selector.trim() } : {}),
        };
      }
    });

    if (!hybridMode && Object.keys(mappingsDict).length === 0) {
      message.warning('Vui lòng cấu hình ít nhất 1 trường ánh xạ hợp lệ (có Selector và Cột Excel)!');
      return;
    }

    try {
      setIsStarting(true);
      await runAutomation({
        filename: uploadedData.filename,
        url: targetUrl,
        submit_selector: submitSelector,
        open_form_trigger: openFormTrigger,
        mappings: mappingsDict,
        ...(hybridMode ? { mapping_plan: draftToMappingPlan(mappingPlanDraft, openFormTrigger, submitSelector) } : {}),
        use_session: useSession,
        table_mode: tableMode,
      });

      // Also save preset silently for convenience
      await handleSavePreset();

      message.success('Đã khởi chạy luồng tự động hóa thành công!');
      onAutomationStarted();
      onNavigateToMonitoring();
    } catch (err: any) {
      message.error(err.response?.data?.detail || 'Không thể bắt đầu tự động hóa');
    } finally {
      setIsStarting(false);
    }
  };

  // Mapping Table Columns
  const mappingColumns = [
    {
      title: t.col_field_name,
      dataIndex: 'field_name',
      key: 'field_name',
      width: '14%',
      render: (text: string, record: MappingItem) => (
        <Input
          value={text}
          onChange={(e) => handleUpdateMappingRow(record.id, 'field_name', e.target.value)}
          placeholder="Tên trường..."
        />
      ),
    },
    {
      title: t.col_type,
      dataIndex: 'type',
      key: 'type',
      width: '14%',
      render: (val: string, record: MappingItem) => (
        <Space direction="vertical" size={2} style={{ width: '100%' }}>
          <Select
            value={val || 'text'}
            style={{ width: '100%' }}
            popupMatchSelectWidth={220}
            onChange={(newVal) => handleUpdateMappingRow(record.id, 'type', newVal as NonNullable<MappingItem['type']>)}
          >
            <Select.Option value="text">Text</Select.Option>
            <Select.Option value="number">Number</Select.Option>
            <Select.Option value="email">Email</Select.Option>
            <Select.Option value="textarea">Textarea</Select.Option>
            <Select.Option value="select">Select / Dropdown</Select.Option>
            <Select.Option value="checkbox">Checkbox</Select.Option>
            <Select.Option value="radio">Radio group</Select.Option>
            <Select.Option value="date">Date</Select.Option>
            <Select.Option value="upload">File upload</Select.Option>
            <Select.Option value="click">Click action</Select.Option>
          </Select>
          {(val === 'select' || val === 'checkbox') && (
            <Tooltip title={t.multiple_values_help}>
              <Checkbox
                checked={Boolean(record.multiple)}
                onChange={(event) => handleUpdateMappingRow(record.id, 'multiple', event.target.checked)}
              >
                {t.multiple_values} <InfoCircleOutlined />
              </Checkbox>
            </Tooltip>
          )}
        </Space>
      ),
    },
    {
      title: t.col_selector,
      dataIndex: 'selector',
      key: 'selector',
      width: '26%',
      render: (text: string, record: MappingItem) => (
        <Space style={{ width: '100%' }}>
          <Input
            value={text}
            onChange={(e) => handleUpdateMappingRow(record.id, 'selector', e.target.value)}
            placeholder={tableMode ? "tr:nth-child({row}) input" : "input#email, [name='phone']"}
            style={{ fontFamily: 'monospace' }}
          />
          <Tooltip title="Chọn phần tử trực tiếp từ trình duyệt">
            <Button
              type="primary"
              icon={<AimOutlined />}
              loading={isPickingFieldId === record.id}
              onClick={() => handlePickFieldSelector(record.id)}
            />
          </Tooltip>
        </Space>
      ),
    },
    {
      title: t.col_excel_column,
      dataIndex: 'column',
      key: 'column',
      width: '22%',
      render: (val: string, record: MappingItem) => (
        <Select
          value={val || undefined}
          placeholder={record.type === 'click' ? '-- Không cần cột (Tự động click) --' : t.select_column_placeholder}
          style={{ width: '100%' }}
          allowClear
          onChange={(newVal) => handleUpdateMappingRow(record.id, 'column', newVal || '')}
        >
          {record.type === 'click' && (
            <Select.Option value="__click__">
              <span style={{ color: '#1677ff' }}>-- Luôn click mỗi hàng --</span>
            </Select.Option>
          )}
          {uploadedData?.columns.map((col) => (
            <Select.Option key={col} value={col}>
              {col}
            </Select.Option>
          ))}
        </Select>
      ),
    },
    {
      title: <Tooltip title="Selector sẽ được click ngay sau khi field này được điền xong (VD: nút Lưu cùng hàng)">Sau khi xong <InfoCircleOutlined /></Tooltip>,
      key: 'after_selector',
      width: '18%',
      render: (_: any, record: MappingItem) => (
        <Space style={{ width: '100%' }}>
          <Input
            value={record.after_selector || ''}
            onChange={(e) => handleUpdateMappingRow(record.id, 'after_selector' as keyof MappingItem, e.target.value)}
            placeholder={tableMode ? 'tr:nth-of-type({row}) button.save' : 'button#save'}
            style={{ fontFamily: 'monospace', fontSize: 11 }}
            allowClear
          />
          <Tooltip title="Chọn nút click theo sau từ trình duyệt">
            <Button
              icon={<AimOutlined />}
              size="small"
              loading={isPickingAfterFieldId === record.id}
              onClick={() => handlePickAfterSelector(record.id)}
            />
          </Tooltip>
        </Space>
      ),
    },
    {
      title: t.col_actions,
      key: 'actions',
      width: '6%',
      align: 'center' as const,
      render: (_: any, record: MappingItem) => (
        <Button
          type="text"
          danger
          icon={<DeleteOutlined />}
          onClick={() => handleRemoveMappingRow(record.id)}
        />
      ),
    },
  ].filter((col) => {
    // Only show "Sau khi xong" column in table mode
    if ((col as any).key === 'after_selector' && !tableMode) return false;
    return true;
  });

  // Dynamic Preview Table Columns
  const previewColumns = uploadedData?.sheets?.find((sheet) => sheet.name === previewSheetName)?.columns || uploadedData?.columns || [];
  const previewTableColumns = previewColumns.map((col) => ({
    title: col,
    dataIndex: col,
    key: col,
    ellipsis: true,
  }));

  const mappingIssues = mappingItems.flatMap((item) => {
    const issues: string[] = [];
    if (!item.field_name.trim()) issues.push(t.config_missing_field_name);
    if (!item.selector.trim()) issues.push(`${item.field_name || 'Field'}: ${t.config_missing_selector}`);
    if (item.type !== 'click' && !item.column.trim()) issues.push(`${item.field_name || 'Field'}: ${t.config_missing_column}`);
    if (item.column && item.column !== '__click__' && uploadedData && !uploadedData.columns.includes(item.column)) {
      issues.push(`${item.field_name || 'Field'}: ${t.config_unknown_column.replace('{column}', item.column)}`);
    }
    return issues;
  });
  if (targetUrl) {
    try {
      const parsedUrl = new URL(targetUrl);
      if (!['http:', 'https:'].includes(parsedUrl.protocol)) mappingIssues.push(t.config_http_only);
    } catch {
      mappingIssues.push(t.config_invalid_url);
    }
  }
  if (!uploadedData) mappingIssues.push(t.config_missing_file);
  if (!targetUrl) mappingIssues.push(t.config_missing_url);
  if (mappingItems.length === 0) mappingIssues.push(t.config_no_mappings);
  if (!tableMode && !submitSelector.trim()) mappingIssues.push(t.config_missing_submit);

  const hybridMappingIssues: string[] = [];
  if (!uploadedData) hybridMappingIssues.push(t.config_missing_file);
  if (!targetUrl) hybridMappingIssues.push(t.config_missing_url);
  else {
    try {
      const parsedUrl = new URL(targetUrl);
      if (!['http:', 'https:'].includes(parsedUrl.protocol)) hybridMappingIssues.push(t.config_http_only);
    } catch {
      hybridMappingIssues.push(t.config_invalid_url);
    }
  }
  hybridMappingIssues.push(...validateMappingPlanDraft(mappingPlanDraft, uploadedData?.sheets || [], submitSelector));
  const activeMappingIssues = hybridMode ? hybridMappingIssues : mappingIssues;

  return (
    <Row gutter={[20, 20]}>
      {/* LEFT COLUMN: Upload & Configuration Form (Split-View Left) */}
      <Col xs={24} lg={10} xl={9}>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {/* 1. Upload Excel Card */}
          <Card
            title={
              <Space>
                <FileExcelOutlined style={{ color: '#52c41a' }} />
                <span>{t.step_excel_title}</span>
              </Space>
            }
            extra={
              uploadedData && (
                <Tag color="success">
                  {uploadedData.total_rows} {t.total_records}
                </Tag>
              )
            }
            bordered={false}
          >
            {!uploadedData ? (
              <Upload.Dragger {...uploadProps} disabled={isUploading}>
                <p className="ant-upload-drag-icon">
                  <InboxOutlined style={{ color: '#1677ff', fontSize: 40 }} />
                </p>
                <p className="ant-upload-text" style={{ fontSize: 13, fontWeight: 500 }}>
                  {t.upload_drag_text}
                </p>
                <p className="ant-upload-hint" style={{ fontSize: 11 }}>
                  {t.upload_hint}
                </p>
              </Upload.Dragger>
            ) : (
              <div style={{ textAlign: 'center', padding: '10px 0' }}>
                <div
                  style={{
                    padding: '12px',
                    borderRadius: '8px',
                    background: 'rgba(22, 119, 255, 0.05)',
                    border: '1px solid rgba(22, 119, 255, 0.2)',
                    marginBottom: 12,
                  }}
                >
                  <Text strong style={{ fontSize: 14 }}>
                    {uploadedData.filename}
                  </Text>
                  <div>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {uploadedData.total_rows} dòng dữ liệu • {uploadedData.columns.length} cột
                    </Text>
                  </div>
                </div>

                <Space>
                  <Button size="small" icon={<ReloadOutlined />} onClick={handleChangeFileOnly}>
                    {t.btn_change_file}
                  </Button>
                  <Button size="small" danger onClick={handleResetAll}>
                    {t.btn_reset_all}
                  </Button>
                </Space>
              </div>
            )}
          </Card>

          {/* 2. Target Web Config Card */}
          <Card
            title={
              <Space>
                <RocketOutlined style={{ color: '#1677ff' }} />
                <span>{t.step_target_title}</span>
              </Space>
            }
            bordered={false}
          >
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <div>
                <Text strong style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                  {t.label_target_url}:
                </Text>
                <Input
                  placeholder={t.placeholder_target_url}
                  value={targetUrl}
                  onChange={handleUrlChange}
                  allowClear
                />
              </div>

              <div>
                <Checkbox
                  checked={useSession}
                  onChange={(e) => setUseSession(e.target.checked)}
                >
                  <Text style={{ fontSize: 12 }}>{t.label_persistent_session}</Text>
                </Checkbox>
              </div>

              <Divider style={{ margin: '8px 0' }} />

              <div>
                <Text strong style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                  {t.label_submit_selector}:
                </Text>
                <Space style={{ width: '100%' }}>
                  <Input
                    placeholder={t.placeholder_submit_selector}
                    value={submitSelector}
                    onChange={(e) => setSubmitSelector(e.target.value)}
                    style={{ fontFamily: 'monospace' }}
                  />
                  <Tooltip title="Chọn nút Submit trực tiếp">
                    <Button
                      type="primary"
                      icon={<AimOutlined />}
                      loading={isPickingSubmit}
                      onClick={handlePickSubmitSelector}
                    >
                      {t.btn_pick}
                    </Button>
                  </Tooltip>
                </Space>
              </div>

              <div>
                <Text strong style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                  {t.label_trigger_selector}:
                </Text>
                <Space style={{ width: '100%' }}>
                  <Input
                    placeholder={t.placeholder_trigger_selector}
                    value={openFormTrigger}
                    onChange={(e) => setOpenFormTrigger(e.target.value)}
                    style={{ fontFamily: 'monospace' }}
                  />
                  <Tooltip title="Chọn nút trigger trực tiếp">
                    <Button
                      type="primary"
                      icon={<AimOutlined />}
                      loading={isPickingTrigger}
                      onClick={handlePickTriggerSelector}
                    >
                      {t.btn_pick}
                    </Button>
                  </Tooltip>
                </Space>
              </div>

              {/* TABLE MODE TOGGLE */}
              <div
                style={{
                  borderRadius: 10,
                  border: tableMode ? '1.5px solid #1677ff' : '1.5px solid #e8e8e8',
                  padding: '12px 14px',
                  background: tableMode ? 'rgba(22,119,255,0.04)' : 'transparent',
                  transition: 'all 0.25s',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: tableMode ? 12 : 0 }}>
                  <Space>
                    <TableOutlined style={{ color: tableMode ? '#1677ff' : '#8c8c8c', fontSize: 16 }} />
                    <div>
                      <Text strong style={{ fontSize: 13 }}>{t.table_mode_title}</Text>
                      <br />
                      <Text type="secondary" style={{ fontSize: 11 }}>{t.table_mode_hint}</Text>
                    </div>
                  </Space>
                  <Checkbox
                    checked={tableMode}
                    disabled={hybridMode}
                    onChange={(e) => setTableMode(e.target.checked)}
                    aria-label={t.table_mode_title}
                  />
                </div>

                {tableMode && (
                  <Space direction="vertical" size={10} style={{ width: '100%' }}>
                    <Alert
                      type="info"
                      showIcon
                      icon={<InfoCircleOutlined />}
                      style={{ fontSize: 11, borderRadius: 8 }}
                      message={
                        <span>
                          Dùng <code style={{ background: 'rgba(22,119,255,0.1)', padding: '1px 5px', borderRadius: 4 }}>{'{row}'}</code> trong selector để tự động thay thế số thứ tự hàng (1, 2, 3...).
                          <br />
                          <Text type="secondary" style={{ fontSize: 10 }}>
                            Ví dụ: <code>tr:nth-child({'{row}'}) input</code>, <code>tr:nth-of-type({'{row}'}) button</code>. Nếu mỗi hàng có nút hành động riêng, thêm mapping loại <strong>Click action</strong> cho selector nút đó.
                          </Text>
                        </span>
                      }
                    />
                  </Space>
                )}
              </div>

              <div
                style={{
                  borderRadius: 10,
                  border: hybridMode ? '1.5px solid #1677ff' : '1.5px solid #e8e8e8',
                  padding: '12px 14px',
                  background: hybridMode ? 'rgba(22,119,255,0.04)' : 'transparent',
                  transition: 'all 0.25s',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Space>
                    <TableOutlined style={{ color: hybridMode ? '#1677ff' : '#8c8c8c', fontSize: 16 }} />
                    <div>
                      <Text strong style={{ fontSize: 13 }}>{t.hybrid_mode_title}</Text>
                      <br />
                      <Text type="secondary" style={{ fontSize: 11 }}>{t.hybrid_mode_hint}</Text>
                    </div>
                  </Space>
                  <Checkbox
                    checked={hybridMode}
                    onChange={(event) => {
                      setHybridMode(event.target.checked);
                      if (event.target.checked) setTableMode(false);
                    }}
                    aria-label={t.hybrid_mode_title}
                  />
                </div>
              </div>


              <Alert
                type={activeMappingIssues.length === 0 ? 'success' : 'warning'}
                showIcon
                message={activeMappingIssues.length === 0 ? t.config_ready_title : t.config_incomplete_title.replace('{count}', String(activeMappingIssues.length))}
                description={activeMappingIssues.length > 0 ? activeMappingIssues.slice(0, 3).join(' ') : t.config_ready_hint}
                style={{ marginBottom: 4 }}
              />

              <Button
                type="primary"
                size="large"
                icon={<RocketOutlined />}
                loading={isStarting}
                onClick={handleStartAutomation}
                style={{
                  width: '100%',
                  height: 44,
                  fontWeight: 600,
                  fontSize: 14,
                  borderRadius: 8,
                }}
              >
                {t.btn_start_automation}
              </Button>

              <Button
                icon={<SaveOutlined />}
                onClick={handleSavePreset}
                style={{ width: '100%' }}
              >
                {t.btn_save_preset}
              </Button>
            </Space>
          </Card>
        </Space>
      </Col>

      {/* RIGHT COLUMN: Tabs for Mapping & Excel Preview (Split-View Right) */}
      <Col xs={24} lg={14} xl={15}>
        <Card bordered={false} bodyStyle={{ padding: '16px 20px' }}>
          <Tabs
            defaultActiveKey="mapping"
            tabBarExtraContent={!hybridMode ? (
              <Space size="small">
                <Button
                  icon={!isMobile ? <AimOutlined /> : undefined}
                  onClick={handlePickRemainingFieldSelectors}
                  loading={isPickingBatch}
                  disabled={mappingItems.length === 0 || mappingItems.every((item) => Boolean(item.selector.trim()))}
                  size="small"
                  aria-label={t.btn_pick_all_fields}
                  title={t.btn_pick_all_fields}
                >
                  {isMobile ? t.btn_pick_all_fields_short : t.btn_pick_all_fields}
                </Button>
                <Button
                  type="dashed"
                  icon={<PlusOutlined />}
                  onClick={handleAddMappingRow}
                  size="small"
                  aria-label={t.btn_add_mapping_field}
                  title={t.btn_add_mapping_field}
                >
                  {!isMobile && t.btn_add_mapping_field}
                </Button>
              </Space>
            ) : null}
            items={[
              {
                key: 'mapping',
                label: (
                  <span style={{ fontWeight: 600, fontSize: 13 }}>{t.tab_mapping}</span>
                ),
                children: hybridMode ? (
                  <HybridMappingPlanEditor
                    draft={mappingPlanDraft}
                    sheets={uploadedData?.sheets || []}
                    lang={lang}
                    onChange={setMappingPlanDraft}
                    onPickSelector={handlePickPlanSelector}
                    onPickSelectors={handlePickPlanSelectors}
                  />
                ) : (
                  <div>
                    {mappingItems.length === 0 ? (
                      <Alert
                        message="Chưa có trường ánh xạ nào"
                        description="Nhấn nút '+ Thêm trường ánh xạ' ở góc trên để cấu hình selector cho các cột Excel."
                        type="info"
                        showIcon
                        style={{ margin: '20px 0' }}
                      />
                    ) : (
                      <Table
                        dataSource={mappingItems}
                        columns={mappingColumns}
                        rowKey="id"
                        pagination={false}
                        size="small"
                        bordered
                        scroll={{ x: 'max-content' }}
                      />
                    )}
                  </div>
                ),
              },
              {
                key: 'preview',
                label: (
                  <span style={{ fontWeight: 600, fontSize: 13 }}>{t.tab_preview}</span>
                ),
                children: (
                  <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                    {(uploadedData?.sheets?.length || 0) > 1 && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Text type="secondary">{t.preview_sheet}</Text>
                        <Select
                          aria-label={t.preview_sheet}
                          value={previewSheetName || uploadedData?.sheets?.[0]?.name}
                          style={{ minWidth: 180 }}
                          options={uploadedData?.sheets?.map((sheet) => ({ value: sheet.name, label: sheet.name }))}
                          onChange={(sheetName) => {
                            setPreviewSheetName(sheetName);
                            setPreviewPage(1);
                          }}
                        />
                      </div>
                    )}
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
                      <Input
                        placeholder={t.search_preview_placeholder}
                        prefix={<SearchOutlined style={{ color: '#bfbfbf' }} />}
                        value={previewQuery}
                        onChange={(e) => {
                          setPreviewQuery(e.target.value);
                          setPreviewPage(1);
                        }}
                        style={{ maxWidth: 300 }}
                        allowClear
                      />
                      <Text type="secondary" style={{ alignSelf: 'center', fontSize: 12 }}>
                        {previewTotal} {t.total_records}
                      </Text>
                    </div>

                    <Table
                      dataSource={previewRows}
                      columns={previewTableColumns}
                      rowKey={(_, idx) => `row-${idx}`}
                      loading={isPreviewLoading}
                      size="small"
                      bordered
                      scroll={{ x: 'max-content', y: 400 }}
                      pagination={{
                        current: previewPage,
                        pageSize: previewPageSize,
                        total: previewTotal,
                        showSizeChanger: true,
                        pageSizeOptions: ['10', '20', '50'],
                        onChange: (page, pageSize) => {
                          setPreviewPage(page);
                          setPreviewPageSize(pageSize);
                        },
                      }}
                    />
                  </Space>
                ),
              },
            ]}
          />
        </Card>
      </Col>
    </Row>
  );
};
