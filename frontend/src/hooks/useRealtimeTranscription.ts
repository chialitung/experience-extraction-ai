import { useState, useRef, useEffect, useCallback } from 'react';
import { logger } from '@/utils/logger';

const TARGET_SAMPLE_RATE = 16000;
const FRAME_DURATION_MS = 160; // 百度推荐每 160ms 发送一帧
const FRAME_SAMPLES = Math.floor((TARGET_SAMPLE_RATE * FRAME_DURATION_MS) / 1000); // 2560 samples

function floatTo16BitPCM(input: Float32Array): ArrayBuffer {
  const output = new Int16Array(input.length);
  for (let i = 0; i < input.length; i++) {
    const s = Math.max(-1, Math.min(1, input[i]));
    output[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return output.buffer;
}

function resampleLinear(input: Float32Array, sourceRate: number, targetRate: number): Float32Array {
  if (sourceRate === targetRate) return input;
  const ratio = targetRate / sourceRate;
  const outputLength = Math.floor(input.length * ratio);
  const output = new Float32Array(outputLength);
  for (let i = 0; i < outputLength; i++) {
    const srcIndex = i / ratio;
    const index = Math.floor(srcIndex);
    const frac = srcIndex - index;
    const a = input[index] || 0;
    const b = input[index + 1] || a;
    output[i] = a + (b - a) * frac;
  }
  return output;
}

export interface UseRealtimeTranscriptionOptions {
  interviewId: string;
  isActive: boolean;
  deviceId?: string;
  onResult: (type: 'MID_TEXT' | 'FIN_TEXT', text: string) => void;
  onError?: (error: string) => void;
}

export interface UseRealtimeTranscriptionReturn {
  isConnected: boolean;
  isConnecting: boolean;
  start: () => Promise<void>;
  stop: () => void;
}

/**
 * 实时语音识别 Hook（WebSocket 流式）
 *
 * 功能：
 * - WebSocket 连接到后端 /ws/interviews/{id}/transcribe
 * - Web Audio API 实时采集麦克风 PCM
 * - 重采样到 16kHz、16bit、单声道
 * - 按 160ms/帧 发送音频数据
 * - 接收 MID_TEXT（中间结果）和 FIN_TEXT（最终结果）
 */
export function useRealtimeTranscription(
  options: UseRealtimeTranscriptionOptions
): UseRealtimeTranscriptionReturn {
  const { interviewId, isActive, deviceId, onResult, onError } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const gainRef = useRef<GainNode | null>(null);
  const resampleBufferRef = useRef<Float32Array>(new Float32Array(0));
  const shouldSendRef = useRef(false);

  const buildWsUrl = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const token = localStorage.getItem('access_token') || '';
    return `${protocol}//${window.location.host}/api/v1/interviews/${interviewId}/transcribe?token=${encodeURIComponent(token)}`;
  }, [interviewId]);

  const stop = useCallback(() => {
    shouldSendRef.current = false;

    if (wsRef.current) {
      if (wsRef.current.readyState === WebSocket.OPEN) {
        try {
          wsRef.current.send(JSON.stringify({ action: 'stop' }));
        } catch {
          /* ignore */
        }
        wsRef.current.close();
      }
      wsRef.current = null;
    }

    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }
    if (sourceRef.current) {
      sourceRef.current.disconnect();
      sourceRef.current = null;
    }
    if (gainRef.current) {
      gainRef.current.disconnect();
      gainRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    resampleBufferRef.current = new Float32Array(0);

    setIsConnected(false);
    setIsConnecting(false);
  }, []);

  const start = useCallback(async () => {
    if (!interviewId || isConnecting || isConnected) return;

    setIsConnecting(true);

    try {
      // 1. 获取麦克风（使用用户指定的设备，若无则使用默认设备）
      const constraints: MediaStreamConstraints = {
        audio: deviceId ? { deviceId: { exact: deviceId } } : true,
      };
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      streamRef.current = stream;

      // 2. 创建 AudioContext
      const audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
      audioContextRef.current = audioCtx;
      const source = audioCtx.createMediaStreamSource(stream);
      sourceRef.current = source;

      // 3. 创建 ScriptProcessorNode（bufferSize 4096 是平衡延迟和 CPU 的常用值）
      const bufferSize = 4096;
      const processor = audioCtx.createScriptProcessor(bufferSize, 1, 1);
      processorRef.current = processor;

      // 增益节点（gain=0 避免音频回放到扬声器产生回音）
      const gainNode = audioCtx.createGain();
      gainNode.gain.value = 0;
      gainRef.current = gainNode;

      // 4. 建立 WebSocket
      const ws = new WebSocket(buildWsUrl());
      ws.binaryType = 'arraybuffer';
      wsRef.current = ws;

      ws.onopen = () => {
        logger.info('实时语音识别 WebSocket 已连接');
        setIsConnected(true);
        setIsConnecting(false);
        shouldSendRef.current = true;
      };

      ws.onmessage = (event) => {
        try {
          const raw = event.data as string;
          // 记录原始消息（前200字符），用于调试百度返回格式
          logger.debug('WebSocket 收到消息', { preview: raw.slice(0, 200) });
          const data = JSON.parse(raw);
          if (data.type === 'MID_TEXT' || data.type === 'FIN_TEXT') {
            onResult(data.type, data.text);
          } else if (data.type === 'ERROR') {
            onError?.(data.text);
          }
        } catch (e) {
          logger.error('WebSocket 消息解析失败', { error: (e as Error).message });
        }
      };

      ws.onerror = () => {
        logger.error('实时语音识别 WebSocket 错误');
        onError?.('语音识别连接失败');
      };

      ws.onclose = () => {
        logger.info('实时语音识别 WebSocket 已关闭');
        setIsConnected(false);
        shouldSendRef.current = false;
      };

      // 5. 音频处理：重采样 → PCM → WebSocket
      let frameCount = 0;
      processor.onaudioprocess = (e) => {
        if (!shouldSendRef.current || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
          return;
        }

        const inputData = e.inputBuffer.getChannelData(0);

        // 追加到重采样缓冲区
        const newBuffer = new Float32Array(resampleBufferRef.current.length + inputData.length);
        newBuffer.set(resampleBufferRef.current);
        newBuffer.set(inputData, resampleBufferRef.current.length);
        resampleBufferRef.current = newBuffer;

        const sourceRate = audioCtx.sampleRate;
        // 源采样率下，对应目标 FRAME_SAMPLES 所需的采样点数
        const sourceFrameSize = Math.floor((FRAME_SAMPLES * sourceRate) / TARGET_SAMPLE_RATE);

        // 处理缓冲区中所有完整帧
        while (resampleBufferRef.current.length >= sourceFrameSize) {
          const chunk = resampleBufferRef.current.slice(0, sourceFrameSize);
          resampleBufferRef.current = resampleBufferRef.current.slice(sourceFrameSize);

          const resampled = resampleLinear(chunk, sourceRate, TARGET_SAMPLE_RATE);
          const pcmBuffer = floatTo16BitPCM(resampled);
          wsRef.current.send(pcmBuffer);
          frameCount++;
          if (frameCount <= 5 || frameCount % 50 === 0) {
            logger.debug('发送音频帧', { frameCount, pcmByteLength: pcmBuffer.byteLength });
          }
        }
      };

      // 连接音频图：source → processor → gain → destination
      // destination 必须连接才能触发 onaudioprocess，gain=0 避免实际输出
      source.connect(processor);
      processor.connect(gainNode);
      gainNode.connect(audioCtx.destination);
    } catch (err) {
      logger.error('启动实时语音识别失败', { error: (err as Error).message });
      setIsConnecting(false);
      onError?.((err as Error).message);
    }
  }, [interviewId, isConnecting, isConnected, buildWsUrl, onResult, onError]);

  // 监听 isActive 变化自动启停
  useEffect(() => {
    if (isActive && !isConnected && !isConnecting) {
      start();
    } else if (!isActive && (isConnected || isConnecting)) {
      stop();
    }
  }, [isActive, isConnected, isConnecting, start, stop]);

  return { isConnected, isConnecting, start, stop };
}
