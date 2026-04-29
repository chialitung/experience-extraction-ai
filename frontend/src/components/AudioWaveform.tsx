import { useEffect, useRef } from 'react';

interface AudioWaveformProps {
  /** 音频分析器节点，录音时自动跳动 */
  analyser: AnalyserNode | null;
  /** 是否显示错误状态（红框） */
  hasError?: boolean;
  /** 是否正在录音 */
  isRecording?: boolean;
  /** 组件高度 */
  height?: number;
  /** 柱条数量 */
  barCount?: number;
}

/**
 * 音频波形可视化组件
 *
 * 使用 Canvas 绘制实时音频柱状波形。
 * - 录音正常时：柱条随音量跳动（绿色渐变）
 * - 未录音时：显示静态灰色占位条
 * - 录音异常时：外框变红提醒
 */
export function AudioWaveform({
  analyser,
  hasError = false,
  isRecording = false,
  height = 32,
  barCount = 24,
}: AudioWaveformProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // 处理高分屏
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const draw = () => {
      const w = rect.width;
      const h = rect.height;
      ctx.clearRect(0, 0, w, h);

      const gap = 2;
      const barW = (w - (barCount - 1) * gap) / barCount;

      if (analyser && isRecording) {
        const dataArray = new Uint8Array(analyser.frequencyBinCount);
        analyser.getByteFrequencyData(dataArray);
        // 采样到 barCount 个柱条
        const step = Math.floor(dataArray.length / barCount);

        for (let i = 0; i < barCount; i++) {
          const value = dataArray[i * step] || 0;
          const barH = (value / 255) * h * 0.9;
          const x = i * (barW + gap);
          const y = h - barH;

          // 绿色渐变，音量越大越亮
          const intensity = Math.min(1, value / 200);
          const r = Math.round(34 + (56 - 34) * (1 - intensity));
          const g = Math.round(197 + (230 - 197) * intensity);
          const b = Math.round(94 + (120 - 94) * intensity);
          ctx.fillStyle = `rgb(${r},${g},${b})`;
          ctx.beginPath();
          ctx.roundRect(x, y, barW, barH, 2);
          ctx.fill();
        }
      } else {
        // 静态占位：所有柱条显示最低高度
        const placeholderH = h * 0.15;
        for (let i = 0; i < barCount; i++) {
          const x = i * (barW + gap);
          const y = h - placeholderH;
          ctx.fillStyle = hasError ? '#fca5a5' : '#e5e7eb'; // 错误时浅红，否则浅灰
          ctx.beginPath();
          ctx.roundRect(x, y, barW, placeholderH, 2);
          ctx.fill();
        }
      }

      rafRef.current = requestAnimationFrame(draw);
    };

    draw();

    return () => {
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
  }, [analyser, isRecording, hasError, barCount, height]);

  return (
    <div
      className={`w-full rounded-md overflow-hidden transition-colors ${
        hasError ? 'ring-1 ring-red-400 bg-red-50' : 'bg-gray-50'
      }`}
      style={{ height }}
    >
      <canvas
        ref={canvasRef}
        className="w-full h-full"
        style={{ width: '100%', height: '100%' }}
      />
    </div>
  );
}
