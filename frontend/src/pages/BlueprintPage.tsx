import { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, CheckCircle, Clock, Target, Sparkles, Mic, MicOff, X } from 'lucide-react';
import { useInterview } from '@/hooks/useInterview';
import { interviewApi } from '@/services/api';
import { logger } from '@/utils/logger';
import type { Blueprint } from '@/types';

export function BlueprintPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { generateBlueprint, isLoading } = useInterview();
  const [blueprint, setBlueprint] = useState<Blueprint | null>(null);
  const [generating, setGenerating] = useState(false);
  const generateInitiatedRef = useRef(false);

  // 录音确认弹窗状态
  const [showRecordModal, setShowRecordModal] = useState(false);
  const [recordEnabled, setRecordEnabled] = useState(true);
  const [audioDevices, setAudioDevices] = useState<MediaDeviceInfo[]>([]);
  const [selectedDevice, setSelectedDevice] = useState('');
  const [deviceLoading, setDeviceLoading] = useState(false);

  useEffect(() => {
    if (id) {
      loadBlueprint();
    }
  }, [id]);

  const loadBlueprint = async () => {
    if (generating || generateInitiatedRef.current) return;
    try {
      const response = await interviewApi.get(id!);
      if (response.data.blueprint && Object.keys(response.data.blueprint).length > 0) {
        setBlueprint(response.data.blueprint as Blueprint);
      } else {
        // 需要生成蓝图
        await handleGenerate();
      }
    } catch (error) {
      logger.error('加载蓝图失败', { error: (error as Error).message });
    }
  };

  const handleGenerate = async () => {
    if (!id || generating || generateInitiatedRef.current) return;
    generateInitiatedRef.current = true;
    setGenerating(true);
    try {
      const bp = await generateBlueprint(id);
      setBlueprint(bp);
    } catch (error) {
      logger.error('生成蓝图失败', { error: (error as Error).message });
      // 失败后允许重试
      generateInitiatedRef.current = false;
    } finally {
      setGenerating(false);
    }
  };

  const handleConfirm = async () => {
    if (!id) return;
    // 枚举设备并打开录音确认弹窗
    setDeviceLoading(true);
    setShowRecordModal(true);
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
  };

  const handleStartInterview = async () => {
    if (!id) return;
    try {
      await interviewApi.confirmBlueprint(id);
      // 保存录音设置到 localStorage，访谈页面读取
      localStorage.setItem(
        'blueprint_record_settings',
        JSON.stringify({
          enabled: recordEnabled,
          deviceId: recordEnabled ? selectedDevice : null,
        })
      );
      if (recordEnabled && selectedDevice) {
        localStorage.setItem('last_mic_device', selectedDevice);
      }
      navigate(`/interviews/${id}/chat`);
    } catch (error) {
      logger.error('确认蓝图失败', { error: (error as Error).message });
    }
  };

  if (generating || isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto mb-4"></div>
          <p className="text-gray-600">AI正在生成访谈蓝图...</p>
        </div>
      </div>
    );
  }

  if (!blueprint) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <p className="text-gray-600 mb-4">蓝图生成失败</p>
          <button
            onClick={handleGenerate}
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
          >
            重新生成
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-8">
      <button
        onClick={() => navigate(-1)}
        className="flex items-center text-gray-500 hover:text-gray-700 mb-6"
      >
        <ArrowLeft className="w-5 h-5 mr-1" />
        返回
      </button>

      <div className="bg-white rounded-xl shadow-sm p-8">
        {/* Header */}
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 bg-primary-100 rounded-lg flex items-center justify-center">
            <Sparkles className="w-5 h-5 text-primary-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">访谈蓝图</h1>
            <p className="text-gray-500">AI为您规划的访谈路径</p>
          </div>
        </div>

        {/* Theme */}
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-2">萃取主题</h2>
          <p className="text-gray-700 bg-gray-50 p-4 rounded-lg">{blueprint.theme}</p>
        </div>

        {/* Value Assessment */}
        {blueprint.value_assessment && (
          <div className="mb-8">
            <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
              <Target className="w-5 h-5 mr-2" />
              价值评估（金木水火土）
            </h2>
            <div className="grid grid-cols-5 gap-4">
              {[
                { key: 'gold', label: '金', name: '高价值', color: 'bg-yellow-100 text-yellow-700' },
                { key: 'wood', label: '木', name: '有难度', color: 'bg-green-100 text-green-700' },
                { key: 'water', label: '水', name: '常使用', color: 'bg-blue-100 text-blue-700' },
                { key: 'fire', label: '火', name: '急需要', color: 'bg-red-100 text-red-700' },
                { key: 'earth', label: '土', name: '覆盖广', color: 'bg-amber-100 text-amber-700' },
              ].map((item) => {
                const score = blueprint.value_assessment[item.key as keyof typeof blueprint.value_assessment] as number;
                const reason = blueprint.value_assessment.reasons?.[item.key];
                return (
                  <div key={item.key} className={`${item.color} rounded-lg p-4 text-center`}>
                    <div className="text-2xl font-bold">{score}</div>
                    <div className="text-sm font-medium">{item.label}·{item.name}</div>
                    {reason && <div className="text-xs mt-1 opacity-75">{reason}</div>}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Six Steps */}
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <Clock className="w-5 h-5 mr-2" />
            六步访谈流程
          </h2>
          <div className="space-y-4">
            {blueprint.six_steps?.map((step, index) => (
              <div key={index} className="border border-gray-200 rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-primary-100 text-primary-600 rounded-full flex items-center justify-center text-sm font-bold">
                      {index + 1}
                    </div>
                    <div>
                      <h3 className="font-semibold text-gray-900">{step.step_name}</h3>
                      <p className="text-sm text-gray-500">{step.duration_min}分钟</p>
                    </div>
                  </div>
                </div>
                
                {step.objectives && (
                  <div className="mb-3">
                    <p className="text-sm text-gray-600">
                      <span className="font-medium">目标：</span>
                      {step.objectives.join('、')}
                    </p>
                  </div>
                )}

                {step.key_questions && (
                  <div className="space-y-2">
                    <p className="text-sm font-medium text-gray-700">预设问题：</p>
                    {step.key_questions.map((q, qIndex) => (
                      <div key={qIndex} className="bg-gray-50 rounded-lg p-3">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="px-2 py-0.5 bg-primary-100 text-primary-700 rounded text-xs">
                            {q.type}
                          </span>
                        </div>
                        <p className="text-gray-800">{q.question}</p>
                        <p className="text-sm text-gray-500 mt-1">{q.purpose}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Strategy */}
        {blueprint.overall_strategy && (
          <div className="mb-8">
            <h2 className="text-lg font-semibold text-gray-900 mb-2">整体策略</h2>
            <p className="text-gray-700 bg-gray-50 p-4 rounded-lg">{blueprint.overall_strategy}</p>
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-4 pt-4 border-t">
          <button
            onClick={handleConfirm}
            className="flex-1 py-3 bg-primary-600 text-white rounded-lg font-semibold hover:bg-primary-700 transition-colors flex items-center justify-center"
          >
            <CheckCircle className="w-5 h-5 mr-2" />
            确认蓝图并开始访谈
          </button>
          <button
            onClick={handleGenerate}
            className="px-6 py-3 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
          >
            重新生成
          </button>
        </div>
      </div>

      {/* 录音确认弹窗 */}
      {showRecordModal && (
        <>
          {/* 遮罩层：仅负责背景，不拦截任何点击事件 */}
          <div className="fixed inset-0 z-50 bg-black/50 pointer-events-none" />
          {/* 弹窗内容层 */}
          <div className="fixed inset-0 z-50 flex items-center justify-center pointer-events-none">
            <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4 overflow-hidden pointer-events-auto">
            {/* Header */}
            <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">录音设置</h3>
              <button
                onClick={() => setShowRecordModal(false)}
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
                  className={`relative w-12 h-7 rounded-full transition-colors ${recordEnabled ? 'bg-primary-600' : 'bg-gray-300'}`}
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
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none"
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
                onClick={() => setShowRecordModal(false)}
                className="flex-1 py-2.5 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 font-medium"
              >
                取消
              </button>
              <button
                onClick={handleStartInterview}
                className="flex-1 py-2.5 bg-primary-600 text-white rounded-lg hover:bg-primary-700 font-medium"
              >
                开始访谈
              </button>
            </div>
          </div>
        </div>
      </>
      )}
    </div>
  );
}
