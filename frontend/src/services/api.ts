import axios from 'axios';
import type { Interview, InterviewCreateRequest, Message, Blueprint, StructuredContent, ExpertProfile, ContentAnalysis, User, TokenResponse, TextAnalysis, TextAnalysisCreateRequest } from '@/types';
import { SKIP_AUTH } from '@/config/auth';
import { logger } from '@/utils/logger';

const API_BASE_URL = '/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器：自动附加JWT Token + 生成 request_id
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  // 生成请求追踪 ID
  const requestId = `req-${Math.random().toString(36).slice(2, 10)}`;
  config.headers['X-Request-ID'] = requestId;
  (config as any)._requestId = requestId;
  (config as any)._startTime = performance.now();

  logger.debug(`API request: ${config.method?.toUpperCase()} ${config.url}`, {
    requestId,
    url: config.url,
    method: config.method,
  });
  return config;
});

// 响应拦截器：处理401未授权 + 记录响应日志
api.interceptors.response.use(
  (response) => {
    const config = response.config as any;
    const duration = Math.round(performance.now() - (config._startTime || 0));
    const requestId = config._requestId;

    logger.debug(`API response: ${config.method?.toUpperCase()} ${config.url} ${response.status} (${duration}ms)`, {
      requestId,
      url: config.url,
      method: config.method,
      status: response.status,
      duration,
    });
    return response;
  },
  (error) => {
    const config = error.config as any;
    const duration = Math.round(performance.now() - ((config?._startTime) || 0));
    const requestId = config?._requestId;
    const status = error.response?.status;
    const statusText = error.response?.statusText;

    if (status === 401 && !SKIP_AUTH) {
      // 登录/注册/密码重置等认证端点的 401 是预期错误，不应触发全局登出
      const authPaths = ['/auth/login', '/auth/register', '/auth/password-reset-request', '/auth/password-reset-confirm'];
      const isAuthEndpoint = authPaths.some(path => config?.url?.includes(path));
      if (!isAuthEndpoint) {
        logger.warn('API 401 Unauthorized, redirecting to login', { requestId, url: config?.url });
        localStorage.removeItem('access_token');
        localStorage.removeItem('user');
        window.location.href = '/login';
      }
    } else if (status === 429) {
      logger.error('API 429 Too Many Requests', {
        requestId,
        url: config?.url,
        retryAfter: error.response?.headers?.['retry-after'],
        duration,
      });
    } else if (status >= 500) {
      logger.error(`API ${status} Server Error: ${statusText}`, {
        requestId,
        url: config?.url,
        duration,
      });
    } else if (status >= 400) {
      logger.warn(`API ${status} Client Error: ${statusText}`, {
        requestId,
        url: config?.url,
        duration,
      });
    } else {
      logger.error(`API request failed: ${error.message}`, {
        requestId,
        url: config?.url,
        duration,
      });
    }
    return Promise.reject(error);
  }
);

// ==================== Interview APIs ====================

