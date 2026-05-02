import { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, CheckCircle, Clock, Target, Sparkles, Save, X } from 'lucide-react';
import { useInterview } from '@/hooks/useInterview';
import { interviewApi } from '@/services/api';
import { RecordSettingsModal } from '@/components/RecordSettingsModal';
import { logger } from '@/utils/logger';
import type { Blueprint } from '@/types';

export function BlueprintPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { generateBlueprint, isLoading } = useInterview();
  const [blueprint, setBlueprint] = useState<Blueprint | null>(null);
  const [generating, setGenerating] = useState(false);
  const [hasAttemptedLoad, setHasAttemptedLoad] = useState(false);
  const generateInitiatedRef = useRef(false);

  // 录音确认弹窗状态
  const [showRecordModal, setShowRecordModal] = useState(false);

  // 保存蓝图提示
  const [saveToast, setSaveToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

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
    } finally {
      setHasAttemptedLoad(true);
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
    } finally {
      generateInitiatedRef.current = false;
      setGenerating(false);
    }
  };

  const handleConfirm = async () => {
    if (!id) return;
    setShowRecordModal(true);
  };

  const handleStartInterview = async (settings: { enabled: boolean; deviceId: string | null }) => {
    if (!id) return;
    try {
      await interviewApi.confirmBlueprint(id);
      // 保存录音设置到 localStorage，访谈页面读取
      localStorage.setItem(
        'blueprint_record_settings',
        JSON.stringify({
          enabled: settings.enabled,
          deviceId: settings.enabled ? settings.deviceId : null,
        })
      );
      if (settings.enabled && settings.deviceId) {
        localStorage.setItem('last_mic_device', settings.deviceId);
      }
      navigate(`/interviews/${id}/chat`);
    } catch (error) {
      logger.error('确认蓝图失败', { error: (error as Error).message });
    }
  };

  const handleSaveBlueprint = async () => {
    if (!id) return;
    try {
      await interviewApi.saveBlueprint(id);
      setSaveToast({ message: '蓝图已保存', type: 'success' });
      setTimeout(() => {
        setSaveToast(null);
        navigate('/interviews');
      }, 1500);
    } catch (error) {
      logger.error('保存蓝图失败', { error: (error as Error).message });
      setSaveToast({ message: '保存失败，请稍后重试', type: 'error' });
      setTimeout(() => setSaveToast(null), 3000);
    }
  };

  if (!hasAttemptedLoad || generating || isLoading) {
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
            onClick={handleSaveBlueprint}
            className="px-6 py-3 border border-primary-600 text-primary-600 rounded-lg hover:bg-primary-50 transition-colors flex items-center"
          >
            <Save className="w-5 h-5 mr-2" />
            保存蓝图
          </button>
          <button
            onClick={handleGenerate}
            className="px-6 py-3 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
          >
            重新生成
          </button>
        </div>
      </div>

      {/* 保存蓝图提示 */}
      {saveToast && (
        <div className="fixed top-10 left-1/2 -translate-x-1/2 z-50">
          <div
            className={`flex items-center gap-5 pl-3 pr-8 py-6 rounded-2xl shadow-2xl border min-w-[400px] animate-[slideDown_0.3s_ease-out] ${
              saveToast.type === 'success'
                ? 'bg-white border-green-200 shadow-green-100/50'
                : 'bg-white border-red-200 shadow-red-100/50'
            }`}
          >
            <div
              className={`flex items-center justify-center w-14 h-14 rounded-full shrink-0 ${
                saveToast.type === 'success' ? 'bg-green-100' : 'bg-red-100'
              }`}
            >
              <CheckCircle
                className={`w-7 h-7 ${
                  saveToast.type === 'success' ? 'text-green-600' : 'text-red-600'
                }`}
              />
            </div>
            <div className="flex-1">
              <p className="text-lg font-bold text-gray-900">{saveToast.message}</p>
              <p className="text-base text-gray-500 mt-1">
                {saveToast.type === 'success' ? '正在跳转至访谈列表...' : '请检查网络后重试'}
              </p>
            </div>
            <button
              onClick={() => setSaveToast(null)}
              className="text-gray-400 hover:text-gray-600 transition-colors shrink-0 p-1"
            >
              <X className="w-6 h-6" />
            </button>
          </div>
        </div>
      )}

      <RecordSettingsModal
        isOpen={showRecordModal}
        onClose={() => setShowRecordModal(false)}
        onConfirm={(settings) => {
          setShowRecordModal(false);
          handleStartInterview(settings);
        }}
      />
    </div>
  );
}
