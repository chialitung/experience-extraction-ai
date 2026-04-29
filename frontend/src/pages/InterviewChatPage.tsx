import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Send, Loader2, User, Bot, ArrowLeft, CheckCircle, BookOpen, AlertTriangle, Wrench, Lightbulb, ChevronDown, ChevronUp, Target, Shield, Sparkles, X, Mic, MicOff, Pause, Play, ArrowRight, StickyNote } from 'lucide-react';
import { useInterview } from '@/hooks/useInterview';
import { interviewApi } from '@/services/api';
import { logger } from '@/utils/logger';
import { InterviewStates } from '@/types';
import type { Message, StructuredContent } from '@/types';
import { useVoiceRecorder } from '@/hooks/useVoiceRecorder';
import { useRealtimeTranscription } from '@/hooks/useRealtimeTranscription';
import { AudioWaveform } from '@/components/AudioWaveform';

export function InterviewChatPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const {
    currentInterview, messages, structuredContent, isLoading, isStreaming,
    expertProfile, latestAnalysis, error: interviewError,
    loadInterview, startInterview, sendMessage, completeInterview,
    loadExpertProfile, loadLatestAnalysis,
    timing, recording,
    startTimer, pauseTimer, resumeTimer, getTimerStatus,
    completeRound,
    setTiming, setRecording,
  } = useInterview();
  
  const [input, setInput] = useState('');
  const [localMessages, setLocalMessages] = useState<Message[]>([]);
  const [sendError, setSendError] = useState<string | null>(null);
  const [isCompleting, setIsCompleting] = useState(false);
  const [localStructured, setLocalStructured] = useState<StructuredContent>({
    steps: [], principles: [], tools: [], risks: [], decisions: [],
  });
  const [expandedThinking, setExpandedThinking] = useState<Record<string, boolean>>({});
  const [showGaps, setShowGaps] = useState(true);
  const [detailModal, setDetailModal] = useState<{
    type: string;
    title: string;
    fields: { label: string; value: string }[];
  } | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const startedRef = useRef(false);
  const timerIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 当前轮次状态（录音模式下使用）
  const [currentRound, setCurrentRound] = useState<{
    transcription: string;
    notes: string[];
  }>({ transcription: '', notes: [] });
  const [isCompletingRound, setIsCompletingRound] = useState(false);

  // 实时语音识别预览（MID_TEXT 中间结果）
  const [realtimePreview, setRealtimePreview] = useState('');

  // 实时语音识别 Hook
  const handleRealtimeResult = useCallback((type: 'MID_TEXT' | 'FIN_TEXT', text: string) => {
    if (type === 'MID_TEXT') {
      // 中间结果：作为灰色预览显示
      setRealtimePreview(text);
    } else if (type === 'FIN_TEXT') {
      // 最终结果：追加到当前轮次转录区，清空预览
      setCurrentRound((prev) => ({
        ...prev,
        transcription: prev.transcription
          ? prev.transcription + ' ' + text
          : text,
      }));
      setRealtimePreview('');
    }
  }, []);

  const realtimeTranscription = useRealtimeTranscription({
    interviewId: id || '',
    isActive: recording.isActive,
    deviceId: recording.deviceId || undefined,
    onResult: handleRealtimeResult,
    onError: (err) => logger.error('实时转录错误', { error: err }),
  });

  // 语音录制 Hook（波形可视化）
  const voiceRecorder = useVoiceRecorder({
    isActive: recording.isActive,
    isPaused: timing.status === 'paused',
    deviceId: recording.deviceId || undefined,
  });

  // 加载访谈时获取计时状态，若访谈活跃但计时未启动则自动开始
  useEffect(() => {
    if (!id) return;
    getTimerStatus(id)
      .then((status) => {
        if (status.status === 'stopped' && currentInterview?.status === 'ACTIVE') {
          startTimer(id).catch(() => {});
        }
      })
      .catch(() => {});
  }, [id, getTimerStatus, startTimer, currentInterview?.status]);

  // 读取蓝图页面设置的录音偏好（一次性，读取后清除）
  useEffect(() => {
    const raw = localStorage.getItem('blueprint_record_settings');
    if (!raw) return;
    try {
      const cfg = JSON.parse(raw);
      if (cfg.enabled) {
        setRecording({
          isActive: true,
          deviceId: cfg.deviceId || null,
        });
      }
      localStorage.removeItem('blueprint_record_settings');
    } catch {
      localStorage.removeItem('blueprint_record_settings');
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 本地计时器驱动：每秒更新已用时长
  const elapsedRef = useRef(timing.elapsedSeconds);
  elapsedRef.current = timing.elapsedSeconds;

  useEffect(() => {
    if (timing.status !== 'running') {
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current);
        timerIntervalRef.current = null;
      }
      return;
    }
    timerIntervalRef.current = setInterval(() => {
      elapsedRef.current += 1;
      setTiming({ elapsedSeconds: elapsedRef.current });
    }, 1000);
    return () => {
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current);
        timerIntervalRef.current = null;
      }
    };
  }, [timing.status, setTiming]);

  useEffect(() => {
    if (id) {
      loadInterview(id);
    }
  }, [id]);

  // 访谈加载完成后，如果没有消息且访谈未结束，自动触发开场问题
  useEffect(() => {
    if (!id || !currentInterview || messages.length > 0 || startedRef.current) return;
    if (currentInterview.status === 'completed') return;

    startedRef.current = true;
    startInterview(id)
      .then(() => {
        // 访谈启动成功后刷新计时状态
        if (id) getTimerStatus(id).catch(() => {});
      })
      .catch((err) => {
        logger.error('启动访谈失败', { error: (err as Error).message });
        startedRef.current = false;
      });
  }, [id, currentInterview, messages.length, startInterview, getTimerStatus]);

  useEffect(() => {
    setLocalMessages(messages);
  }, [messages]);

  useEffect(() => {
    if (structuredContent) {
      setLocalStructured(structuredContent);
    }
  }, [structuredContent]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [localMessages]);

  // 轮询结构化内容、专家画像和分析结果更新
  useEffect(() => {
    if (!id || !currentInterview) return;
    
    const interval = setInterval(async () => {
      try {
        const [structuredRes, profileRes, analysisRes] = await Promise.all([
          interviewApi.getStructuredContent(id),
          interviewApi.getExpertProfile(id).catch(() => null),
          interviewApi.getLatestAnalysis(id).catch(() => null),
        ]);
        setLocalStructured(structuredRes.data);
        if (profileRes?.data?.expert_profile) {
          loadExpertProfile(id);
        }
        if (analysisRes?.data?.analysis) {
          loadLatestAnalysis(id);
        }
      } catch {
        // 忽略错误
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [id, currentInterview, loadExpertProfile, loadLatestAnalysis]);

  // 每次有新消息时，刷新专家画像和分析结果
  useEffect(() => {
    if (!id || messages.length === 0) return;
    loadExpertProfile(id);
    loadLatestAnalysis(id);
  }, [id, messages.length]);

  const handleSend = async () => {
    if (!input.trim() || !id || isLoading || isStreaming || isCompletingRound) return;

    const content = input.trim();
    setInput('');
    setSendError(null);

    // 录音模式：发送的是备注，追加到当前轮次
    if (recording.isActive) {
      setCurrentRound((prev) => ({
        ...prev,
        notes: [...prev.notes, content],
      }));
      return;
    }

    // 非录音模式：保持原有行为
    try {
      await sendMessage(id, content);
    } catch (error: any) {
      logger.error('发送消息失败', { error: error?.message });
      const msg = error?.response?.data?.detail || error?.message || '发送失败，请稍后重试';
      setSendError(msg);
    }
  };

  const handleNextRound = async () => {
    if (!id || isLoading || isStreaming || isCompletingRound) return;
    if (!currentRound.transcription.trim() && currentRound.notes.length === 0) return;

    setIsCompletingRound(true);
    setSendError(null);

    try {
      await completeRound(id, currentRound.transcription, currentRound.notes);
      // 成功后清空当前轮次
      setCurrentRound({ transcription: '', notes: [] });
    } catch (error: any) {
      logger.error('进入下一轮失败', { error: error?.message });
      const detail = error?.response?.data?.detail;
      let msg: string;
      if (Array.isArray(detail)) {
        msg = detail.map((d: any) => d.msg || String(d)).join('; ');
      } else if (typeof detail === 'string') {
        msg = detail;
      } else {
        msg = error?.message || '进入下一轮失败，请稍后重试';
      }
      setSendError(msg);
    } finally {
      setIsCompletingRound(false);
    }
  };

  const handleComplete = async () => {
    if (!id || isCompleting) return;
    setIsCompleting(true);
    try {
      await completeInterview(id);
      navigate(`/interviews/${id}/output`);
    } catch (error) {
      logger.error('完成访谈失败', { error: (error as Error).message });
    } finally {
      setIsCompleting(false);
    }
  };

  const openDetailModal = (type: string, item: any) => {
    const fields: { label: string; value: string }[] = [];
    if (type === 'step') {
      fields.push({ label: '步骤名称', value: item.title || item.name || '未命名' });
      fields.push({ label: '简要描述', value: item.description || item.detail || '' });
      fields.push({ label: '详细操作说明', value: item.details || '暂无详细说明' });
    } else if (type === 'principle') {
      fields.push({ label: '原则名称', value: item.title || item.name || '未命名' });
      fields.push({ label: '核心思想', value: item.description || item.detail || '' });
      fields.push({ label: '适用场景', value: item.application_scenario || '暂无详细说明' });
    } else if (type === 'tool') {
      fields.push({ label: '工具名称', value: item.name || item.title || '未命名' });
      fields.push({ label: '用途说明', value: item.description || item.detail || '' });
      fields.push({ label: '使用方法', value: item.usage_method || '暂无详细说明' });
    } else if (type === 'risk') {
      const riskTypeMap: Record<string, string> = {
        error: '易错点',
        difficulty: '难点',
        overlook: '易忽视',
        high: '高风险',
        medium: '中风险',
        low: '低风险',
      };
      const typeLabel = riskTypeMap[item.type] || item.type || item.name || '未命名';
      fields.push({ label: '风险类型', value: typeLabel });
      fields.push({ label: '风险描述', value: item.description || item.detail || '' });
      fields.push({ label: '预防/应对方法', value: item.prevention || '暂无详细说明' });
    }
    setDetailModal({
      type,
      title: fields[0]?.value || '详情',
      fields: fields.filter(f => f.value),
    });
  };

  const getCurrentStateInfo = () => {
    return InterviewStates.find(s => s.key === currentInterview?.current_state) || InterviewStates[0];
  };

  const getStateProgress = () => {
    const currentIndex = InterviewStates.findIndex(s => s.key === currentInterview?.current_state);
    return ((currentIndex + 1) / InterviewStates.length) * 100;
  };

  const formatTime = (seconds: number) => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  const handleToggleTimer = async () => {
    if (!id) return;
    if (timing.status === 'running') {
      await pauseTimer(id);
    } else if (timing.status === 'paused') {
      await resumeTimer(id);
    }
  };

  const handleToggleRecording = () => {
    setRecording({ isActive: !recording.isActive });
  };

  const handleDeviceChange = (deviceId: string) => {
    localStorage.setItem('last_mic_device', deviceId);
    setRecording({ deviceId });
  };

  return (
    <div className="flex h-screen">
      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="bg-white border-b border-gray-200 px-6 py-4">
          <div className="flex items-center justify-between">
            {/* 左侧：返回 + 主题 + 阶段 */}
            <div className="flex items-center gap-4 flex-1 min-w-0">
              <button
                onClick={() => navigate('/interviews')}
                className="text-gray-500 hover:text-gray-700 flex-shrink-0"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <div className="min-w-0">
                <h2 className="font-semibold text-gray-900 truncate">{currentInterview?.theme || '访谈中...'}</h2>
                <div className="flex items-center gap-2 text-sm text-gray-500">
                  <span>当前阶段：{getCurrentStateInfo().name}</span>
                  <span>·</span>
                  <span>{getCurrentStateInfo().description}</span>
                  {expertProfile?.profile_type && (
                    <>
                      <span>·</span>
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
                        expertProfile.profile_type === 'talkative' ? 'bg-orange-100 text-orange-700' :
                        expertProfile.profile_type === 'quiet' ? 'bg-blue-100 text-blue-700' :
                        expertProfile.profile_type === 'cautious' ? 'bg-purple-100 text-purple-700' :
                        'bg-gray-100 text-gray-600'
                      }`}>
                        <Shield className="w-3 h-3" />
                        {expertProfile.type_label_cn}
                        {expertProfile.confidence > 0 && (
                          <span className="opacity-70">({Math.round(expertProfile.confidence * 100)}%)</span>
                        )}
                      </span>
                    </>
                  )}
                </div>
              </div>
            </div>

            {/* 中间：计时器 + 暂停/恢复 */}
            <div className="flex items-center gap-3 px-4">
              <div className={`text-2xl font-bold tabular-nums ${
                timing.status === 'paused' ? 'text-warning-600' : 'text-gray-900'
              }`}>
                {formatTime(timing.elapsedSeconds)}
              </div>
              {timing.status !== 'stopped' && timing.status !== 'completed' && (
                <button
                  onClick={handleToggleTimer}
                  className={`w-8 h-8 rounded-full flex items-center justify-center transition-colors ${
                    timing.status === 'running'
                      ? 'bg-warning-100 text-warning-600 hover:bg-warning-200'
                      : 'bg-success-100 text-success-600 hover:bg-success-200'
                  }`}
                  title={timing.status === 'running' ? '暂停计时' : '恢复计时'}
                >
                  {timing.status === 'running' ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                </button>
              )}
            </div>

            {/* 右侧：录音控制 + 完成访谈 */}
            <div className="flex items-center gap-3 flex-1 justify-end">
              {/* 录音开关 */}
              <button
                onClick={handleToggleRecording}
                disabled={voiceRecorder.permissionState === 'denied'}
                className={`px-3 py-1.5 rounded-full text-xs font-medium flex items-center gap-1.5 transition-colors ${
                  recording.isActive
                    ? 'bg-red-100 text-red-700 hover:bg-red-200'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                } disabled:opacity-40 disabled:cursor-not-allowed`}
                title={voiceRecorder.permissionState === 'denied' ? '麦克风权限被拒绝' : recording.isActive ? '停止录音' : '开始录音'}
              >
                {recording.isActive ? (
                  <>
                    <span className="relative flex h-2 w-2">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
                    </span>
                    <Mic className="w-3.5 h-3.5" />
                    录音中
                  </>
                ) : (
                  <>
                    <MicOff className="w-3.5 h-3.5" />
                    录音
                  </>
                )}
              </button>

              {/* 设备选择 */}
              {voiceRecorder.devices.length > 0 && (
                <select
                  value={recording.deviceId || ''}
                  onChange={(e) => handleDeviceChange(e.target.value)}
                  className="text-xs border border-gray-200 rounded-md px-2 py-1 bg-white focus:ring-1 focus:ring-primary-500 focus:border-primary-500 outline-none max-w-[140px]"
                  title="选择麦克风"
                >
                  <option value="">默认设备</option>
                  {voiceRecorder.devices.map((d) => (
                    <option key={d.deviceId} value={d.deviceId}>
                      {d.label || `麦克风 ${d.deviceId.slice(0, 6)}...`}
                    </option>
                  ))}
                </select>
              )}

              {/* 完成访谈 */}
              <button
                onClick={handleComplete}
                disabled={isLoading || isStreaming || isCompleting || currentInterview?.current_state === 'completed'}
                className="px-4 py-2 bg-success-500 text-white rounded-lg hover:bg-success-600 disabled:opacity-50 text-sm font-medium flex items-center"
              >
                {isCompleting ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                    正在生成成果...
                  </>
                ) : (
                  <>
                    <CheckCircle className="w-4 h-4 mr-1" />
                    完成访谈
                  </>
                )}
              </button>
            </div>
          </div>
          
          {/* Progress Bar */}
          <div className="mt-3">
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div 
                className="bg-primary-500 h-2 rounded-full transition-all duration-500"
                style={{ width: `${getStateProgress()}%` }}
              />
            </div>
            <div className="flex justify-between mt-1">
              {InterviewStates.slice(0, -1).map((state, index) => (
                <span 
                  key={state.key}
                  className={`text-xs ${
                    index <= InterviewStates.findIndex(s => s.key === currentInterview?.current_state)
                      ? 'text-primary-600 font-medium'
                      : 'text-gray-400'
                  }`}
                >
                  {state.name}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {localMessages.length === 0 && (
            <div className="text-center py-12">
              {isLoading ? (
                <>
                  <Loader2 className="w-12 h-12 text-primary-500 mx-auto mb-4 animate-spin" />
                  <p className="text-gray-600 font-medium">AI正在准备开场问题...</p>
                  <p className="text-gray-400 text-sm mt-1">请稍候，马上开始访谈</p>
                </>
              ) : (
                <>
                  <Bot className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                  <p className="text-gray-500">访谈即将开始，请等待AI生成第一个问题...</p>
                </>
              )}
            </div>
          )}
          
          {localMessages.map((message, index) => (
            <div
              key={message.id || index}
              className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div className={`flex max-w-3xl ${message.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                  message.role === 'user' ? 'bg-primary-100 ml-3' : 'bg-gray-100 mr-3'
                }`}>
                  {message.role === 'user' ? (
                    <User className="w-4 h-4 text-primary-600" />
                  ) : (
                    <Bot className="w-4 h-4 text-gray-600" />
                  )}
                </div>
                <div className="flex flex-col max-w-xl">
                  <div className={`rounded-lg px-4 py-3 ${
                    message.role === 'user' 
                      ? 'bg-primary-600 text-white' 
                      : 'bg-white border border-gray-200 text-gray-800'
                  }`}>
                    {message.question_type && message.role === 'assistant' && (
                      <span className="inline-block px-2 py-0.5 bg-primary-100 text-primary-700 rounded text-xs mb-2">
                        {message.question_type}
                      </span>
                    )}
                    <p className="whitespace-pre-wrap">{message.content}</p>
                  </div>
                  {/* AI消息的Thinking折叠面板 */}
                  {message.role === 'assistant' && message.metadata?.thinking && (
                    <div className="mt-1 ml-0">
                      <button
                        onClick={() => setExpandedThinking(prev => ({
                          ...prev,
                          [message.id || index]: !prev[message.id || index]
                        }))}
                        className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600 transition-colors"
                      >
                        <Sparkles className="w-3 h-3" />
                        <span>为什么问这个问题？</span>
                        {expandedThinking[message.id || index] ? (
                          <ChevronUp className="w-3 h-3" />
                        ) : (
                          <ChevronDown className="w-3 h-3" />
                        )}
                      </button>
                      {expandedThinking[message.id || index] && (
                        <div className="mt-1 bg-gray-50 rounded-lg px-3 py-2 text-xs text-gray-600 border border-gray-100">
                          <div className="mb-1">
                            <span className="font-medium text-gray-700">思考过程：</span>
                            <p className="mt-0.5">{message.metadata.thinking}</p>
                          </div>
                          {message.metadata?.content_analysis && (
                            <div className="mt-2 pt-2 border-t border-gray-200">
                              <span className="font-medium text-gray-700">内容分析：</span>
                              <div className="mt-1 space-y-0.5">
                                <p>颗粒度：{message.metadata.content_analysis.depth}（评分{message.metadata.content_analysis.depth_score}）</p>
                                {message.metadata.content_analysis.gaps?.length > 0 && (
                                  <div>
                                    <span className="text-gray-500">信息缺口：</span>
                                    <ul className="list-disc list-inside text-gray-500">
                                      {message.metadata.content_analysis.gaps.map((gap: string, i: number) => (
                                        <li key={i}>{gap}</li>
                                      ))}
                                    </ul>
                                  </div>
                                )}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
          
          {/* 当前轮次草稿（录音模式下） */}
          {recording.isActive && (currentRound.transcription || currentRound.notes.length > 0 || realtimePreview) && (
            <div className="flex justify-end">
              <div className="flex flex-row-reverse max-w-3xl">
                <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 bg-primary-100 ml-3">
                  <User className="w-4 h-4 text-primary-600" />
                </div>
                <div className="flex flex-col max-w-xl">
                  <div className="rounded-lg px-4 py-3 bg-primary-600 text-white">
                    {/* 已确认的转录内容 */}
                    {currentRound.transcription && (
                      <p className="whitespace-pre-wrap">{currentRound.transcription}</p>
                    )}
                    {/* 实时识别预览（中间结果，灰色） */}
                    {realtimePreview && (
                      <p className={`whitespace-pre-wrap opacity-60 ${currentRound.transcription ? 'mt-1' : ''}`}>
                        {realtimePreview}
                      </p>
                    )}
                    {/* 备注列表 */}
                    {currentRound.notes.length > 0 && (
                      <div className={`space-y-1 ${(currentRound.transcription || realtimePreview) ? 'mt-2 pt-2 border-t border-primary-400' : ''}`}>
                        {currentRound.notes.map((note, i) => (
                          <p key={i} className="text-primary-100 text-sm">
                            <span className="inline-flex items-center gap-1 mr-1">
                              <StickyNote className="w-3 h-3" />
                              备注{i + 1}：
                            </span>
                            {note}
                          </p>
                        ))}
                      </div>
                    )}
                  </div>
                  <span className="text-xs text-gray-400 mt-1 text-right">当前轮次（待提交）</span>
                </div>
              </div>
            </div>
          )}

          {/* AI正在思考中（非流式请求时） */}
          {isLoading && localMessages.length > 0 && localMessages[localMessages.length - 1].role === 'user' && (
            <div className="flex justify-start">
              <div className="flex flex-row">
                <div className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center mr-3">
                  <Bot className="w-4 h-4 text-gray-600" />
                </div>
                <div className="bg-white border border-gray-200 rounded-lg px-4 py-3">
                  <div className="flex items-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin text-primary-600" />
                    <span className="text-gray-500 text-sm">AI正在深入分析您的回答，准备下一个问题...</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {isStreaming && (
            <div className="flex justify-start">
              <div className="flex flex-row">
                <div className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center mr-3">
                  <Bot className="w-4 h-4 text-gray-600" />
                </div>
                <div className="bg-white border border-gray-200 rounded-lg px-4 py-3">
                  <div className="flex items-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin text-primary-600" />
                    <span className="text-gray-500 text-sm">AI正在思考...</span>
                  </div>
                </div>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        {/* Error Banner */}
        {(sendError || interviewError) && (
          <div className="bg-red-50 border-t border-red-200 px-6 py-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm text-red-700">
                <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                <span>{sendError || interviewError}</span>
              </div>
              <button
                onClick={() => { setSendError(null); }}
                className="text-red-400 hover:text-red-600 p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* Input */}
        <div className="bg-white border-t border-gray-200 px-6 py-4">
          {/* 录音模式：下一轮按钮（在波形图上方） */}
          {recording.isActive && (
            <div className="mb-2 flex items-center justify-between">
              <div className="flex items-center gap-2">
                {(currentRound.transcription || realtimePreview) && (
                  <span className="text-xs text-gray-500">
                    当前轮次已转录 {currentRound.transcription.length} 字
                    {realtimePreview && '，识别中...'}
                    {currentRound.notes.length > 0 && `，${currentRound.notes.length} 条备注`}
                  </span>
                )}
              </div>
              <button
                onClick={handleNextRound}
                disabled={
                  isLoading ||
                  isStreaming ||
                  isCompletingRound ||
                  (!currentRound.transcription.trim() && currentRound.notes.length === 0)
                }
                className="px-4 py-1.5 bg-success-500 text-white text-sm rounded-lg hover:bg-success-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center gap-1.5"
              >
                {isCompletingRound ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    整理中...
                  </>
                ) : (
                  <>
                    <ArrowRight className="w-3.5 h-3.5" />
                    下一轮
                  </>
                )}
              </button>
            </div>
          )}

          {/* 音频波形 + 状态提示 */}
          <div className="mb-2">
            <AudioWaveform
              analyser={voiceRecorder.analyser}
              isRecording={voiceRecorder.isRecording}
              hasError={voiceRecorder.hasError}
              height={32}
              barCount={32}
            />
            <div className="flex items-center gap-3 mt-1 min-h-[16px]">
              {realtimeTranscription.isConnecting && (
                <span className="text-xs text-primary-600 flex items-center gap-1">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  正在连接实时语音识别...
                </span>
              )}
              {realtimeTranscription.isConnected && (
                <span className="text-xs text-green-600 flex items-center gap-1">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                  </span>
                  实时语音识别已连接
                </span>
              )}
              {voiceRecorder.permissionState === 'denied' && (
                <span className="text-xs text-red-500">麦克风权限被拒绝，请检查浏览器设置</span>
              )}
              {!voiceRecorder.isSupported && (
                <span className="text-xs text-gray-400">当前浏览器不支持录音功能</span>
              )}
              {voiceRecorder.hasError && recording.isActive && (
                <span className="text-xs text-red-500">录音设备异常，请检查麦克风</span>
              )}
            </div>
          </div>
          <div className="flex gap-4">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder={
                recording.isActive
                  ? '添加备注信息，补充专家回答的内容...'
                  : '请输入您的回答，或开启麦克风直接说话...'
              }
              rows={2}
              disabled={isLoading || isStreaming || isCompletingRound}
              className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none disabled:bg-gray-50"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isLoading || isStreaming || isCompletingRound}
              className="px-6 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <Send className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>

      {/* Right Sidebar - Structured Content */}
      <div className="w-80 bg-gray-50 border-l border-gray-200 overflow-y-auto">
        <div className="p-4">
          <h3 className="font-semibold text-gray-900 mb-4 flex items-center">
            <BookOpen className="w-5 h-5 mr-2" />
            实时萃取
          </h3>

          {/* 信息缺口展示 */}
          {latestAnalysis?.gaps && latestAnalysis.gaps.length > 0 && (
            <div className="mb-4 bg-orange-50 border border-orange-200 rounded-lg p-3">
              <button
                onClick={() => setShowGaps(!showGaps)}
                className="flex items-center justify-between w-full text-sm"
              >
                <span className="flex items-center gap-1 font-medium text-orange-800">
                  <Target className="w-4 h-4" />
                  信息缺口 ({latestAnalysis.gaps.length})
                </span>
                {showGaps ? <ChevronUp className="w-3 h-3 text-orange-600" /> : <ChevronDown className="w-3 h-3 text-orange-600" />}
              </button>
              {showGaps && (
                <ul className="mt-2 space-y-1">
                  {latestAnalysis.gaps.map((gap, i) => (
                    <li key={i} className="text-xs text-orange-700 flex items-start gap-1">
                      <span className="text-orange-400 mt-0.5">•</span>
                      {gap}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {/* 偏离检测提示 */}
          {latestAnalysis?.off_topic && (
            <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-3">
              <div className="flex items-center gap-1 text-sm font-medium text-red-800">
                <AlertTriangle className="w-4 h-4" />
                偏离检测
              </div>
              <p className="text-xs text-red-600 mt-1">{latestAnalysis.off_topic_reason}</p>
            </div>
          )}

          {/* 价值评估（金木水火土） */}
          {currentInterview?.blueprint?.value_assessment && (
            <div className="mb-4 bg-white border border-gray-200 rounded-lg p-3">
              <h4 className="text-sm font-medium text-gray-700 mb-2 flex items-center">
                <Sparkles className="w-4 h-4 mr-1 text-yellow-500" />
                价值评估
              </h4>
              <div className="grid grid-cols-5 gap-1 text-center">
                {Object.entries(currentInterview.blueprint.value_assessment as Record<string, any>)
                  .filter(([k]) => ['金', '木', '水', '火', '土'].includes(k))
                  .map(([key, val]) => {
                    const score = typeof val === 'number' ? val : (typeof val === 'object' ? val?.score || 0 : 0);
                    const color = score >= 4 ? 'text-green-600 bg-green-50' : score >= 3 ? 'text-yellow-600 bg-yellow-50' : 'text-gray-500 bg-gray-50';
                    return (
                      <div key={key} className={`rounded p-1 ${color}`}>
                        <div className="text-xs font-medium">{key}</div>
                        <div className="text-sm font-bold">{score}</div>
                      </div>
                    );
                  })}
              </div>
            </div>
          )}

          {/* Steps */}
          {localStructured.steps && localStructured.steps.length > 0 && (
            <div className="mb-6">
              <h4 className="text-sm font-medium text-gray-700 mb-2 flex items-center">
                <CheckCircle className="w-4 h-4 mr-1" />
                关键步骤
              </h4>
              <div className="space-y-2">
                {localStructured.steps.map((step, index) => (
                  <div
                    key={index}
                    className="bg-white rounded-lg p-3 text-sm cursor-pointer hover:shadow-md hover:ring-1 hover:ring-primary-300 transition-all"
                    onClick={() => openDetailModal('step', step)}
                    title="点击查看详情"
                  >
                    <div className="font-medium text-gray-900">
                      {step.order && <span className="text-primary-600 mr-1">{step.order}.</span>}
                      {step.title || step.name || '未命名步骤'}
                    </div>
                    <div className="text-gray-600 mt-1">{step.description || step.detail || ''}</div>
                    {step.details && (
                      <div className="text-xs text-primary-500 mt-1 flex items-center gap-1">
                        <Sparkles className="w-3 h-3" />
                        点击查看详细说明
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Principles */}
          {localStructured.principles && localStructured.principles.length > 0 && (
            <div className="mb-6">
              <h4 className="text-sm font-medium text-gray-700 mb-2 flex items-center">
                <Lightbulb className="w-4 h-4 mr-1" />
                核心原则
              </h4>
              <div className="space-y-2">
                {localStructured.principles.map((principle, index) => (
                  <div
                    key={index}
                    className="bg-white rounded-lg p-3 text-sm cursor-pointer hover:shadow-md hover:ring-1 hover:ring-primary-300 transition-all"
                    onClick={() => openDetailModal('principle', principle)}
                    title="点击查看详情"
                  >
                    <div className="font-medium text-gray-900">{principle.title || principle.name || '未命名原则'}</div>
                    <div className="text-gray-600 mt-1">{principle.description || principle.detail || ''}</div>
                    {principle.application_scenario && (
                      <div className="text-xs text-primary-500 mt-1 flex items-center gap-1">
                        <Sparkles className="w-3 h-3" />
                        点击查看适用场景
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Tools */}
          {localStructured.tools && localStructured.tools.length > 0 && (
            <div className="mb-6">
              <h4 className="text-sm font-medium text-gray-700 mb-2 flex items-center">
                <Wrench className="w-4 h-4 mr-1" />
                工具/话术
              </h4>
              <div className="space-y-2">
                {localStructured.tools.map((tool, index) => (
                  <div
                    key={index}
                    className="bg-white rounded-lg p-3 text-sm cursor-pointer hover:shadow-md hover:ring-1 hover:ring-primary-300 transition-all"
                    onClick={() => openDetailModal('tool', tool)}
                    title="点击查看详情"
                  >
                    <div className="font-medium text-gray-900">{tool.name || tool.title || '未命名工具'}</div>
                    <div className="text-gray-600 mt-1">{tool.description || tool.detail || ''}</div>
                    {tool.usage_method && (
                      <div className="text-xs text-primary-500 mt-1 flex items-center gap-1">
                        <Sparkles className="w-3 h-3" />
                        点击查看使用方法
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Risks */}
          {localStructured.risks && localStructured.risks.length > 0 && (
            <div className="mb-6">
              <h4 className="text-sm font-medium text-gray-700 mb-2 flex items-center">
                <AlertTriangle className="w-4 h-4 mr-1" />
                风险/易错点
              </h4>
              <div className="space-y-2">
                {localStructured.risks.map((risk, index) => (
                  <div
                    key={index}
                    className="bg-white rounded-lg p-3 text-sm cursor-pointer hover:shadow-md hover:ring-1 hover:ring-primary-300 transition-all"
                    onClick={() => openDetailModal('risk', risk)}
                    title="点击查看详情"
                  >
                    <div className="font-medium text-gray-900">
                      {(() => {
                        const riskTypeMap: Record<string, string> = {
                          error: '易错点',
                          difficulty: '难点',
                          overlook: '易忽视',
                          high: '高风险',
                          medium: '中风险',
                          low: '低风险',
                        };
                        return riskTypeMap[risk.type] || risk.type || risk.name || '风险点';
                      })()}
                    </div>
                    <div className="text-gray-600 mt-1">{risk.description || risk.detail || ''}</div>
                    {risk.prevention && (
                      <div className="text-xs text-primary-500 mt-1 flex items-center gap-1">
                        <Sparkles className="w-3 h-3" />
                        点击查看预防/应对方法
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {(!localStructured.steps?.length && !localStructured.principles?.length && !localStructured.tools?.length && !localStructured.risks?.length) && (
            <div className="text-center py-8 text-gray-400 text-sm">
              访谈进行中，萃取内容将实时显示在这里...
            </div>
          )}
        </div>
      </div>

      {/* Detail Modal */}
      {detailModal && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
          onClick={() => setDetailModal(null)}
        >
          <div
            className="bg-white rounded-xl shadow-xl max-w-lg w-full max-h-[80vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="sticky top-0 bg-white border-b border-gray-100 px-6 py-4 flex items-center justify-between rounded-t-xl">
              <h3 className="font-semibold text-gray-900 text-lg">{detailModal.title}</h3>
              <button
                onClick={() => setDetailModal(null)}
                className="text-gray-400 hover:text-gray-600 p-1 rounded-lg hover:bg-gray-100 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="px-6 py-4 space-y-4">
              {detailModal.fields.map((field, i) => (
                <div key={i}>
                  <div className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">
                    {field.label}
                  </div>
                  <div className="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">
                    {field.value}
                  </div>
                </div>
              ))}
            </div>
            <div className="sticky bottom-0 bg-gray-50 px-6 py-3 border-t border-gray-100 rounded-b-xl flex justify-end">
              <button
                onClick={() => setDetailModal(null)}
                className="px-4 py-2 bg-primary-600 text-white text-sm rounded-lg hover:bg-primary-700 transition-colors"
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