export const interviewApi = {
  create: (data: InterviewCreateRequest) =>
    api.post<Interview>('/interviews', data),

  list: (skip = 0, limit = 20, status_filter?: string, search?: string) => {
    const params = new URLSearchParams();
    params.append('skip', String(skip));
    params.append('limit', String(limit));
    if (status_filter) params.append('status_filter', status_filter);
    if (search) params.append('search', search);
    return api.get<{ items: Interview[]; total: number; page: number; limit: number }>(
      `/interviews?${params.toString()}`
    );
  },

  get: (id: string) =>
    api.get<Interview>(`/interviews/${id}`),

  update: (id: string, data: Partial<InterviewCreateRequest> & { target_output_format?: string[]; status?: string }) =>
    api.patch<Interview>(`/interviews/${id}`, data),

  delete: (id: string) =>
    api.delete(`/interviews/${id}`),

  // Start interview (auto-generate opening question)
  startInterview: (id: string) =>
    api.post<Message>(`/interviews/${id}/start`),

  // Blueprint
  generateBlueprint: (id: string) =>
    api.post<{ blueprint: Blueprint }>(`/interviews/${id}/blueprint/generate`),

  confirmBlueprint: (id: string, adjustments?: Record<string, any>) =>
    api.post(`/interviews/${id}/blueprint/confirm`, { adjustments }),

  saveBlueprint: (id: string, adjustments?: Record<string, any>) =>
    api.post<{ success: boolean; status: string; message: string }>(`/interviews/${id}/blueprint/save`, { adjustments }),

  // Messages
  sendMessage: (id: string, content: string) =>
    api.post<Message>(`/interviews/${id}/messages`, { content }),

  getMessages: (id: string, limit = 50) =>
    api.get<Message[]>(`/interviews/${id}/messages?limit=${limit}`),

  // Streaming message
  sendMessageStream: (id: string, content: string) => {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    const token = localStorage.getItem('access_token');
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    const response = fetch(`${API_BASE_URL}/interviews/${id}/messages/stream`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ content }),
    });
    return response;
  },

  // Structured content
  getStructuredContent: (id: string) =>
    api.get<StructuredContent>(`/interviews/${id}/structured-content`),

  // Complete & Output
  complete: (id: string) =>
    api.post<{ output: Record<string, any> }>(`/interviews/${id}/complete`),

  // Resume from completed state back to confirmation (for "继续访谈")
  resume: (id: string) =>
    api.post<Interview>(`/interviews/${id}/resume`),

  getOutput: (id: string, format = 'json') =>
    api.get<{ interview_id: string; content: any; format: string; generated_at: string }>(
      `/interviews/${id}/output?format=${format}`
    ),

  // Expert Profile & Analysis
  getExpertProfile: (id: string) =>
    api.get<{ interview_id: string; expert_profile: ExpertProfile; is_identified: boolean }>(
      `/interviews/${id}/expert-profile`
    ),

  getLatestAnalysis: (id: string) =>
    api.get<{ interview_id: string; analysis: ContentAnalysis; has_analysis: boolean }>(
      `/interviews/${id}/analysis/latest`
    ),

  // Templates & Export
  listTemplates: () =>
    api.get<{ templates: { id: string; name: string; description: string; icon: string }[] }>(
      '/interviews/templates'
    ),

  render: (id: string, template: string) =>
    api.get<{ interview_id: string; template: string; content: string }>(
      `/interviews/${id}/render?template=${template}`
    ),

  export: (id: string, format: string, template: string) => {
    const url = `/interviews/${id}/export?format=${format}&template=${template}`;
    return api.get(url, { responseType: 'blob' });
  },

  // Report
  generateReport: (id: string, depth: string = 'standard') =>
    api.post<{ analysis_report: Record<string, any>; metadata: Record<string, any> }>(
      `/interviews/${id}/report`,
      { depth }
    ),

  getReport: (id: string, depth?: string) =>
    api.get<{ analysis_report: Record<string, any>; metadata: Record<string, any> }>(
      `/interviews/${id}/report${depth ? `?depth=${depth}` : ''}`
    ),

  exportReport: (id: string, format: string, depth: string = 'standard') => {
    const url = `/interviews/${id}/report/export?format=${format}&depth=${depth}`;
    return api.get(url, { responseType: 'blob' });
  },

  // Timer
  timerStart: (id: string) =>
    api.post<{ status: string; elapsed_seconds: number }>(`/interviews/${id}/timer/start`),

  timerPause: (id: string) =>
    api.post<{ status: string; elapsed_seconds: number }>(`/interviews/${id}/timer/pause`),

  timerResume: (id: string) =>
    api.post<{ status: string; elapsed_seconds: number }>(`/interviews/${id}/timer/resume`),

  timerStatus: (id: string) =>
    api.get<{ status: string; elapsed_seconds: number }>(`/interviews/${id}/timer/status`),

  // Voice Transcription [DEPRECATED] — 请使用 WebSocket 实时语音识别
  voiceTranscribe: (id: string, audio_base64: string, segment_index: number = 0) =>
    api.post<{ transcription: string | null; segment_index: number }>(
      `/interviews/${id}/voice/transcribe`,
      { audio_base64, segment_index }
    ),

  // Round Complete (Voice Mode)
  completeRound: (id: string, transcription: string, notes: string[]) =>
    api.post<{
      refined_answer: string;
      user_message: Message;
      ai_message: Message;
    }>(
      `/interviews/${id}/round/complete`,
      { transcription, notes }
    ),
};

// ==================== Auth APIs ====================

export const authApi = {
  register: (data: { email: string; password: string; full_name?: string }) =>
    api.post<TokenResponse>('/auth/register', data),

  login: (data: { email: string; password: string }) =>
    api.post<TokenResponse>('/auth/login', data),

  getMe: () =>
    api.get<User>('/auth/me'),

  updateMe: (data: { full_name?: string; password?: string }) =>
    api.patch<User>('/auth/me', data),

  // Admin APIs
  listUsers: (skip = 0, limit = 100) =>
    api.get<{ items: User[]; total: number }>(`/auth/admin/users?skip=${skip}&limit=${limit}`),

  getUser: (id: string) =>
    api.get<User>(`/auth/admin/users/${id}`),

  updateUser: (id: string, data: { full_name?: string; email?: string; is_active?: boolean; is_superuser?: boolean; password?: string }) =>
    api.patch<User>(`/auth/admin/users/${id}`, data),

  deleteUser: (id: string) =>
    api.delete(`/auth/admin/users/${id}`),

  // Password Reset
  requestPasswordReset: (email: string) =>
    api.post<{ message: string }>('/auth/password-reset-request', { email }),

  confirmPasswordReset: (token: string, new_password: string) =>
    api.post<{ message: string }>('/auth/password-reset-confirm', { token, new_password }),
};

// ==================== Config APIs ====================

export interface LlmConfig {
  provider: string;
  label: string;
  model: string;
  base_url: string;
  environment: string;
  debug: boolean;
}

export const configApi = {
  get: () => api.get<LlmConfig>('/config'),
  update: (data: {
    default_llm_provider?: string;
    deepseek_model?: string;
    deepseek_api_key?: string;
    deepseek_base_url?: string;
    baidu_speech_app_id?: string;
    baidu_speech_api_key?: string;
    baidu_speech_secret_key?: string;
  }) => api.put('/config', data),
};

// ==================== Text Analysis APIs ====================

export const textAnalysisApi = {
  create: (data: TextAnalysisCreateRequest) =>
    api.post<TextAnalysis>('/text-analysis', data),

  list: (skip = 0, limit = 20) =>
    api.get<{ items: TextAnalysis[]; total: number; page: number; limit: number }>(
      `/text-analysis?skip=${skip}&limit=${limit}`
    ),

  get: (id: string) =>
    api.get<TextAnalysis>(`/text-analysis/${id}`),

  delete: (id: string) =>
    api.delete(`/text-analysis/${id}`),

  export: (id: string, format: string) => {
    const url = `/text-analysis/${id}/export?format=${format}`;
    return api.get(url, { responseType: 'blob' });
  },
};

export default api;
