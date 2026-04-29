import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, FileText, Loader2, BookOpen,
  ChevronDown, Printer, FileCode, FileSpreadsheet, Sparkles,
  BarChart3, Lightbulb, AlertTriangle, Wrench, Target,
  CheckCircle, Layers, MessageSquare, ListChecks, GitBranch,
  GraduationCap,
} from 'lucide-react';
import { interviewApi } from '@/services/api';
import { OutputPageSkeleton } from '@/components/Skeleton';
import { logger } from '@/utils/logger';

const DEPTH_OPTIONS = [
  { key: 'brief', label: '简要版', desc: '800-1200字，聚焦核心结论', icon: Layers },
  { key: 'standard', label: '标准版', desc: '2000-3000字，完整分析', icon: BookOpen },
  { key: 'deep', label: '深度版', desc: '4000-6000字，含推导过程', icon: BarChart3 },
];

// 已生成报告的展示优先级：深度版 > 标准版 > 简要版
const DEPTH_PRIORITY = ['deep', 'standard', 'brief'];

const getGeneratedDepths = (interview: any): string[] => {
  const reports = interview?.final_output?.analysis_reports || {};
  return DEPTH_PRIORITY.filter((d) => d in reports);
};

const EXPORT_FORMATS = [
  { key: 'markdown', label: 'MD', icon: FileCode },
  { key: 'docx', label: 'Word', icon: FileSpreadsheet },
  { key: 'pdf', label: 'PDF', icon: FileText },
  { key: 'json', label: 'JSON', icon: FileCode },
];

const OUTPUT_TABS = [
  { key: 'overview', label: '萃取总览', icon: Layers, color: 'text-indigo-600', bg: 'bg-indigo-50' },
  { key: 'script_card', label: '话术卡', icon: MessageSquare, color: 'text-blue-600', bg: 'bg-blue-50' },
  { key: 'checklist', label: '检查表', icon: ListChecks, color: 'text-green-600', bg: 'bg-green-50' },
  { key: 'flowchart', label: '流程图', icon: GitBranch, color: 'text-purple-600', bg: 'bg-purple-50' },
  { key: 'learning_card', label: '学习卡', icon: GraduationCap, color: 'text-orange-600', bg: 'bg-orange-50' },
  { key: 'case_study', label: '案例', icon: BookOpen, color: 'text-red-600', bg: 'bg-red-50' },
];

interface ReportSection {
  key: string;
  title: string;
  icon: React.ElementType;
  content?: string;
}

interface ReportPageProps {
  defaultView?: 'materials' | 'report';
}

