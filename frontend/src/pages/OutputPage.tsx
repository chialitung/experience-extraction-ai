import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, FileText, CheckCircle, Printer,
  MessageSquare, ListChecks, GitBranch, GraduationCap, BookOpen,
  Layers, Lightbulb, Wrench, AlertTriangle, FileSpreadsheet,
  ChevronDown, Loader2, BarChart3,
} from 'lucide-react';
import { interviewApi } from '@/services/api';
import { OutputPageSkeleton } from '@/components/Skeleton';
import { logger } from '@/utils/logger';
import type { Interview, StructuredContent } from '@/types';

const OUTPUT_TABS = [
  { key: 'overview', label: '萃取总览', icon: Layers, color: 'text-indigo-600', bg: 'bg-indigo-50' },
  { key: 'script_card', label: '话术卡', icon: MessageSquare, color: 'text-blue-600', bg: 'bg-blue-50' },
  { key: 'checklist', label: '检查表', icon: ListChecks, color: 'text-green-600', bg: 'bg-green-50' },
  { key: 'flowchart', label: '流程图', icon: GitBranch, color: 'text-purple-600', bg: 'bg-purple-50' },
  { key: 'learning_card', label: '学习卡', icon: GraduationCap, color: 'text-orange-600', bg: 'bg-orange-50' },
  { key: 'case_study', label: '案例', icon: BookOpen, color: 'text-red-600', bg: 'bg-red-50' },
];

