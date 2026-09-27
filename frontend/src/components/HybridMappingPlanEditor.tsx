import React, { useId, useRef, useState } from 'react';
import {
  Button,
  Card,
  Checkbox,
  Grid,
  Input,
  InputNumber,
  Select,
  Space,
  Tooltip,
  Typography,
} from 'antd';
import {
  ArrowDownOutlined,
  ArrowUpOutlined,
  AimOutlined,
  DeleteOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import type { Language } from '../i18n';
import { translations } from '../i18n';
import type { DetailTableDraft, MappingItem, MappingPlanDraft, PickerSelection, PickerTarget, WorkbookSheetInfo } from '../types';
import { createField } from '../utils/mappingPlan';

const { Text } = Typography;

type MappingPlanEditorProps = {
  draft: MappingPlanDraft;
  sheets: WorkbookSheetInfo[];
  lang: Language;
  onChange: (draft: MappingPlanDraft) => void;
  onPickSelector: (label: string, rowScoped: boolean) => Promise<string | null>;
  onPickSelectors: (targets: PickerTarget[], rowScoped: boolean) => Promise<PickerSelection[]>;
};

export const HybridMappingPlanEditor: React.FC<MappingPlanEditorProps> = ({
  draft,
  sheets,
  lang,
  onChange,
  onPickSelector,
  onPickSelectors,
}) => {
  const t = translations[lang];
  const screens = Grid.useBreakpoint();
  const isMobile = !screens.md;
  const [pickingKey, setPickingKey] = useState<string | null>(null);
  const tableIdPrefix = useId().replace(/[^a-zA-Z0-9_-]/g, '_');
  const tableIdSequence = useRef(0);
  const fieldIdSequence = useRef(0);

  const updateParentField = (id: string, patch: Partial<MappingItem>) => {
    onChange({
      ...draft,
      parent_mappings: draft.parent_mappings.map((field) => field.id === id ? { ...field, ...patch } : field),
    });
  };

  const updateTable = (tableId: string, patch: Partial<DetailTableDraft>) => {
    onChange({
      ...draft,
      detail_tables: draft.detail_tables.map((table) => table.id === tableId ? { ...table, ...patch } : table),
    });
  };

  const updateTableField = (tableId: string, fieldId: string, patch: Partial<MappingItem>) => {
    onChange({
      ...draft,
      detail_tables: draft.detail_tables.map((table) => table.id === tableId
        ? { ...table, mappings: table.mappings.map((field) => field.id === fieldId ? { ...field, ...patch } : field) }
        : table),
    });
  };

  const addField = (tableId?: string) => {
    const sheetName = tableId
      ? draft.detail_tables.find((table) => table.id === tableId)?.sheet_name
      : draft.parent_sheet_name;
    const sheet = sheets.find((item) => item.name === sheetName);
    const excludedKey = tableId
      ? draft.detail_tables.find((table) => table.id === tableId)?.parent_key_column
      : draft.parent_key_column;
    const existingFields = tableId
      ? draft.detail_tables.find((table) => table.id === tableId)?.mappings || []
      : draft.parent_mappings;
    const usedColumns = new Set(existingFields.map((item) => item.column).filter(Boolean));
    const column = sheet?.columns.find((item) => item !== excludedKey && !usedColumns.has(item)) || '';
    fieldIdSequence.current += 1;
    const field = createField(`field-${tableIdPrefix}-${fieldIdSequence.current}`, column);
    if (!field.column) field.field_name = '';
    if (tableId) {
      const table = draft.detail_tables.find((item) => item.id === tableId);
      if (table) updateTable(tableId, { mappings: [...table.mappings, field] });
    } else {
      onChange({ ...draft, parent_mappings: [...draft.parent_mappings, field] });
    }
  };

  const addTable = () => {
    const availableSheet = sheets.find((sheet) =>
      sheet.name !== draft.parent_sheet_name && !draft.detail_tables.some((table) => table.sheet_name === sheet.name)
    );
    const tableNumber = draft.detail_tables.length + 1;
    tableIdSequence.current += 1;
    let id = `detail-${tableIdPrefix}-${tableIdSequence.current}`;
    while (draft.detail_tables.some((table) => table.id === id)) {
      tableIdSequence.current += 1;
      id = `detail-${tableIdPrefix}-${tableIdSequence.current}`;
    }
    onChange({
      ...draft,
      detail_tables: [...draft.detail_tables, {
        id,
        name: `${lang === 'vi' ? 'Bảng chi tiết' : 'Detail table'} ${tableNumber}`,
        sheet_name: availableSheet?.name || '',
        parent_key_column: availableSheet?.columns.includes(draft.parent_key_column)
          ? draft.parent_key_column
          : availableSheet?.columns[0] || '',
        mappings: [],
        add_row_selector: '',
        row_save_selector: '',
        row_save_timeout: 8000,
      }],
    });
  };

  const moveTable = (tableId: string, offset: -1 | 1) => {
    const index = draft.detail_tables.findIndex((table) => table.id === tableId);
    const targetIndex = index + offset;
    if (index < 0 || targetIndex < 0 || targetIndex >= draft.detail_tables.length) return;
    const nextTables = [...draft.detail_tables];
    [nextTables[index], nextTables[targetIndex]] = [nextTables[targetIndex], nextTables[index]];
    onChange({ ...draft, detail_tables: nextTables });
  };

  const pickField = async (scopeId: string, field: MappingItem, rowScoped: boolean, tableId?: string) => {
    setPickingKey(scopeId);
    try {
      const selector = await onPickSelector(field.field_name || field.column || t.plan_selector, rowScoped);
      if (!selector) return;
      if (tableId) updateTableField(tableId, field.id, { selector });
      else updateParentField(field.id, { selector });
    } finally {
      setPickingKey(null);
    }
  };

  const pickMissingFields = async (tableId?: string) => {
    const fields = tableId
      ? draft.detail_tables.find((table) => table.id === tableId)?.mappings || []
      : draft.parent_mappings;
    const missing = fields.filter((field) => !field.selector.trim());
    if (!missing.length) return;
    const scopeId = tableId || 'parent-batch';
    setPickingKey(scopeId);
    try {
      const targets = missing.map((field) => ({
        id: field.id,
        label: field.field_name || field.column || t.plan_selector,
      }));
      const selections = await onPickSelectors(
        targets,
        Boolean(tableId)
      );
      const selectorById = new Map(selections.map((selection) => [selection.target_id, selection.selector]));
      if (tableId) {
        const table = draft.detail_tables.find((item) => item.id === tableId);
        if (table) updateTable(tableId, { mappings: table.mappings.map((field) => ({ ...field, selector: selectorById.get(field.id) || field.selector })) });
      } else {
        onChange({ ...draft, parent_mappings: draft.parent_mappings.map((field) => ({ ...field, selector: selectorById.get(field.id) || field.selector })) });
      }
    } finally {
      setPickingKey(null);
    }
  };

  const renderFields = (fields: MappingItem[], columns: string[], rowScoped: boolean, tableId?: string) => (
    <Space direction="vertical" size="small" style={{ width: '100%' }}>
      {fields.map((field) => {
        const fieldScope = `${tableId || 'parent'}-${field.id}`;
        const remove = () => tableId
          ? updateTable(tableId, { mappings: fields.filter((item) => item.id !== field.id) })
          : onChange({ ...draft, parent_mappings: fields.filter((item) => item.id !== field.id) });
        const update = (patch: Partial<MappingItem>) => tableId
          ? updateTableField(tableId, field.id, patch)
          : updateParentField(field.id, patch);
        return (
          <Card key={field.id} size="small" bodyStyle={{ padding: 10 }}>
            <Space direction="vertical" size={8} style={{ width: '100%' }}>
              {isMobile ? (
                <Space direction="vertical" style={{ width: '100%' }} size={4}>
                  <Text type="secondary">{t.plan_source_column}</Text>
                  <Select
                    aria-label={t.plan_source_column}
                    value={field.column || undefined}
                    placeholder={t.plan_source_column}
                    showSearch
                    optionFilterProp="label"
                    style={{ width: '100%' }}
                    options={columns.map((column) => ({ value: column, label: column }))}
                    onChange={(column) => update({ column, field_name: column })}
                  />
                  <Text type="secondary">{t.plan_selector}</Text>
                  <Input.TextArea
                    aria-label={t.plan_selector}
                    value={field.selector}
                    placeholder={rowScoped ? 'tr:nth-of-type({row}) input' : '#input-name'}
                    autoSize={{ minRows: 1, maxRows: 3 }}
                    style={{ fontFamily: 'monospace', resize: 'none' }}
                    onChange={(event) => update({ selector: event.target.value })}
                  />
                  <Space size="small">
                    <Tooltip title={t.btn_pick_tooltip}>
                      <Button
                        icon={<AimOutlined />}
                        loading={pickingKey === fieldScope}
                        onClick={() => pickField(fieldScope, field, rowScoped, tableId)}
                        aria-label={`${t.btn_pick} ${field.field_name || field.column}`}
                      />
                    </Tooltip>
                    <Button danger icon={<DeleteOutlined />} onClick={remove} aria-label={`${t.col_actions} ${field.field_name || field.column}`} />
                  </Space>
                </Space>
              ) : (
                <Space.Compact style={{ width: '100%' }}>
                  <Select
                    aria-label={t.plan_source_column}
                    value={field.column || undefined}
                    placeholder={t.plan_source_column}
                    showSearch
                    optionFilterProp="label"
                    style={{ width: '38%' }}
                    options={columns.map((column) => ({ value: column, label: column }))}
                    onChange={(column) => update({ column, field_name: column })}
                  />
                  <Input
                    aria-label={t.plan_selector}
                    value={field.selector}
                    placeholder={rowScoped ? 'tr:nth-of-type({row}) input' : '#input-name'}
                    style={{ fontFamily: 'monospace' }}
                    onChange={(event) => update({ selector: event.target.value })}
                  />
                  <Tooltip title={t.btn_pick_tooltip}>
                    <Button
                      icon={<AimOutlined />}
                      loading={pickingKey === fieldScope}
                      onClick={() => pickField(fieldScope, field, rowScoped, tableId)}
                      aria-label={`${t.btn_pick} ${field.field_name || field.column}`}
                    />
                  </Tooltip>
                  <Button danger icon={<DeleteOutlined />} onClick={remove} aria-label={`${t.col_actions} ${field.field_name || field.column}`} />
                </Space.Compact>
              )}
              <Space wrap>
                <Select
                  aria-label={t.plan_field_type}
                  value={field.type || 'text'}
                  style={{ minWidth: 150 }}
                  onChange={(type) => update({ type: type as NonNullable<MappingItem['type']> })}
                  options={[
                    { value: 'text', label: 'Text' },
                    { value: 'number', label: 'Number' },
                    { value: 'email', label: 'Email' },
                    { value: 'textarea', label: 'Textarea' },
                    { value: 'select', label: 'Select / Dropdown' },
                    { value: 'checkbox', label: 'Checkbox' },
                    { value: 'radio', label: 'Radio group' },
                    { value: 'date', label: 'Date' },
                    { value: 'upload', label: 'File upload' },
                    { value: 'click', label: 'Click action' },
                  ]}
                />
                {(field.type === 'select' || field.type === 'checkbox') && (
                  <Checkbox checked={Boolean(field.multiple)} onChange={(event) => update({ multiple: event.target.checked })}>
                    {t.multiple_values}
                  </Checkbox>
                )}
              </Space>
            </Space>
          </Card>
        );
      })}
      <Space wrap>
        <Button size="small" icon={<PlusOutlined />} onClick={() => addField(tableId)}>
          {tableId ? t.plan_add_field : t.plan_add_parent_field}
        </Button>
        <Button
          size="small"
          icon={<AimOutlined />}
          loading={pickingKey === (tableId || 'parent-batch')}
          onClick={() => pickMissingFields(tableId)}
        >
          {t.plan_pick_batch}
        </Button>
      </Space>
    </Space>
  );

  const parentSheet = sheets.find((sheet) => sheet.name === draft.parent_sheet_name);
  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Card size="small" title={t.plan_parent_title}>
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <Space wrap style={{ width: '100%' }}>
            <div style={{ flex: 1, minWidth: 180 }}>
              <Text type="secondary">{t.plan_parent_sheet}</Text>
              <Select
                value={draft.parent_sheet_name || undefined}
                style={{ width: '100%' }}
                options={sheets.map((sheet) => ({ value: sheet.name, label: `${sheet.name} (${sheet.total_rows})` }))}
                onChange={(parent_sheet_name) => {
                  const nextSheet = sheets.find((sheet) => sheet.name === parent_sheet_name);
                  onChange({
                    ...draft,
                    parent_sheet_name,
                    parent_key_column: nextSheet?.columns[0] || '',
                  });
                }}
              />
            </div>
            <div style={{ flex: 1, minWidth: 180 }}>
              <Text type="secondary">{t.plan_parent_key}</Text>
              <Select
                value={draft.parent_key_column || undefined}
                style={{ width: '100%' }}
                options={(parentSheet?.columns || []).map((column) => ({ value: column, label: column }))}
                onChange={(parent_key_column) => onChange({ ...draft, parent_key_column })}
              />
            </div>
          </Space>
          {renderFields(draft.parent_mappings, parentSheet?.columns || [], false)}
        </Space>
      </Card>

      <Card
        size="small"
        title={t.plan_tables_title}
        extra={<Button size="small" icon={<PlusOutlined />} onClick={addTable}>{t.plan_add_table}</Button>}
      >
        {draft.detail_tables.length === 0 ? (
          <Text type="secondary">{t.plan_empty_table}</Text>
        ) : (
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            {draft.detail_tables.map((table, index) => {
              const tableSheet = sheets.find((sheet) => sheet.name === table.sheet_name);
              const sheetOptions = sheets
                .filter((sheet) => sheet.name !== draft.parent_sheet_name && (sheet.name === table.sheet_name || !draft.detail_tables.some((other) => other.id !== table.id && other.sheet_name === sheet.name)))
                .map((sheet) => ({ value: sheet.name, label: `${sheet.name} (${sheet.total_rows})` }));
              return (
                <Card
                  key={table.id}
                  size="small"
                  title={<Input value={table.name} aria-label={t.plan_table_name} onChange={(event) => updateTable(table.id, { name: event.target.value })} />}
                  extra={(
                    <Space size="small">
                      <Button size="small" type="text" icon={<ArrowUpOutlined />} title={t.plan_move_up} aria-label={t.plan_move_up} disabled={index === 0} onClick={() => moveTable(table.id, -1)} />
                      <Button size="small" type="text" icon={<ArrowDownOutlined />} title={t.plan_move_down} aria-label={t.plan_move_down} disabled={index === draft.detail_tables.length - 1} onClick={() => moveTable(table.id, 1)} />
                      <Button danger type="text" icon={<DeleteOutlined />} aria-label={t.plan_remove_table} onClick={() => onChange({ ...draft, detail_tables: draft.detail_tables.filter((item) => item.id !== table.id) })} />
                    </Space>
                  )}
                >
                  <Space direction="vertical" size="small" style={{ width: '100%' }}>
                    <Space wrap style={{ width: '100%' }}>
                      <div style={{ flex: 1, minWidth: 180 }}>
                        <Text type="secondary">{t.plan_table_sheet}</Text>
                        <Select
                          value={table.sheet_name || undefined}
                          style={{ width: '100%' }}
                          options={sheetOptions}
                          onChange={(sheet_name) => {
                            const nextSheet = sheets.find((sheet) => sheet.name === sheet_name);
                            updateTable(table.id, {
                              sheet_name,
                              parent_key_column: nextSheet?.columns.includes(draft.parent_key_column)
                                ? draft.parent_key_column
                                : nextSheet?.columns[0] || '',
                            });
                          }}
                        />
                      </div>
                      <div style={{ flex: 1, minWidth: 180 }}>
                        <Text type="secondary">{t.plan_table_parent_key}</Text>
                        <Select
                          value={table.parent_key_column || undefined}
                          style={{ width: '100%' }}
                          options={(tableSheet?.columns || []).map((column) => ({ value: column, label: column }))}
                          onChange={(parent_key_column) => updateTable(table.id, { parent_key_column })}
                        />
                      </div>
                    </Space>
                    <Space.Compact style={{ width: '100%' }}>
                      <Input
                        aria-label={t.plan_table_add_row}
                        value={table.add_row_selector}
                        placeholder={t.plan_table_add_row}
                        style={{ fontFamily: 'monospace' }}
                        onChange={(event) => updateTable(table.id, { add_row_selector: event.target.value })}
                      />
                      <Button icon={<AimOutlined />} onClick={async () => {
                        setPickingKey(`${table.id}-add`);
                        try {
                          const selector = await onPickSelector(t.plan_table_add_row, false);
                          if (selector) updateTable(table.id, { add_row_selector: selector });
                        } finally { setPickingKey(null); }
                      }} loading={pickingKey === `${table.id}-add`} aria-label={t.plan_table_add_row} />
                    </Space.Compact>
                    <Space.Compact style={{ width: '100%' }}>
                      <Input
                        aria-label={t.plan_table_save_row}
                        value={table.row_save_selector}
                        placeholder={t.plan_table_save_row}
                        style={{ fontFamily: 'monospace' }}
                        onChange={(event) => updateTable(table.id, { row_save_selector: event.target.value })}
                      />
                      <Button icon={<AimOutlined />} onClick={async () => {
                        setPickingKey(`${table.id}-save`);
                        try {
                          const selector = await onPickSelector(t.plan_table_save_row, true);
                          if (selector) updateTable(table.id, { row_save_selector: selector });
                        } finally { setPickingKey(null); }
                      }} loading={pickingKey === `${table.id}-save`} aria-label={t.plan_table_save_row} />
                    </Space.Compact>
                    <Space>
                      <Text type="secondary">{t.plan_table_save_timeout}</Text>
                      <InputNumber
                        min={1000}
                        max={60000}
                        step={1000}
                        value={table.row_save_timeout}
                        onChange={(value) => updateTable(table.id, { row_save_timeout: value || 8000 })}
                        aria-label={t.plan_table_save_timeout}
                      />
                    </Space>
                    {renderFields(table.mappings, tableSheet?.columns || [], true, table.id)}
                  </Space>
                </Card>
              );
            })}
          </Space>
        )}
      </Card>
    </Space>
  );
};
