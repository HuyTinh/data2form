import axios from 'axios';
import type {
  UploadResponse,
  PresetData,
  PreviewResponse,
  AutomationStatusResponse,
  HistoryItem,
  LogItem,
  MappingPlan,
  PickerSelection,
  PickerTarget,
} from '../types';

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
});

export const uploadExcelFile = async (file: File): Promise<UploadResponse> => {
  const formData = new FormData();
  formData.append('file', file);
  const response = await api.post<UploadResponse>('/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

export const getExcelPreview = async (
  filename: string,
  page: number = 1,
  pageSize: number = 10,
  query: string = '',
  sheetName?: string
): Promise<PreviewResponse> => {
  const response = await api.get<PreviewResponse>('/preview', {
    params: {
      filename,
      page,
      page_size: pageSize,
      query,
      sheet_name: sheetName,
    },
  });
  return response.data;
};

export const clearCache = async (filename: string): Promise<void> => {
  await api.post('/clear-cache', null, { params: { filename } });
};

export const getPreset = async (url: string): Promise<PresetData | null> => {
  const response = await api.get<PresetData>('/presets', { params: { url } });
  return response.data;
};

export const savePreset = async (preset: {
  url: string;
  submit_selector: string;
  use_session: boolean;
  mappings: Record<string, any>;
  mapping_plan?: MappingPlan | null;
  open_form_trigger: string;
  saved_at: string;
}): Promise<void> => {
  await api.post('/presets', preset);
};

export const pickSelector = async (url: string, useSession: boolean): Promise<string | null> => {
  const response = await api.post<{ selector: string | null }>('/pick-selector', {
    url,
    use_session: useSession,
  });
  return response.data.selector;
};

export const pickSelectors = async (
  url: string,
  useSession: boolean,
  targetLabels: string[]
): Promise<string[]> => {
  const response = await api.post<{ selectors: string[] }>('/pick-selectors', {
    url,
    use_session: useSession,
    target_count: targetLabels.length,
    target_labels: targetLabels,
  });
  return response.data.selectors;
};

export const pickSelectorsForTargets = async (
  url: string,
  useSession: boolean,
  targets: PickerTarget[]
): Promise<PickerSelection[]> => {
  const response = await api.post<{ selections: PickerSelection[] }>('/pick-selectors', {
    url,
    use_session: useSession,
    target_count: targets.length,
    target_labels: targets.map((target) => target.label),
    targets,
  });
  return response.data.selections;
};

export const runAutomation = async (payload: {
  filename: string;
  url: string;
  submit_selector: string;
  open_form_trigger: string;
  mappings: Record<string, any>;
  mapping_plan?: MappingPlan;
  use_session: boolean;
  table_mode?: boolean;
  row_save_selector?: string;
  row_save_timeout?: number;
}): Promise<{ status: string }> => {
  const response = await api.post<{ status: string }>('/run', payload);
  return response.data;
};

export const getAutomationStatus = async (): Promise<AutomationStatusResponse> => {
  const response = await api.get<AutomationStatusResponse>('/status');
  return response.data;
};

export const getHistory = async (): Promise<HistoryItem[]> => {
  const response = await api.get<HistoryItem[]>('/history');
  return response.data;
};

export const getHistoryLogs = async (itemId: number): Promise<LogItem[]> => {
  const response = await api.get<LogItem[]>(`/history/${itemId}/logs`);
  return response.data;
};

export const getDownloadUrl = (itemId: number): string => {
  return `/api/download/${itemId}`;
};

export default api;
