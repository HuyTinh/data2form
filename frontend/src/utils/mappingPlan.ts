import type {
  DetailTablePlan,
  MappingItem,
  MappingPlan,
  MappingPlanDraft,
  PlanFieldMapping,
  WorkbookSheetInfo,
} from '../types';

const createField = (id: string, column = ''): MappingItem => ({
  id,
  field_name: column || 'Trường mới',
  column,
  selector: '',
  type: 'text',
});

export const createMappingPlanDraft = (sheets: WorkbookSheetInfo[] = []): MappingPlanDraft => ({
  parent_sheet_name: sheets[0]?.name || '',
  parent_key_column: sheets[0]?.columns[0] || '',
  parent_mappings: [],
  detail_tables: [],
});

const mappingsToObject = (items: MappingItem[]): Record<string, PlanFieldMapping> => {
  const result: Record<string, PlanFieldMapping> = {};
  items.forEach((item) => {
    const sourceColumn = item.column.trim() || (item.type === 'click' ? item.field_name.trim() : '');
    if (!sourceColumn || !item.selector.trim()) return;
    if (Object.prototype.hasOwnProperty.call(result, sourceColumn)) {
      throw new Error(`Duplicate mapping for Excel column '${sourceColumn}'.`);
    }
    result[sourceColumn] = {
      selector: item.selector.trim(),
      type: item.type || 'text',
      ...(item.multiple ? { multiple: true } : {}),
      ...(item.after_selector?.trim() ? { after_selector: item.after_selector.trim() } : {}),
    };
  });
  return result;
};

const objectToMappings = (mappings: Record<string, PlanFieldMapping> = {}, prefix: string): MappingItem[] =>
  Object.entries(mappings).map(([column, mapping], index) => ({
    id: `${prefix}-${index}-${column}`,
    field_name: column,
    column,
    selector: mapping.selector || '',
    type: mapping.type || 'text',
    multiple: Boolean(mapping.multiple),
    after_selector: mapping.after_selector || '',
  }));

export const mappingPlanToDraft = (
  plan: MappingPlan | null | undefined,
  sheets: WorkbookSheetInfo[] = []
): MappingPlanDraft => {
  if (!plan) return createMappingPlanDraft(sheets);
  return {
    parent_sheet_name: plan.parent?.sheet_name || sheets[0]?.name || '',
    parent_key_column: plan.parent?.key_column || '',
    parent_mappings: objectToMappings(plan.parent?.mappings || {}, 'parent'),
    detail_tables: (plan.detail_tables || []).map((table) => ({
      id: table.id,
      name: table.name,
      sheet_name: table.sheet_name,
      parent_key_column: table.parent_key_column,
      mappings: objectToMappings(table.mappings || {}, table.id),
      add_row_selector: table.add_row_selector || '',
      row_save_selector: table.row_save_selector || '',
      row_save_timeout: table.row_save_timeout ?? 8000,
    })),
  };
};

export const draftToMappingPlan = (
  draft: MappingPlanDraft,
  openFormTrigger: string,
  submitSelector: string
): MappingPlan => ({
  version: 1,
  parent: {
    sheet_name: draft.parent_sheet_name,
    key_column: draft.parent_key_column,
    mappings: mappingsToObject(draft.parent_mappings),
  },
  open_form_trigger: openFormTrigger.trim(),
  submit_selector: submitSelector.trim(),
  detail_tables: draft.detail_tables.map((table): DetailTablePlan => ({
    id: table.id,
    name: table.name.trim(),
    sheet_name: table.sheet_name,
    parent_key_column: table.parent_key_column,
    mappings: mappingsToObject(table.mappings),
    add_row_selector: table.add_row_selector.trim(),
    row_save_selector: table.row_save_selector.trim(),
    row_save_timeout: table.row_save_timeout,
  })),
});

const validateFields = (
  fields: MappingItem[],
  columns: string[],
  label: string,
  issues: string[]
) => {
  if (fields.length === 0) issues.push(`${label}: cần ít nhất một field mapping.`);
  const usedColumns = new Set<string>();
  fields.forEach((field, index) => {
    const sourceColumn = field.column.trim() || (field.type === 'click' ? field.field_name.trim() : '');
    if (!sourceColumn) issues.push(`${label}, field ${index + 1}: chưa chọn cột nguồn.`);
    else if (field.type !== 'click' && !columns.includes(sourceColumn)) issues.push(`${label}: không tìm thấy cột '${sourceColumn}'.`);
    else if (usedColumns.has(sourceColumn)) issues.push(`${label}: cột '${sourceColumn}' bị mapping trùng.`);
    else usedColumns.add(sourceColumn);
    if (!field.selector.trim()) issues.push(`${label}, field ${index + 1}: thiếu selector.`);
  });
};

export const validateMappingPlanDraft = (
  draft: MappingPlanDraft,
  sheets: WorkbookSheetInfo[],
  submitSelector: string
): string[] => {
  const issues: string[] = [];
  const parentSheet = sheets.find((sheet) => sheet.name === draft.parent_sheet_name);
  if (!parentSheet) {
    issues.push('Chưa chọn sheet thông tin chung.');
  } else {
    if (!draft.parent_key_column || !parentSheet.columns.includes(draft.parent_key_column)) {
      issues.push('Chưa chọn cột khóa cho thông tin chung.');
    }
    validateFields(draft.parent_mappings, parentSheet.columns, 'Thông tin chung', issues);
  }

  if (draft.detail_tables.length === 0) issues.push('Cần cấu hình ít nhất một bảng chi tiết.');
  const usedIds = new Set<string>();
  const usedSheets = new Set<string>([draft.parent_sheet_name]);
  draft.detail_tables.forEach((table, index) => {
    const label = table.name.trim() || `Bảng chi tiết ${index + 1}`;
    if (!table.name.trim()) issues.push(`Bảng ${index + 1}: chưa đặt tên.`);
    if (!table.id || usedIds.has(table.id)) issues.push(`${label}: mã bảng bị trùng hoặc rỗng.`);
    usedIds.add(table.id);
    if (!table.sheet_name) {
      issues.push(`${label}: chưa chọn sheet nguồn.`);
      return;
    }
    if (usedSheets.has(table.sheet_name)) issues.push(`${label}: mỗi bảng cần một sheet riêng.`);
    usedSheets.add(table.sheet_name);
    const sheet = sheets.find((candidate) => candidate.name === table.sheet_name);
    if (!sheet) {
      issues.push(`${label}: không tìm thấy sheet '${table.sheet_name}'.`);
      return;
    }
    if (!table.parent_key_column || !sheet.columns.includes(table.parent_key_column)) {
      issues.push(`${label}: chưa chọn cột khóa liên kết.`);
    }
    if (table.row_save_timeout < 1000 || table.row_save_timeout > 60000) {
      issues.push(`${label}: timeout lưu dòng phải trong khoảng 1000–60000 ms.`);
    }
    validateFields(table.mappings, sheet.columns, label, issues);
  });
  if (!submitSelector.trim()) issues.push('Chưa chọn selector lưu/gửi form chính.');
  return issues;
};

export { createField };