export function ReportPage({ defaultView = 'report' }: ReportPageProps = {}) {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [interview, setInterview] = useState<any>(null);
  const [structuredContent, setStructuredContent] = useState<any>(null);
  const [report, setReport] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [selectedDepth, setSelectedDepth] = useState('standard');
  const [showDepthDropdown, setShowDepthDropdown] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [activeSection, setActiveSection] = useState<string | null>(null);

  // 顶部视图切换：访谈素材包（默认）vs 经验分析报告
  const [topView, setTopView] = useState<'materials' | 'report'>(defaultView);
  const [activeTab, setActiveTab] = useState('overview');
  const [showTabDropdown, setShowTabDropdown] = useState(false);

  useEffect(() => {
    if (id) {
      loadData();
    }
  }, [id]);

  // 点击外部关闭下拉框
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest('.depth-dropdown')) {
        setShowDepthDropdown(false);
      }
    };
    if (showDepthDropdown) {
      document.addEventListener('click', handleClick);
      return () => document.removeEventListener('click', handleClick);
    }
  }, [showDepthDropdown]);

  // 点击外部关闭Tab下拉框
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest('.tab-dropdown')) {
        setShowTabDropdown(false);
      }
    };
    if (showTabDropdown) {
      document.addEventListener('click', handleClick);
      return () => document.removeEventListener('click', handleClick);
    }
  }, [showTabDropdown]);

  const loadData = async (targetDepth?: string) => {
    setLoading(true);
    try {
      // 先获取访谈数据，用于判断哪些版本已生成
      const interviewRes = await interviewApi.get(id!);
      setInterview(interviewRes.data);

      // 确定要加载的版本
      let depthToLoad = targetDepth;
      if (!depthToLoad) {
        // 初始加载：按优先级自动选择已生成的版本（深度版 > 标准版 > 简要版）
        const generated = getGeneratedDepths(interviewRes.data);
        if (generated.length > 0) {
          depthToLoad = generated[0];
        }
      }
      if (depthToLoad) {
        setSelectedDepth(depthToLoad);
      }

      // 并行加载报告和结构化内容
      const [reportRes, structuredRes] = await Promise.allSettled([
        depthToLoad ? interviewApi.getReport(id!, depthToLoad) : interviewApi.getReport(id!),
        interviewApi.getStructuredContent(id!),
      ]);

      if (reportRes.status === 'fulfilled') {
        setReport(reportRes.value.data);
        if (reportRes.value.data.metadata?.depth) {
          setSelectedDepth(reportRes.value.data.metadata.depth);
        }
      } else {
        // 指定深度没有报告，进入空状态
        setReport(null);
      }

      if (structuredRes.status === 'fulfilled') {
        setStructuredContent(structuredRes.value.data);
      }
    } catch (error) {
      logger.error('加载数据失败', { error: (error as Error).message });
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateReport = async (depth?: string) => {
    if (!id) return;
    // 防御：若 depth 不是字符串（如 React 合成事件对象被直接传入），忽略它
    const targetDepth = typeof depth === 'string' && depth ? depth : selectedDepth;
    setGenerating(true);
    try {
      const response = await interviewApi.generateReport(id, targetDepth);
      setReport(response.data);
      if (response.data.metadata?.depth) {
        setSelectedDepth(response.data.metadata.depth);
      }
      // 刷新 interview 数据，使下拉菜单中的"已生成"标记更新
      const interviewRes = await interviewApi.get(id);
      setInterview(interviewRes.data);
    } catch (error: any) {
      const status = error.response?.status;
      // 强制将 detail 转为字符串，避免传入对象导致 logger / alert 序列化异常
      const rawDetail = error.response?.data?.detail;
      const detail =
        typeof rawDetail === 'string'
          ? rawDetail
          : Array.isArray(rawDetail)
            ? rawDetail.map((d: any) => (typeof d === 'string' ? d : JSON.stringify(d))).join('; ')
            : typeof rawDetail === 'object' && rawDetail !== null
              ? JSON.stringify(rawDetail)
              : error.message || '请稍后重试';
      logger.error('生成报告失败', { status, detail: String(detail).slice(0, 500), targetDepth });
      alert(`生成报告失败${status ? ` (HTTP ${status})` : ''}：${detail}`);
    } finally {
      setGenerating(false);
    }
  };

  const handleExport = async (format: string) => {
    if (!id || !interview) return;
    setExporting(true);
    try {
      let response;
      let depthLabel = '';
      if (topView === 'report') {
        response = await interviewApi.exportReport(id, format, selectedDepth);
        depthLabel = `_${selectedDepth}`;
      } else {
        response = await interviewApi.export(id, format, activeTab);
        depthLabel = `_${activeTab}`;
      }
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
      a.download = `${safeTheme}${depthLabel}.${ext}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (error: any) {
      let msg = '导出失败';
      if (error.response) {
        const status = error.response.status;
        msg = `导出失败 (HTTP ${status})`;
        if (error.response.data instanceof Blob) {
          try {
            const text = await error.response.data.text();
            msg += `\n${text.slice(0, 200)}`;
          } catch {
            /* ignore */
          }
        } else if (typeof error.response.data === 'string') {
          msg += `\n${error.response.data.slice(0, 200)}`;
        }
      } else if (error.request) {
        msg = '导出失败：服务器未响应，请检查网络连接';
      } else {
        msg = `导出失败：${error.message || '未知错误'}`;
      }
      logger.error('导出失败', { error: error.message, status: error.response?.status });
      alert(msg);
    } finally {
      setExporting(false);
    }
  };

  // ==================== 萃取成果渲染逻辑 ====================

  const getAvailableOutputs = (): string[] => {
    const available: string[] = [];
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
      available.push('script_card');
    }
    return available;
  };

  const getCurrentOutput = () => {
    if (activeTab === 'overview') return null;
    if (!interview?.final_output) return null;
    const output = interview.final_output;
    if ('script_card' in output && !('script_card' in output)) {
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
    const sc = structuredContent || { steps: [], principles: [], tools: [], risks: [], decisions: [] };
    const fo = interview?.final_output;
    const steps = sc.steps?.length ? sc.steps : (fo?.script_card?.steps || fo?.steps || []);
    const principles = sc.principles?.length ? sc.principles : (fo?.learning_card?.principles || []);
    const tools = sc.tools?.length ? sc.tools : (fo?.script_card?.tools || fo?.tools || fo?.learning_card?.tools || []);
    const risks = sc.risks?.length ? sc.risks : (fo?.script_card?.warnings || fo?.risks || fo?.obstacles || []);

    return (
      <div className="space-y-8">
        <div className="bg-indigo-50 rounded-xl p-6">
          <h3 className="text-lg font-bold text-indigo-900 mb-2">{interview?.theme || '萃取成果'}</h3>
          <p className="text-indigo-700 text-sm">
            本访谈围绕「{interview?.theme}」展开，通过六步萃取法提取了专家的关键经验。
          </p>
        </div>

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

        {risks.length > 0 && (
          <div>
            <h4 className="text-base font-semibold text-gray-900 mb-3 flex items-center">
              <AlertTriangle className="w-5 h-5 mr-2 text-red-500" />
              风险/易错点（{risks.length}个）
            </h4>
            <div className="grid gap-3">
              {risks.map((r: any, index: number) => {
                const riskTypeMap: Record<string, string> = {
                  error: '易错点', difficulty: '难点', overlook: '易忽视',
                  high: '高风险', medium: '中风险', low: '低风险',
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
                      <CheckCircle className="w-4 h-4 text-green-500 mr-2" />{point}
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
                node.type === 'decision' ? 'bg-purple-50 border-purple-300 text-purple-800' :
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
              <li key={i}>{edge.from} → {edge.to} {edge.label && `（${edge.label}）`}</li>
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
                  <span className="w-6 h-6 bg-red-100 text-red-600 rounded-full flex items-center justify-center text-xs font-bold">{i + 1}</span>
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
    if (activeTab === 'overview') return renderOverview();
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

  const renderMaterialsView = () => {
    const available = getAvailableOutputs();
    return (
      <div className="space-y-6">
        <div className="text-center pb-6 border-b">
          <h2 className="text-2xl font-bold text-gray-900">{interview?.theme}</h2>
          <p className="text-gray-500 mt-1">访谈素材包 · {available.length > 0 ? available.length : 0} 种形式</p>
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

        {/* 原始数据 */}
        {interview?.final_output && (
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
        )}
      </div>
    );
  };

  // ==================== 经验分析报告渲染逻辑 ====================

  const getReportSections = (): ReportSection[] => {
    if (!report?.analysis_report) return [];
    const ar = report.analysis_report;
    return [
      { key: 'executive_summary', title: '执行摘要', icon: Sparkles, content: ar.executive_summary },
      { key: 'case_background', title: '案例背景', icon: FileText, content: ar.case_background },
      { key: 'methodology_framework', title: '方法论框架', icon: Target, content: ar.methodology_framework },
      { key: 'key_steps_analysis', title: '关键步骤详解', icon: CheckCircle, content: ar.key_steps_analysis },
      { key: 'decision_logic_analysis', title: '决策逻辑深度分析', icon: Lightbulb, content: ar.decision_logic_analysis },
      { key: 'obstacles_and_risks', title: '风险与挑战分析', icon: AlertTriangle, content: ar.obstacles_and_risks },
      { key: 'tools_and_scripts', title: '工具与话术清单', icon: Wrench, content: ar.tools_and_scripts },
      { key: 'application_guidance', title: '应用建议', icon: Target, content: ar.application_guidance },
      { key: 'value_assessment', title: '价值评估', icon: BarChart3, content: ar.value_assessment },
      { key: 'lessons_learned', title: '可迁移的经验教训', icon: Lightbulb, content: ar.lessons_learned },
      { key: 'references', title: '相关概念与理论引用', icon: BookOpen, content: ar.references },
    ].filter((s) => typeof s.content === 'string' && s.content.trim().length > 0);
  };

  const renderMarkdownContent = (content: string) => {
    let html = content
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
    html = html.replace(/^### (.*$)/gim, '<h3 class="text-lg font-bold text-gray-900 mt-4 mb-2">$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2 class="text-xl font-bold text-gray-900 mt-6 mb-3">$1</h2>');
    html = html.replace(/^# (.*$)/gim, '<h1 class="text-2xl font-bold text-gray-900 mt-8 mb-4">$1</h1>');
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/__(.*?)__/g, '<strong>$1</strong>');
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
    html = html.replace(/^- (.*$)/gim, '<li class="ml-4 text-gray-700">$1</li>');
    html = html.replace(/^\d+\. (.*$)/gim, '<li class="ml-4 text-gray-700">$1</li>');
    html = html.replace(/^> (.*$)/gim, '<blockquote class="border-l-4 border-indigo-300 pl-4 italic text-gray-600 my-3">$1</blockquote>');
    html = html.replace(/```([\s\S]*?)```/g, '<pre class="bg-gray-900 text-gray-100 rounded-lg p-4 overflow-x-auto text-sm my-3"><code>$1</code></pre>');
    html = html.replace(/`([^`]+)`/g, '<code class="bg-gray-100 text-red-600 px-1.5 py-0.5 rounded text-sm">$1</code>');
    html = html.replace(/\n\n/g, '</p><p class="text-gray-700 leading-relaxed my-2">');
    html = '<p class="text-gray-700 leading-relaxed my-2">' + html + '</p>';
    html = html.replace(/<p class="text-gray-700 leading-relaxed my-2"><\/p>/g, '');
    html = html.replace(/<p class="text-gray-700 leading-relaxed my-2"><(h[123]|blockquote|pre|li)/g, '<$1');
    html = html.replace(/<(\/h[123]|\/blockquote|\/pre|\/li)><\/p>/g, '<$1>');
    return { __html: html };
  };

  const renderReportView = () => {
    const sections = getReportSections();
    const hasReport = sections.length > 0;

    if (!hasReport) {
      const currentDepth = DEPTH_OPTIONS.find((d) => d.key === selectedDepth);
      const currentDepthLabel = currentDepth?.label || '标准版';
      const generatedDepths = getGeneratedDepths(interview);
      const hasAnyReport = generatedDepths.length > 0;
      return (
        <div className="text-center py-16">
          <BookOpen className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-gray-700 mb-2">
            {hasAnyReport ? `尚未生成${currentDepthLabel}` : '暂无分析报告'}
          </h3>
          <p className="text-gray-500 mb-2 max-w-md mx-auto">
            {hasAnyReport
              ? `您已生成 ${generatedDepths.map((d) => DEPTH_OPTIONS.find((o) => o.key === d)?.label).join('、')}，可切换查看。`
              : '基于本次访谈的所有内容，AI 可以为您生成一份系统性的经验分析报告。'}
          </p>
          <p className="text-sm text-gray-400 mb-8 max-w-md mx-auto">
            {currentDepth?.desc}
          </p>
          <button
            onClick={() => handleGenerateReport()}
            disabled={generating}
            className="flex items-center gap-2 px-8 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 mx-auto"
          >
            {generating ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Sparkles className="w-4 h-4" />
            )}
            {generating ? '正在生成报告，请稍候...' : `生成${currentDepthLabel}报告`}
          </button>
        </div>
      );
    }

    return (
      <div className="space-y-6">
        {/* 生成状态提示 */}
        {generating && (
          <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-4 flex items-center gap-3">
            <Loader2 className="w-5 h-5 text-indigo-600 animate-spin" />
            <div>
              <p className="font-medium text-indigo-800">
                正在为您生成{DEPTH_OPTIONS.find((d) => d.key === selectedDepth)?.label || '报告'}...
              </p>
              <p className="text-sm text-indigo-600">请稍候，AI 正在基于访谈内容进行分析</p>
            </div>
          </div>
        )}

        {!generating && report?.metadata?.depth && report.metadata.depth !== selectedDepth && (
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0" />
              <p className="font-medium text-amber-800">
                当前报告为{DEPTH_OPTIONS.find((d) => d.key === report.metadata.depth)?.label || ''}，
                如需查看{DEPTH_OPTIONS.find((d) => d.key === selectedDepth)?.label || ''}请点击重新生成
              </p>
            </div>
            <button
              onClick={() => handleGenerateReport()}
              disabled={generating}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-600 text-white rounded-md hover:bg-amber-700 disabled:opacity-50 text-sm flex-shrink-0"
            >
              <Sparkles className="w-3.5 h-3.5" />
              重新生成
            </button>
          </div>
        )}

        {/* 访谈主题 */}
        <div className="text-center pb-6 border-b">
          <h2 className="text-2xl font-bold text-gray-900">{interview?.theme}</h2>
          <div className="flex items-center justify-center gap-4 mt-2 text-sm text-gray-500">
            <span className="flex items-center gap-1">
              <Layers className="w-4 h-4" />
              {DEPTH_OPTIONS.find((d) => d.key === selectedDepth)?.label || '标准版'}
            </span>
            <span>·</span>
            <span>约 {report.metadata?.word_count || 0} 字</span>
            <span>·</span>
            <span>{report.metadata?.generated_at?.slice(0, 10) || ''}</span>
          </div>
        </div>

        {/* 重新生成按钮 */}
        <div className="flex justify-start">
          <button
            onClick={() => handleGenerateReport()}
            disabled={generating}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 text-sm"
          >
            {generating ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Sparkles className="w-4 h-4" />
            )}
            {generating ? '生成中...' : '重新生成报告'}
          </button>
        </div>

        {/* 目录导航 */}
        <div className="bg-gray-50 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">目录</h3>
          <div className="flex flex-wrap gap-2">
            {sections.map((section) => (
              <button
                key={section.key}
                onClick={() => {
                  setActiveSection(section.key);
                  document.getElementById(`section-${section.key}`)?.scrollIntoView({ behavior: 'smooth' });
                }}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors ${
                  activeSection === section.key
                    ? 'bg-indigo-100 text-indigo-700'
                    : 'bg-white text-gray-600 hover:bg-gray-100'
                }`}
              >
                <section.icon className="w-3.5 h-3.5" />
                {section.title}
              </button>
            ))}
          </div>
        </div>

        {/* 报告正文 */}
        <div className="space-y-8">
          {sections.map((section) => (
            <div
              key={section.key}
              id={`section-${section.key}`}
              className="scroll-mt-4"
            >
              <div className="flex items-center gap-2 mb-4">
                <div className="w-8 h-8 bg-indigo-100 rounded-lg flex items-center justify-center">
                  <section.icon className="w-4 h-4 text-indigo-600" />
                </div>
                <h3 className="text-lg font-bold text-gray-900">{section.title}</h3>
              </div>
              <div
                className="prose prose-indigo max-w-none"
                dangerouslySetInnerHTML={renderMarkdownContent(section.content || '')}
              />
            </div>
          ))}
        </div>


      </div>
    );
  };

  if (loading) {
    return <OutputPageSkeleton />;
  }

  return (
    <div className="max-w-5xl mx-auto p-8">
      <button
        onClick={() => navigate(-1)}
        className="flex items-center text-gray-500 hover:text-gray-700 mb-6"
      >
        <ArrowLeft className="w-5 h-5 mr-1" />
        返回
      </button>

      <div className="bg-white rounded-xl shadow-sm p-8">
        {/* Header */}
        <div className="mb-8">
          {/* 第一行：操作按钮 */}
          <div className="flex items-center justify-between flex-wrap gap-3 mb-6">
            {/* 左侧：视图切换 + 深度选择 */}
            <div className="flex items-center gap-3 flex-wrap">
              {/* 顶部视图切换 */}
              <div className="flex rounded-lg border overflow-hidden">
                <button
                  onClick={() => setTopView('materials')}
                  className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium transition-colors ${
                    topView === 'materials'
                      ? 'bg-indigo-600 text-white'
                      : 'bg-white text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  <FileText className="w-4 h-4" />
                  访谈素材包
                </button>
                <button
                  onClick={() => setTopView('report')}
                  className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium transition-colors ${
                    topView === 'report'
                      ? 'bg-indigo-600 text-white'
                      : 'bg-white text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  <BarChart3 className="w-4 h-4" />
                  经验分析报告
                </button>
              </div>

              {/* 报告视图才显示版本选择 */}
              {topView === 'report' && (
                <div className="relative depth-dropdown">
                  <button
                    onClick={() => setShowDepthDropdown(!showDepthDropdown)}
                    className="flex items-center gap-2 px-3 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50"
                  >
                    <Layers className="w-4 h-4" />
                    {DEPTH_OPTIONS.find((d) => d.key === selectedDepth)?.label || '标准版'}
                    <ChevronDown className="w-3 h-3" />
                  </button>
                  {showDepthDropdown && (
                    <div className="absolute left-0 mt-1 w-56 bg-white rounded-lg shadow-lg border z-50">
                      {(() => {
                        const generatedDepths = getGeneratedDepths(interview);
                        return DEPTH_OPTIONS.map((d) => {
                          const isGenerated = generatedDepths.includes(d.key);
                          return (
                            <button
                              key={d.key}
                              onClick={() => {
                                setShowDepthDropdown(false);
                                loadData(d.key);
                              }}
                              className={`w-full text-left px-4 py-3 text-sm hover:bg-gray-50 first:rounded-t-lg last:rounded-b-lg ${
                                selectedDepth === d.key ? 'bg-indigo-50 text-indigo-700 font-medium' : 'text-gray-700'
                              }`}
                            >
                              <div className="flex items-center gap-2">
                                <d.icon className="w-4 h-4" />
                                <span>{d.label}</span>
                                {isGenerated && (
                                  <span className="ml-auto text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded">
                                    已生成
                                  </span>
                                )}
                              </div>
                              <div className="text-xs text-gray-400 mt-0.5 ml-6">{d.desc}</div>
                            </button>
                          );
                        });
                      })()}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* 右侧：导出按钮 */}
            <div className="flex items-center gap-1.5">
              {EXPORT_FORMATS.map((fmt) => (
                <button
                  key={fmt.key}
                  onClick={() => handleExport(fmt.key)}
                  disabled={exporting || (topView === 'report' && !report)}
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

          {/* 第二行：动态标题 */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-indigo-100 rounded-lg flex items-center justify-center">
              {topView === 'materials' ? (
                <FileText className="w-5 h-5 text-indigo-600" />
              ) : (
                <BookOpen className="w-5 h-5 text-indigo-600" />
              )}
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                {topView === 'materials' ? '访谈素材包' : '经验分析报告'}
              </h1>
              <p className="text-gray-500">
                {topView === 'materials'
                  ? '访谈完成后自动生成的经验资产'
                  : '基于访谈内容生成的系统性分析报告'}
              </p>
            </div>
          </div>
        </div>

        {/* 视图内容 */}
        {topView === 'materials' ? renderMaterialsView() : renderReportView()}
      </div>
    </div>
  );
}
