import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Sparkles, Clock, User, FileText, CheckSquare } from 'lucide-react';
import { useInterview } from '@/hooks/useInterview';
import { logger } from '@/utils/logger';

export function InterviewCreatePage() {
  const navigate = useNavigate();
  const { createInterview, isLoading } = useInterview();

  const [formData, setFormData] = useState({
    theme: '',
    background: '',
    expert_role: '',
    expected_duration: 30,
    target_output_format: ['comprehensive'] as string[],
  });
  const [themeError, setThemeError] = useState('');

  const handleThemeChange = (value: string) => {
    setFormData({ ...formData, theme: value });
    if (value.trim() && value.trim().length < 5) {
      setThemeError('主题至少需要5个字符');
    } else {
      setThemeError('');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.theme.trim()) {
      setThemeError('请输入萃取主题');
      return;
    }
    if (formData.theme.trim().length < 5) {
      setThemeError('主题至少需要5个字符');
      return;
    }

    try {
      const interview = await createInterview(formData);
      navigate(`/interviews/${interview.id}/blueprint`);
    } catch (error) {
      logger.error('创建访谈失败', { error: (error as Error).message });
    }
  };

  return (
    <div className="max-w-3xl mx-auto p-8">
      <button
        onClick={() => navigate(-1)}
        className="flex items-center text-gray-500 hover:text-gray-700 mb-6"
      >
        <ArrowLeft className="w-5 h-5 mr-1" />
        返回
      </button>

      <div className="bg-white rounded-xl shadow-sm p-8">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 bg-primary-100 rounded-lg flex items-center justify-center">
            <Sparkles className="w-5 h-5 text-primary-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">创建新访谈</h1>
            <p className="text-gray-500">配置访谈参数，AI将为您生成访谈蓝图</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* 主题 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              萃取主题 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={formData.theme}
              onChange={(e) => handleThemeChange(e.target.value)}
              placeholder="例如：新任销售代表的异议处理技巧"
              className={`w-full px-4 py-3 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent ${
                themeError ? 'border-red-500 focus:ring-red-500' : 'border-gray-300'
              }`}
              required
            />
            {themeError ? (
              <p className="text-sm text-red-500 mt-1">{themeError}</p>
            ) : (
              <p className="text-sm text-gray-500 mt-1">
                明确您想要萃取的经验主题（至少5个字符）
              </p>
            )}
          </div>

          {/* 业务背景 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              业务背景
            </label>
            <textarea
              value={formData.background}
              onChange={(e) => setFormData({ ...formData, background: e.target.value })}
              placeholder="描述该经验所在的业务场景和背景..."
              rows={3}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>

          {/* 专家角色 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              <User className="w-4 h-4 inline mr-1" />
              专家角色
            </label>
            <input
              type="text"
              value={formData.expert_role}
              onChange={(e) => setFormData({ ...formData, expert_role: e.target.value })}
              placeholder="例如：资深销售经理"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>

          {/* 时长 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              <Clock className="w-4 h-4 inline mr-1" />
              期望时长（分钟）
            </label>
            <input
              type="number"
              value={formData.expected_duration}
              onChange={(e) => setFormData({ ...formData, expected_duration: parseInt(e.target.value) || 30 })}
              min={10}
              max={120}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>

          {/* 输出格式 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              <FileText className="w-4 h-4 inline mr-1" />
              目标成果形式
              <span className="text-xs text-gray-400 ml-2 font-normal">（默认全套生成，不可更改）</span>
            </label>
            <div className="p-4 rounded-lg border-2 border-amber-500 bg-amber-50 text-left relative">
              <div className="flex items-center gap-2">
                <CheckSquare className="w-4 h-4 text-amber-600" />
                <div className="font-medium text-gray-900">全套素材包</div>
              </div>
              <div className="text-sm text-gray-600 mt-1 pl-6">一次性生成全部5种形式，满足不同场景使用需求</div>
              <div className="absolute top-2 right-2 text-xs font-bold text-amber-600 bg-amber-100 px-2 py-0.5 rounded">
                默认
              </div>
            </div>

            {/* 详细形式介绍 */}
            <div className="mt-4">
              <div className="text-xs font-medium text-gray-500 mb-2 uppercase tracking-wide">本次访谈将为您生成以下素材</div>
              <div className="grid grid-cols-1 gap-2">
                {[
                  {
                    label: '话术卡',
                    desc: '提炼专家在关键场景下的标准话术与应对策略，可直接用于培训新员工或作为临场参考。',
                    icon: '💬',
                  },
                  {
                    label: '检查表',
                    desc: '将操作步骤转化为可逐项核对的检查清单，确保执行过程不遗漏关键环节，适合标准化作业场景。',
                    icon: '☑️',
                  },
                  {
                    label: '流程图',
                    desc: '梳理决策分支与步骤流转，形成可视化的操作流程图，帮助团队成员快速理解全局与关键节点。',
                    icon: '📊',
                  },
                  {
                    label: '学习卡',
                    desc: '将核心知识点、注意事项和易错点浓缩为速记卡片，便于碎片化学习和快速回顾。',
                    icon: '🎴',
                  },
                  {
                    label: '案例',
                    desc: '整理完整的典型事件经过、决策依据与最终效果，形成可供复盘、研讨和教学使用的案例文档。',
                    icon: '📖',
                  },
                ].map((item) => (
                  <div key={item.label} className="flex items-start gap-3 p-3 rounded-lg bg-gray-50 border border-gray-100">
                    <span className="text-lg shrink-0">{item.icon}</span>
                    <div>
                      <div className="font-medium text-gray-900 text-sm">{item.label}</div>
                      <div className="text-sm text-gray-500 mt-0.5 leading-relaxed">{item.desc}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* 提交 */}
          <div className="pt-4">
            <button
              type="submit"
              disabled={isLoading || !formData.theme.trim()}
              className="w-full py-3 bg-primary-600 text-white rounded-lg font-semibold hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isLoading ? (
                <span className="flex items-center justify-center">
                  <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-2"></div>
                  创建中...
                </span>
              ) : (
                '创建访谈并生成蓝图'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
