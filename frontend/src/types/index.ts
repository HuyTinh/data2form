export interface MappingItem {
  id: string;
  field_name: string;
  selector: string;
  column: string;
  type?: 'text' | 'number' | 'email' | 'textarea' | 'select' | 'selection' | 'checkbox' | 'radio' | 'date' | 'click' | 'upload';
  multiple?: boolean;
  after_selector?: string; // Optional: click this selector after this field is filled
}

export interface PresetData {
  url: string;
  submit_selector: string;
  use_session: boolean;
  mappings: Record<string, any>;
  mapping_plan?: MappingPlan | null;
  open_form_trigger?: string;
  saved_at?: string;
}

export interface UploadResponse {
  filename: string;
  rel_path: string;
  columns: string[];
  total_rows: number;
  sheets?: WorkbookSheetInfo[];
}

export interface WorkbookSheetInfo {
  name: string;
  columns: string[];
  total_rows: number;
}

export interface PlanFieldMapping {
  selector: string;
  type?: MappingItem['type'];
  multiple?: boolean;
  after_selector?: string;
}

export interface DetailTablePlan {
  id: string;
  name: string;
  sheet_name: string;
  parent_key_column: string;
  mappings: Record<string, PlanFieldMapping>;
  add_row_selector?: string;
  row_save_selector?: string;
  row_save_timeout?: number;
}

export interface MappingPlan {
  version: 1;
  parent: {
    sheet_name: string;
    key_column: string;
    mappings: Record<string, PlanFieldMapping>;
  };
  open_form_trigger: string;
  submit_selector: string;
  detail_tables: DetailTablePlan[];
}

export interface PickerTarget {
  id: string;
  label: string;
}

export interface PickerSelection {
  target_id: string;
  label: string;
  selector: string;
}

export interface DetailTableDraft {
  id: string;
  name: string;
  sheet_name: string;
  parent_key_column: string;
  mappings: MappingItem[];
  add_row_selector: string;
  row_save_selector: string;
  row_save_timeout: number;
}

export interface MappingPlanDraft {
  parent_sheet_name: string;
  parent_key_column: string;
  parent_mappings: MappingItem[];
  detail_tables: DetailTableDraft[];
}

export interface DetailRowResult {
  row: number;
  status: 'running' | 'completed' | 'failed';
  errors: { field: string; message: string }[];
  applied_fields?: string[];
  partial_state?: boolean;
}

export interface DetailTableResult {
  table_id: string;
  name: string;
  status: 'running' | 'completed' | 'failed' | 'skipped';
  rows: DetailRowResult[];
  errors: { field: string; message: string }[];
  partial_state?: boolean;
}

export interface ParentResult {
  parent_key: string;
  row: number;
  status: 'running' | 'completed' | 'failed';
  errors: { field: string; message: string }[];
  tables: DetailTableResult[];
  applied_fields?: string[];
  partial_state?: boolean;
}

export interface PreviewResponse {
  data: Record<string, any>[];
  total: number;
}

export interface LogItem {
  time?: string;
  level: 'info' | 'success' | 'warning' | 'error';
  message: string;
  msg?: string;
}

export interface AutomationStatusResponse {
  is_running: boolean;
  current_row: number;
  total_rows: number;
  logs: LogItem[];
  screenshots: string[];
  row_results: RowResult[];
  detail_results?: ParentResult[];
}

export interface RowResult {
  row: number;
  status: 'running' | 'completed' | 'failed';
  errors: { field: string; message: string }[];
  partial_state?: boolean;
}

export interface HistoryItem {
  id: number;
  filename: string;
  rel_path: string;
  start_time: string;
  total_rows: number;
  status: string;
}