export function OutputPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [interview, setInterview] = useState<Interview | null>(null);
  const [structuredContent, setStructuredContent] = useState<StructuredContent | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');
  const [templates, setTemplates] = useState<{ id: string; name: string; description: string; icon: string }[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState('script_card');
  const [exporting, setExporting] = useState(false);
  const [showTemplateDropdown, setShowTemplateDropdown] = useState(false);

  useEffect(() => {
    if (id) {
      loadInterview();
    }
  }, [id]);

  // activeTab 切换时同步模板选择
  useEffect(() => {
    if (activeTab !== 'overview' && templates.some((t) => t.id === activeTab)) {
      setSelectedTemplate(activeTab);
    }
  }, [activeTab, templates]);

  // 点击外部关闭模板下拉框
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest('.template-dropdown')) {
        setShowTemplateDropdown(false);
      }
    };
    if (showTemplateDropdown) {
      document.addEventListener('click', handleClick);
      return () => document.removeEventListener('click', handleClick);
    }
  }, [showTemplateDropdown]);

  const loadInterview = async () => {
    try {
      const [interviewRes, structuredRes, templatesRes] = await Promise.all([
        interviewApi.get(id!),
        interviewApi.getStructuredContent(id!),
        interviewApi.listTemplates(),
      ]);
      setInterview(interviewRes.data);
      setStructuredContent(structuredRes.data);
      setTemplates(templatesRes.data.templates);
      // 根据访谈的目标格式设置默认Tab
      const formats = interviewRes.data.target_output_format || ['script_card'];
      // 如果有成果数据，优先显示萃取总览；如果没有，显示第一个可用形式
      const hasOutput = interviewRes.data.final_output && Object.keys(interviewRes.data.final_output).length > 0;
      if (hasOutput && formats.length > 0) {
        setActiveTab('overview');
      } else if (formats.length > 0 && !formats.includes(activeTab)) {
        setActiveTab(formats[0]);
      }
      // 默认选中第一个可用模板
      if (formats.length > 0) {
        setSelectedTemplate(formats[0]);
      }
    } catch (error) {
      logger.error('加载输出页失败', { error: (error as Error).message });
      // 如果结构化内容或模板获取失败，至少加载访谈数据
      try {
        const [response, templatesRes] = await Promise.all([
          interviewApi.get(id!),
          interviewApi.listTemplates(),
        ]);
        setInterview(response.data);
        setTemplates(templatesRes.data.templates);
      } catch (e) {
        logger.error('访谈数据加载失败', { error: (e as Error).message });
      }
    } finally {
      setLoading(false);
    }
  };

  const handleExportFile = async (format: string) => {
    if (!id || !interview) return;
    setExporting(true);
    try {
      const response = await interviewApi.export(id, format, selectedTemplate);
      const blob = response.data as Blob;
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const extMap: Record<string, string> = {
        markdown: 'md',
        docx: 'docx',
        pdf: 'html',
        json: 'json',
      };
      const ext = extMap[format] || format;
      const safeTheme = (interview.theme || '未命名').replace(/[^\w\s\-_]/g, '').slice(0, 30);
      a.download = `${safeTheme}_${selectedTemplate}.${ext}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      logger.error('导出失败', { error: (error as Error).message });
      alert('导出失败，请稍后重试');
    } finally {
      setExporting(false);
    }
  };

  // 判断成果数据结构：嵌套（多形式）还是扁平（单形式兼容）
  const getAvailableOutputs = (): string[] => {
    const available: string[] = [];
    // 萃取总览始终可用（只要有结构化内容或final_output）
    if (structuredContent || interview?.final_output) {
      available.push('overview');
    }
    if (!interview?.final_output) return available;
    const output = interview.final_output;
    const nestedKeys = OUTPUT_TABS.map((t) => t.key);
    const hasNested = nestedKeys.some((k) => k in output);
    if (hasNested) {
      available.push(...nestedKeys.filter((k) => k in output && k !== 'overview'));
    } else {
      // 兼容旧格式：扁平结构视为 script_card
      available.push('script_card');
    }
    return available;
  };

  const getCurrentOutput = () => {
    if (activeTab === 'overview') return null; // overview 不走 final_output
    if (!interview?.final_output) return null;
    const output = interview.final_output;
    const available = getAvailableOutputs();
    if (available.includes('script_card') && !('script_card' in output)) {
      // 旧格式兼容
      return output;
    }
    return output[activeTab] || null;
  };

  const renderOverview = () => {
    if (!structuredContent && !interview?.final_output) {
      return (
        <div className="text-center py-12">
          <FileText className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-500">暂无萃取数据</p>
        </div>
      );
    }
    // 优先使用 structuredContent，回退到 final_output 中的数据
    const sc = structuredContent || { steps: [], principles: [], tools: [], risks: [], decisions: [] };
    const fo = interview?.final_output;
    // 从 final_output 中补充数据（如果 structuredContent 为空）
    const steps = sc.steps?.length ? sc.steps : (fo?.script_card?.steps || fo?.steps || []);
    const principles = sc.principles?.length ? sc.principles : (fo?.learning_card?.principles || []);
    const tools = sc.tools?.length ? sc.tools : (fo?.script_card?.tools || fo?.tools || fo?.learning_card?.tools || []);
    const risks = sc.risks?.length ? sc.risks : (fo?.script_card?.warnings || fo?.risks || fo?.obstacles || []);

    return (
      <div className="space-y-8">
        {/* 访谈主题与价值评估 */}
        <div className="bg-indigo-50 rounded-xl p-6">
          <h3 className="text-lg font-bold text-indigo-900 mb-2">{interview?.theme || '萃取成果'}</h3>
          <p className="text-indigo-700 text-sm">
            本访谈围绕「{interview?.theme}」展开，通过六步萃取法提取了专家的关键经验。
          </p>
        </div>

        {/* 关键步骤 */}
        {steps.length > 0 && (
          <div>
            <h4 className="text-base font-semibold text-gray-900 mb-3 flex items-center">
              <CheckCircle className="w-5 h-5 mr-2 text-green-600" />
              关键步骤（{steps.length}个）
            </h4>
            <div className="space-y-3">
              {steps.map((step: any, index: number) => (
                <div key={index} className="bg-white border rounded-lg p-4">
                  <div className="flex items-start gap-3">
                    <span className="w-7 h-7 bg-green-100 text-green-700 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0">
                      {step.order || step.step || index + 1}
                    </span>
                    <div>
                      <div className="font-medium text-gray-900">{step.title || step.name || step.action || '未命名步骤'}</div>
                      <div className="text-gray-600 text-sm mt-1">{step.description || step.detail || step.script || ''}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 核心原则 */}
        {principles.length > 0 && (
          <div>
            <h4 className="text-base font-semibold text-gray-900 mb-3 flex items-center">
              <Lightbulb className="w-5 h-5 mr-2 text-amber-500" />
              核心原则（{principles.length}个）
            </h4>
            <div className="grid gap-3">
              {principles.map((p: any, index: number) => (
                <div key={index} className="bg-amber-50 rounded-lg p-4 border-l-4 border-amber-400">
                  <h5 className="font-semibold text-amber-900">{p.title || p.name || '原则'}</h5>
                  <p className="text-amber-800 mt-1 text-sm">{p.description || p.detail || ''}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 工具/话术 */}
        {tools.length > 0 && (
          <div>
            <h4 className="text-base font-semibold text-gray-900 mb-3 flex items-center">
              <Wrench className="w-5 h-5 mr-2 text-blue-600" />
              工具/话术（{tools.length}个）
            </h4>
            <div className="grid gap-3">
              {tools.map((t: any, index: number) => (
                <div key={index} className="bg-white border rounded-lg p-4">
                  <h5 className="font-semibold text-gray-900">{t.name || t.title || '未命名工具'}</h5>
                  <p className="text-gray-600 text-sm mt-1">{t.description || t.detail || ''}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 风险/易错点 */}
        {risks.length > 0 && (
          <div>
            <h4 className="text-base font-semibold text-gray-900 mb-3 flex items-center">
              <AlertTriangle className="w-5 h-5 mr-2 text-red-500" />
              风险/易错点（{risks.length}个）
            </h4>
            <div className="grid gap-3">
              {risks.map((r: any, index: number) => {
                const riskTypeMap: Record<string, string> = {
                  error: '易错点',
                  difficulty: '难点',
                  overlook: '易忽视',
                  high: '高风险',
                  medium: '中风险',
                  low: '低风险',
                };
                const typeLabel = riskTypeMap[r.type] || r.type || r.name || '风险点';
                return (
                  <div key={index} className="bg-red-50 rounded-lg p-4 border-l-4 border-red-400">
                    <h5 className="font-semibold text-red-900">{typeLabel}</h5>
                    <p className="text-red-800 mt-1 text-sm">{r.description || r.detail || ''}</p>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {(!steps.length && !principles.length && !tools.length && !risks.length) && (
          <div className="text-center py-12 text-gray-400">
            <FileText className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>本次访谈暂未提取到结构化内容</p>
            <p className="text-sm mt-1">结构化内容在访谈过程中实时积累，完成后自动生成</p>
          </div>
        )}
      </div>
    );
  };

  const renderScriptCard = (data: any) => (
    <div className="space-y-6">
      {data.scenario && <p className="text-gray-600">{data.scenario}</p>}
      {data.steps?.map((step: any, index: number) => (
        <div key={index} className="bg-gray-50 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0">
              {step.step || step.order || index + 1}
            </div>
            <div className="flex-1">
              <h4 className="font-semibold text-gray-900">{step.action || step.title || step.name || `步骤${index + 1}`}</h4>
              {(step.script || step.key_phrase) && (
                <div className="mt-2 bg-white rounded p-3 border-l-4 border-blue-400">
                  <p className="text-gray-700 italic">"{step.script || step.key_phrase}"</p>
                </div>
              )}
              {(step.key_points || step.keyPoint) && (
                <ul className="mt-2 space-y-1">
                  {(step.key_points || [step.keyPoint]).filter(Boolean).map((point: string, i: number) => (
                    <li key={i} className="text-sm text-gray-600 flex items-center">
                      <CheckCircle className="w-4 h-4 text-green-500 mr-2" />
                      {point}
                    </li>
                  ))}
                </ul>
              )}
              {(step.pitfalls || step.warnings) && (
                <div className="mt-2">
                  <p className="text-sm font-medium text-amber-600">⚠ 易错点：</p>
                  <ul className="mt-1 space-y-1">
                    {(step.pitfalls || step.warnings || []).map((pitfall: string, i: number) => (
                      <li key={i} className="text-sm text-gray-600">{pitfall}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        </div>
      ))}
      {data.summary && (
        <div className="bg-blue-50 rounded-lg p-4">
          <h3 className="font-semibold text-blue-900 mb-2">核心要点总结</h3>
          <p className="text-blue-800">{data.summary}</p>
        </div>
      )}
    </div>
  );

  const renderChecklist = (data: any) => (
    <div className="space-y-6">
      {data.checklist?.map((cat: any, ci: number) => (
        <div key={ci} className="bg-white border rounded-lg p-4">
          <h4 className="font-semibold text-gray-900 mb-3">{cat.category}</h4>
          <div className="space-y-2">
            {cat.items?.map((item: any, ii: number) => (
              <div key={ii} className="flex items-center gap-3 p-2 bg-gray-50 rounded">
                <input type="checkbox" className="w-4 h-4 text-green-600 rounded" readOnly />
                <span className="flex-1 text-gray-700">{item.item}</span>
                <span className={`text-xs px-2 py-0.5 rounded ${
                  item.importance === '高' ? 'bg-red-100 text-red-700' :
                  item.importance === '中' ? 'bg-yellow-100 text-yellow-700' :
                  'bg-gray-100 text-gray-600'
                }`}>{item.importance}</span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );

  const renderFlowchart = (data: any) => (
    <div className="space-y-6">
      <div className="bg-white border rounded-lg p-6">
        <div className="flex flex-wrap gap-3 justify-center">
          {data.nodes?.map((node: any, i: number) => (
            <div key={i} className="flex items-center gap-2">
              <div className={`px-4 py-2 rounded-lg border-2 text-sm font-medium ${
                node.type === 'start' ? 'bg-green-50 border-green-300 text-green-800' :
                node.type === 'decision' ? 'bg-purple-50 border-purple-300 text-purple-800 rotate-0' :
                node.type === 'end' ? 'bg-red-50 border-red-300 text-red-800' :
                'bg-blue-50 border-blue-300 text-blue-800'
              }`}>
                {node.label}
              </div>
              {i < (data.nodes?.length || 0) - 1 && (
                <div className="text-gray-400">→</div>
              )}
            </div>
          ))}
        </div>
      </div>
      {data.edges && data.edges.length > 0 && (
        <div className="bg-gray-50 rounded-lg p-4">
          <h4 className="font-semibold text-gray-900 mb-2">流程连线</h4>
          <ul className="space-y-1 text-sm text-gray-600">
            {data.edges.map((edge: any, i: number) => (
              <li key={i}>
                {edge.from} → {edge.to} {edge.label && `（${edge.label}）`}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );

  const renderLearningCard = (data: any) => (
    <div className="space-y-6">
      {data.principles?.length > 0 && (
        <div>
          <h4 className="font-semibold text-gray-900 mb-3">核心原则</h4>
          <div className="grid gap-3">
            {data.principles.map((p: any, i: number) => (
              <div key={i} className="bg-orange-50 rounded-lg p-4 border-l-4 border-orange-400">
                <h5 className="font-semibold text-orange-900">{p.title || p.name || '原则'}</h5>
                <p className="text-orange-800 mt-1 text-sm">{p.description || p.detail || ''}</p>
                {(p.application_scenario || p.scenario) && (
                  <p className="text-orange-600 mt-1 text-xs">适用：{p.application_scenario || p.scenario}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
      {data.tools?.length > 0 && (
        <div>
          <h4 className="font-semibold text-gray-900 mb-3">工具方法</h4>
          <div className="grid gap-3">
            {data.tools.map((t: any, i: number) => (
              <div key={i} className="bg-white border rounded-lg p-4">
                <h5 className="font-semibold text-gray-900">{t.name || t.title || '工具'}</h5>
                <p className="text-gray-600 mt-1 text-sm">{t.description || t.detail || ''}</p>
                {(t.usage || t.usage_method) && <p className="text-gray-500 mt-1 text-xs">用法：{t.usage || t.usage_method}</p>}
              </div>
            ))}
          </div>
        </div>
      )}
      {data.key_concepts?.length > 0 && (
        <div>
          <h4 className="font-semibold text-gray-900 mb-3">关键概念</h4>
          <div className="grid gap-2">
            {data.key_concepts.map((c: any, i: number) => (
              <div key={i} className="flex gap-3 bg-gray-50 rounded-lg p-3">
                <span className="font-semibold text-orange-700 min-w-[80px]">{c.concept || c.name || c.title}</span>
                <span className="text-gray-600 text-sm">{c.explanation || c.description || c.detail || ''}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );

  const renderCaseStudy = (data: any) => (
    <div className="space-y-6">
      {(data.background || data.event_description || data.scenario) && (
        <div className="bg-gray-50 rounded-lg p-4">
          <h4 className="font-semibold text-gray-900 mb-2">案例背景</h4>
          <p className="text-gray-700">{data.background || data.event_description || data.scenario}</p>
        </div>
      )}
      {(data.challenge || data.obstacle || data.difficulty) && (
        <div className="bg-red-50 rounded-lg p-4 border-l-4 border-red-400">
          <h4 className="font-semibold text-red-900 mb-2">面临挑战</h4>
          <p className="text-red-800">{data.challenge || data.obstacle || data.difficulty}</p>
        </div>
      )}
      {(data.process?.length > 0 || data.steps?.length > 0) && (
        <div>
          <h4 className="font-semibold text-gray-900 mb-3">处理过程</h4>
          <div className="space-y-3">
            {(data.process || data.steps || []).map((p: any, i: number) => (
              <div key={i} className="bg-white border rounded-lg p-4">
                <div className="flex items-center gap-2 mb-2">
                  <span className="w-6 h-6 bg-red-100 text-red-600 rounded-full flex items-center justify-center text-xs font-bold">
                    {i + 1}
                  </span>
                  <h5 className="font-semibold text-gray-900">{p.phase || p.title || p.action || p.name || `阶段${i + 1}`}</h5>
                </div>
                <p className="text-gray-600 text-sm">{p.description || p.detail || p.script || ''}</p>
                {(p.key_decision || p.decision) && (
                  <p className="text-gray-500 text-xs mt-2">💡 关键决策：{p.key_decision || p.decision}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
      {(data.result || data.outcome || data.conclusion) && (
        <div className="bg-green-50 rounded-lg p-4 border-l-4 border-green-400">
          <h4 className="font-semibold text-green-900 mb-2">最终结果</h4>
          <p className="text-green-800">{data.result || data.outcome || data.conclusion}</p>
        </div>
      )}
      {(data.lessons?.length > 0 || data.takeaways?.length > 0) && (
        <div>
          <h4 className="font-semibold text-gray-900 mb-3">经验总结</h4>
          <ul className="space-y-2">
            {(data.lessons || data.takeaways || []).map((lesson: string, i: number) => (
              <li key={i} className="flex items-start gap-2 bg-yellow-50 rounded-lg p-3">
                <span className="text-yellow-600 font-bold">{i + 1}.</span>
                <span className="text-gray-700 text-sm">{lesson}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );

  const renderTabContent = () => {
    if (activeTab === 'overview') {
      return renderOverview();
    }
    const data = getCurrentOutput();
    if (!data) {
      return (
        <div className="text-center py-12">
          <FileText className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-500">该形式暂无数据</p>
        </div>
      );
    }
    switch (activeTab) {
      case 'script_card': return renderScriptCard(data);
      case 'checklist': return renderChecklist(data);
      case 'flowchart': return renderFlowchart(data);
      case 'learning_card': return renderLearningCard(data);
      case 'case_study': return renderCaseStudy(data);
      default: return renderScriptCard(data);
    }
  };

  const renderOutput = () => {
    if (!interview?.final_output) {
      return (
        <div className="text-center py-12">
          <FileText className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-500">暂无成果数据</p>
        </div>
      );
    }

    const available = getAvailableOutputs();

    return (
      <div className="space-y-6">
        {/* Title */}
        <div className="text-center pb-6 border-b">
          <h2 className="text-2xl font-bold text-gray-900">{interview.theme}</h2>
          <p className="text-gray-500 mt-1">{available.length > 1 ? `全套素材包 · ${available.length} 种形式` : '萃取成果'}</p>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 overflow-x-auto pb-2">
          {OUTPUT_TABS.filter((t) => available.includes(t.key)).map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors whitespace-nowrap ${
                  isActive
                    ? `${tab.bg} ${tab.color} ring-1 ring-current`
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Tab Content */}
        <div className="bg-white rounded-xl border p-6">
          {renderTabContent()}
        </div>

        {/* Raw JSON for debugging/editing */}
        <div className="border-t pt-6">
          <h3 className="text-sm font-semibold text-gray-500 mb-3">原始数据</h3>
          <pre className="bg-gray-900 text-gray-100 rounded-lg p-4 overflow-x-auto text-xs">
            {(() => {
              try {
                return JSON.stringify(interview.final_output, null, 2);
              } catch {
                return '[数据包含循环引用，无法序列化]';
              }
            })()}
          </pre>
        </div>
      </div>
    );
  };

  if (loading) {
    return <OutputPageSkeleton />;
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
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-success-100 rounded-lg flex items-center justify-center">
              <FileText className="w-5 h-5 text-success-600" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">萃取成果</h1>
              <p className="text-gray-500">访谈完成后自动生成的经验资产</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {/* 生成报告入口 */}
            <button
              onClick={() => navigate(`/interviews/${id}/report`)}
              className="flex items-center gap-2 px-3 py-2 bg-indigo-50 text-indigo-700 border border-indigo-200 rounded-lg text-sm hover:bg-indigo-100 transition-colors"
            >
              <BarChart3 className="w-4 h-4" />
              经验分析报告
            </button>

            {/* 模板选择器 */}
            <div className="relative template-dropdown">
              <button
                onClick={() => setShowTemplateDropdown(!showTemplateDropdown)}
                className="flex items-center gap-2 px-3 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50"
              >
                <FileText className="w-4 h-4" />
                {templates.find((t) => t.id === selectedTemplate)?.name || '话术卡'}
                <ChevronDown className="w-3 h-3" />
              </button>
              {showTemplateDropdown && (
                <div className="absolute right-0 mt-1 w-48 bg-white rounded-lg shadow-lg border z-50">
                  {templates.map((t) => (
                    <button
                      key={t.id}
                      onClick={() => {
                        setSelectedTemplate(t.id);
                        setShowTemplateDropdown(false);
                      }}
                      className={`w-full text-left px-4 py-2.5 text-sm hover:bg-gray-50 first:rounded-t-lg last:rounded-b-lg ${
                        selectedTemplate === t.id ? 'bg-blue-50 text-blue-700 font-medium' : 'text-gray-700'
                      }`}
                    >
                      <div>{t.name}</div>
                      <div className="text-xs text-gray-400 mt-0.5">{t.description}</div>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* 导出格式按钮 */}
            <div className="flex gap-1.5">
              {[
                { key: 'docx', label: 'Word', icon: FileSpreadsheet },
                { key: 'pdf', label: 'PDF', icon: FileText },
              ].map((fmt) => (
                <button
                  key={fmt.key}
                  onClick={() => handleExportFile(fmt.key)}
                  disabled={exporting}
                  className="px-3 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 flex items-center text-sm disabled:opacity-50"
                >
                  {exporting ? (
                    <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />
                  ) : (
                    <fmt.icon className="w-3.5 h-3.5 mr-1" />
                  )}
                  {fmt.label}
                </button>
              ))}
              <button
                onClick={() => window.print()}
                className="px-3 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 flex items-center text-sm"
              >
                <Printer className="w-3.5 h-3.5 mr-1" />
                打印
              </button>
            </div>
          </div>
        </div>

        {renderOutput()}
      </div>
    </div>
  );
}
