import { useCallback } from 'react';
import { useInterviewStore, type TimingState } from '@/store/interviewStore';
import { interviewApi } from '@/services/api';
import type { InterviewCreateRequest, Message } from '@/types';

export function useInterview() {
  const store = useInterviewStore();

  const createInterview = useCallback(async (data: InterviewCreateRequest) => {
    store.setIsLoading(true);
    store.setError(null);
    try {
      const response = await interviewApi.create(data);
      store.setCurrentInterview(response.data);
      return response.data;
    } catch (error: any) {
      store.setError(error.response?.data?.detail || '创建访谈失败');
      throw error;
    } finally {
      store.setIsLoading(false);
    }
  }, []);

  const loadInterview = useCallback(async (id: string) => {
    store.setIsLoading(true);
    store.setError(null);
    try {
      const [interviewRes, messagesRes, structuredRes, profileRes] = await Promise.all([
        interviewApi.get(id),
        interviewApi.getMessages(id),
        interviewApi.getStructuredContent(id),
        interviewApi.getExpertProfile(id).catch(() => ({ data: { expert_profile: null, is_identified: false } })),
      ]);
      store.setCurrentInterview(interviewRes.data);
      store.setMessages(messagesRes.data);
      store.setStructuredContent(structuredRes.data);
      if (profileRes.data?.expert_profile) {
        store.setExpertProfile(profileRes.data.expert_profile);
      }
    } catch (error: any) {
      store.setError(error.response?.data?.detail || '加载访谈失败');
      throw error;
    } finally {
      store.setIsLoading(false);
    }
  }, []);

  const loadExpertProfile = useCallback(async (id: string) => {
    try {
      const response = await interviewApi.getExpertProfile(id);
      if (response.data?.expert_profile) {
        store.setExpertProfile(response.data.expert_profile);
      }
    } catch {
      // 静默失败
    }
  }, []);

  const loadLatestAnalysis = useCallback(async (id: string) => {
    try {
      const response = await interviewApi.getLatestAnalysis(id);
      if (response.data?.analysis) {
        store.setLatestAnalysis(response.data.analysis);
      }
    } catch {
      // 静默失败
    }
  }, []);

  const generateBlueprint = useCallback(async (id: string) => {
    store.setIsLoading(true);
    try {
      const response = await interviewApi.generateBlueprint(id);
      store.setBlueprint(response.data.blueprint);
      return response.data.blueprint;
    } catch (error: any) {
      store.setError(error.response?.data?.detail || '生成蓝图失败');
      throw error;
    } finally {
      store.setIsLoading(false);
    }
  }, []);

  const startInterview = useCallback(async (id: string) => {
    store.setIsLoading(true);
    store.setError(null);
    try {
      const response = await interviewApi.startInterview(id);
      store.addMessage(response.data);
      return response.data;
    } catch (error: any) {
      store.setError(error.response?.data?.detail || '启动访谈失败');
      throw error;
    } finally {
      store.setIsLoading(false);
    }
  }, []);

  const sendMessage = useCallback(async (id: string, content: string) => {
    store.setIsLoading(true);
    store.setError(null);

    // 乐观更新：先添加用户消息
    const tempUserMessage: Message = {
      id: `temp-${Date.now()}`,
      interview_id: id,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    };
    store.addMessage(tempUserMessage);

    try {
      const response = await interviewApi.sendMessage(id, content);
      store.addMessage(response.data);
      // 刷新访谈状态（后端可能已推进阶段）
      const interviewRes = await interviewApi.get(id);
      store.setCurrentInterview(interviewRes.data);
      return response.data;
    } catch (error: any) {
      store.setError(error.response?.data?.detail || '发送消息失败');
      throw error;
    } finally {
      store.setIsLoading(false);
    }
  }, []);

  const sendMessageStream = useCallback(async (id: string, content: string) => {
    store.setIsStreaming(true);
    store.setError(null);

    // 乐观更新用户消息
    const tempUserMessage: Message = {
      id: `temp-user-${Date.now()}`,
      interview_id: id,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    };
    store.addMessage(tempUserMessage);

    try {
      const response = await interviewApi.sendMessageStream(id, content);
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('无法读取流式响应');
      }

      let aiContent = '';
      const tempAiId = `temp-ai-${Date.now()}`;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') {
              // 流结束
              const finalMessage: Message = {
                id: tempAiId,
                interview_id: id,
                role: 'assistant',
                content: aiContent,
                created_at: new Date().toISOString(),
              };
              store.addMessage(finalMessage);
              store.setIsStreaming(false);
              // 刷新访谈状态（后端可能已推进阶段）
              interviewApi.get(id).then(res => store.setCurrentInterview(res.data)).catch(() => {});
              return;
            } else {
              aiContent += data;
              // 更新临时AI消息
              store.updateMessage(tempAiId, { content: aiContent });
            }
          }
        }
      }
    } catch (error: any) {
      store.setError(error.message || '流式发送失败');
      store.setIsStreaming(false);
      throw error;
    }
  }, []);

  const completeInterview = useCallback(async (id: string) => {
    store.setIsLoading(true);
    try {
      const response = await interviewApi.complete(id);
      // 刷新访谈状态
      const interviewRes = await interviewApi.get(id);
      store.setCurrentInterview(interviewRes.data);
      return response.data.output;
    } catch (error: any) {
      store.setError(error.response?.data?.detail || '完成访谈失败');
      throw error;
    } finally {
      store.setIsLoading(false);
    }
  }, []);

  // ==================== Timer ====================

  const startTimer = useCallback(async (id: string) => {
    try {
      const response = await interviewApi.timerStart(id);
      store.setTiming({
        status: response.data.status as TimingState['status'],
        elapsedSeconds: response.data.elapsed_seconds,
      });
      return response.data;
    } catch (error: any) {
      store.setError(error.response?.data?.detail || '开始计时失败');
      throw error;
    }
  }, []);

  const pauseTimer = useCallback(async (id: string) => {
    try {
      const response = await interviewApi.timerPause(id);
      store.setTiming({
        status: response.data.status as TimingState['status'],
        elapsedSeconds: response.data.elapsed_seconds,
      });
      return response.data;
    } catch (error: any) {
      store.setError(error.response?.data?.detail || '暂停计时失败');
      throw error;
    }
  }, []);

  const resumeTimer = useCallback(async (id: string) => {
    try {
      const response = await interviewApi.timerResume(id);
      store.setTiming({
        status: response.data.status as TimingState['status'],
        elapsedSeconds: response.data.elapsed_seconds,
      });
      return response.data;
    } catch (error: any) {
      store.setError(error.response?.data?.detail || '恢复计时失败');
      throw error;
    }
  }, []);

  const getTimerStatus = useCallback(async (id: string) => {
    try {
      const response = await interviewApi.timerStatus(id);
      store.setTiming({
        status: response.data.status as TimingState['status'],
        elapsedSeconds: response.data.elapsed_seconds,
      });
      return response.data;
    } catch (error: any) {
      store.setError(error.response?.data?.detail || '获取计时状态失败');
      throw error;
    }
  }, []);

  // ==================== Voice ====================

  const uploadVoiceSegment = useCallback(async (id: string, audioBase64: string, segmentIndex: number) => {
    const response = await interviewApi.voiceTranscribe(id, audioBase64, segmentIndex);
    return response.data;
  }, []);

  // ==================== Round Complete (Voice Mode) ====================

  const completeRound = useCallback(async (id: string, transcription: string, notes: string[]) => {
    store.setIsLoading(true);
    store.setError(null);
    try {
      const response = await interviewApi.completeRound(id, transcription, notes);
      // 将返回的两条消息加入聊天
      if (response.data.user_message) {
        store.addMessage(response.data.user_message);
      }
      if (response.data.ai_message) {
        store.addMessage(response.data.ai_message);
      }
      // 刷新访谈状态（后端可能已推进阶段）
      const interviewRes = await interviewApi.get(id);
      store.setCurrentInterview(interviewRes.data);
      return response.data;
    } catch (error: any) {
      store.setError(error.response?.data?.detail || '进入下一轮失败');
      throw error;
    } finally {
      store.setIsLoading(false);
    }
  }, []);

  return {
    // State
    currentInterview: store.currentInterview,
    messages: store.messages,
    structuredContent: store.structuredContent,
    blueprint: store.blueprint,
    expertProfile: store.expertProfile,
    latestAnalysis: store.latestAnalysis,
    isLoading: store.isLoading,
    isStreaming: store.isStreaming,
    error: store.error,
    timing: store.timing,
    recording: store.recording,

    // Actions
    createInterview,
    loadInterview,
    startInterview,
    generateBlueprint,
    sendMessage,
    sendMessageStream,
    completeInterview,
    loadExpertProfile,
    loadLatestAnalysis,
    startTimer,
    pauseTimer,
    resumeTimer,
    getTimerStatus,
    uploadVoiceSegment,
    completeRound,
    setTiming: store.setTiming,
    setRecording: store.setRecording,
    reset: store.reset,
  };
}
