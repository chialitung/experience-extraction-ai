import { useState, useRef, useEffect, useCallback } from 'react';
import { logger } from '@/utils/logger';

export interface UseVoiceRecorderOptions {
  /** 用户是否开启了录音（录音开关状态） */
  isActive: boolean;
  /** 计时器是否暂停 */
  isPaused: boolean;
  /** 选定的麦克风设备ID */
  deviceId?: string;
}

export interface UseVoiceRecorderReturn {
  isRecording: boolean;
  isSupported: boolean;
  devices: MediaDeviceInfo[];
  permissionState: 'prompt' | 'granted' | 'denied' | 'unknown';
  /** 用于音频可视化的 AnalyserNode，可直接连接到 Canvas 波形组件 */
  analyser: AnalyserNode | null;
  /** 当前音频电平 (0-255)，用于简单音量指示 */
  audioLevel: number;
  /** 录音是否有错误（如设备断开等） */
  hasError: boolean;
  startRecording: () => Promise<void>;
  stopRecording: () => void;
  refreshDevices: () => Promise<void>;
}

/**
 * 语音录制 Hook（波形可视化版）
 *
 * 职责：设备枚举、麦克风权限管理、音频波形可视化、静音检测。
 * 不再负责音频切片与上传，音频采集由 useRealtimeTranscription 独立处理。
 *
 * 设计要点：
 * - isActive=true && isPaused=false → 自动开始录音（获取音频流 + AnalyserNode）
 * - isActive=false || isPaused=true → 自动停止录音（释放音频流）
 */
export function useVoiceRecorder(options: UseVoiceRecorderOptions): UseVoiceRecorderReturn {
  const { isActive, isPaused, deviceId } = options;

  const [isRecording, setIsRecording] = useState(false);
  const [isSupported, setIsSupported] = useState(false);
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [permissionState, setPermissionState] = useState<'prompt' | 'granted' | 'denied' | 'unknown'>('unknown');
  const [audioLevel, setAudioLevel] = useState(0);
  const [hasError, setHasError] = useState(false);

  const streamRef = useRef<MediaStream | null>(null);
  const isPausedRef = useRef(isPaused);
  const isActiveRef = useRef(isActive);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const rafRef = useRef<number | null>(null);
  const silenceStartRef = useRef<number | null>(null);

  isPausedRef.current = isPaused;
  isActiveRef.current = isActive;

  // 检测浏览器支持
  useEffect(() => {
    setIsSupported(typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia);
  }, []);

  // 检查权限状态
  useEffect(() => {
    if (!navigator.permissions?.query) return;
    navigator.permissions
      .query({ name: 'microphone' as PermissionName })
      .then((status) => {
        setPermissionState(status.state as any);
        status.addEventListener('change', () => {
          setPermissionState(status.state as any);
        });
      })
      .catch(() => {});
  }, []);

  // 组件挂载时立即尝试枚举设备
  useEffect(() => {
    refreshDevices();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /** 枚举音频输入设备 */
  const refreshDevices = useCallback(async () => {
    if (!navigator.mediaDevices?.enumerateDevices) return;
    try {
      const allDevices = await navigator.mediaDevices.enumerateDevices();
      const audioInputs = allDevices.filter((d) => d.kind === 'audioinput');
      setDevices(audioInputs);
    } catch (err) {
      logger.error('枚举音频设备失败', { error: (err as Error).message });
    }
  }, []);

  /** 请求麦克风权限 */
  const ensurePermission = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((t) => t.stop());
      setPermissionState('granted');
      await refreshDevices();
      return true;
    } catch (err) {
      setPermissionState('denied');
      logger.error('麦克风权限请求失败', { error: (err as Error).message });
      return false;
    }
  }, [refreshDevices]);

  /** 启动录音（仅获取音频流 + AnalyserNode） */
  const startRecording = useCallback(async () => {
    if (!isSupported) return;

    // 确保有权限
    if (permissionState !== 'granted') {
      const ok = await ensurePermission();
      if (!ok) return;
    }

    // 清理旧的 audio context
    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
      analyserRef.current = null;
    }
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }

    try {
      const constraints: MediaStreamConstraints = {
        audio: deviceId ? { deviceId: { exact: deviceId } } : true,
      };
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      streamRef.current = stream;
      setHasError(false);

      // 创建音频分析器用于波形可视化
      const audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
      audioContextRef.current = audioCtx;
      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.8;
      source.connect(analyser);
      analyserRef.current = analyser;

      // 音量监测循环（含静默检测：连续5秒无有效音量判定设备异常）
      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      const SILENT_THRESHOLD = 3; // 平均音量低于3视为静默
      const SILENT_DURATION_MS = 5000; // 连续静默5秒触发异常提示

      const updateLevel = () => {
        if (!analyserRef.current) return;
        analyserRef.current.getByteFrequencyData(dataArray);
        // 计算平均音量
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
        const avg = sum / dataArray.length;
        setAudioLevel(Math.round(avg));

        // 静默检测：持续无输入音量的设备可能是选错的设备
        const now = Date.now();
        if (avg < SILENT_THRESHOLD) {
          if (!silenceStartRef.current) silenceStartRef.current = now;
          if (now - silenceStartRef.current >= SILENT_DURATION_MS) {
            setHasError(true);
          }
        } else {
          silenceStartRef.current = null;
          setHasError(false);
        }

        rafRef.current = requestAnimationFrame(updateLevel);
      };
      rafRef.current = requestAnimationFrame(updateLevel);

      setIsRecording(true);
      logger.info('录音开始（波形可视化）', { deviceId });
    } catch (err) {
      logger.error('启动录音失败', { error: (err as Error).message });
      setHasError(true);
      setIsRecording(false);
    }
  }, [isSupported, deviceId, permissionState, ensurePermission]);

  /** 停止录音 */
  const stopRecording = useCallback(() => {
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }

    const stream = streamRef.current;
    if (stream) {
      stream.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }

    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }
    analyserRef.current = null;
    silenceStartRef.current = null;
    setAudioLevel(0);

    setIsRecording(false);
    logger.info('录音停止');
  }, []);

  // 监听 isActive 变化：控制录音总开关
  useEffect(() => {
    if (isActive && !isRecording && !isPaused) {
      startRecording();
    } else if ((!isActive || isPaused) && isRecording) {
      stopRecording();
    }
  }, [isActive, isPaused, isRecording, startRecording, stopRecording]);

  // 组件卸载时清理
  useEffect(() => {
    return () => {
      stopRecording();
    };
  }, [stopRecording]);

  return {
    isRecording,
    isSupported,
    devices,
    permissionState,
    analyser: analyserRef.current,
    audioLevel,
    hasError,
    startRecording,
    stopRecording,
    refreshDevices,
  };
}
