import { useEffect, useState } from 'react';
import { Mic, MicOff, X, Loader2 } from 'lucide-react';
import { logger } from '@/utils/logger';

interface RecordSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (settings: { enabled: boolean; deviceId: string | null }) => void;
  isLoading?: boolean;
  loadingText?: string;
}

export function RecordSettingsModal({ isOpen, onClose, onConfirm, isLoading = false, loadingText = '正在启动访谈...' }: RecordSettingsModalProps) {
  const [recordEnabled, setRecordEnabled] = useState(true);
  const [audioDevices, setAudioDevices] = useState<MediaDeviceInfo[]>([]);
  const [selectedDevice, setSelectedDevice] = useState('');
  const [deviceLoading, setDeviceLoading] = useState(false);

  useEffect(() => {
    if (!isOpen) return;

    setDeviceLoading(true);
    async function enumerateDevices() {
      try {
        if (navigator.mediaDevices?.enumerateDevices) {
          // 先请求权限以获取带 label 的设备列表
          try {
            const tempStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            tempStream.getTracks().forEach((t) => t.stop());
          } catch {
            // 权限被拒绝，仍然尝试枚举（可能获得空label设备）
          }
          const allDevices = await navigator.mediaDevices.enumerateDevices();
          const inputs = allDevices.filter((d) => d.kind === 'audioinput');
          setAudioDevices(inputs);
          // 默认选中上次使用的设备或第一个
          const lastDevice = localStorage.getItem('last_mic_device');
          if (lastDevice && inputs.some((d) => d.deviceId === lastDevice)) {
            setSelectedDevice(lastDevice);
          } else if (inputs.length > 0) {
            setSelectedDevice(inputs[0].deviceId);
          }
        }
      } catch (err) {
        logger.error('枚举录音设备失败', { error: (err as Error).message });
      } finally {
        setDeviceLoading(false);
      }
    }

    enumerateDevices();
  }, [isOpen]);

  const handleConfirm = () => {
    if (recordEnabled && selectedDevice) {
      localStorage.setItem('last_mic_device', selectedDevice);
    }
    onConfirm({
      enabled: recordEnabled,
      deviceId: recordEnabled ? selectedDevice : null,
    });
  };

  if (!isOpen) return null;

  return (
    <>
      {/* 遮罩层 */}
      <div className="fixed inset-0 z-50 bg-black/50 pointer-events-none" />
      {/* 弹窗内容层 */}
      <div className="fixed inset-0 z-50 flex items-center justify-center pointer-events-none">
        <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4 overflow-hidden pointer-events-auto">
          {/* Header */}
          <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
            <h3 className="text-lg font-semibold text-gray-900">录音设置</h3>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 p-1"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Body */}
          <div className="px-6 py-5 space-y-5">
            {/* 启用录音开关 */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-full flex items-center justify-center ${recordEnabled ? 'bg-red-100' : 'bg-gray-100'}`}>
                  {recordEnabled ? <Mic className="w-5 h-5 text-red-600" /> : <MicOff className="w-5 h-5 text-gray-500" />}
                </div>
                <div>
                  <p className="font-medium text-gray-900">启用语音录制</p>
                  <p className="text-sm text-gray-500">
                    {recordEnabled ? '访谈中将自动录音并转录文字' : '仅使用文字输入，可在访谈中随时开启'}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setRecordEnabled(!recordEnabled)}
                disabled={isLoading}
                className={`relative w-12 h-7 rounded-full transition-colors ${recordEnabled ? 'bg-primary-600' : 'bg-gray-300'} disabled:opacity-50 disabled:cursor-not-allowed`}
              >
                <span
                  className={`absolute top-0.5 left-0.5 w-6 h-6 bg-white rounded-full shadow transition-transform ${recordEnabled ? 'translate-x-5' : ''}`}
                />
              </button>
            </div>

            {/* 设备选择 */}
            {recordEnabled && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  选择录音设备
                </label>
                {deviceLoading ? (
                  <div className="text-sm text-gray-400 py-2">正在检测设备...</div>
                ) : audioDevices.length === 0 ? (
                  <div className="text-sm text-orange-600 py-2">未检测到麦克风设备，请确保麦克风已连接并授权</div>
                ) : (
                  <select
                    value={selectedDevice}
                    onChange={(e) => setSelectedDevice(e.target.value)}
                    disabled={isLoading}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {audioDevices.map((d) => (
                      <option key={d.deviceId} value={d.deviceId}>
                        {d.label || `麦克风 ${d.deviceId.slice(0, 8)}...`}
                      </option>
                    ))}
                  </select>
                )}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="px-6 py-4 border-t border-gray-100 flex gap-3">
            <button
              onClick={onClose}
              disabled={isLoading}
              className="flex-1 py-2.5 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 font-medium disabled:opacity-50"
            >
              取消
            </button>
            <button
              onClick={handleConfirm}
              disabled={isLoading}
              className="flex-1 py-2.5 bg-primary-600 text-white rounded-lg hover:bg-primary-700 font-medium disabled:opacity-50 flex items-center justify-center"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  {loadingText}
                </>
              ) : (
                '开始访谈'
              )}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
