import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, FileText, Loader2, Sparkles, Send,
  ChevronDown, FileSpreadsheet, Download, FileCode,
  Layers, BookOpen, Target, AlertTriangle, Wrench,
  CheckCircle, BarChart3, Lightbulb, GitBranch,
  GraduationCap, Award, Table, Star, CheckSquare,
  MessageSquare, User, Briefcase,
} from 'lucide-react';
import { textAnalysisApi } from '@/services/api';
import type { TextAnalysis, TextAnalysisCreateRequest } from '@/types';
import { ReportToc } from '@/components/ReportToc';
import { useReportScrollSpy } from '@/hooks/useReportScrollSpy';
import { logger } from '@/utils/logger';

const EXPORT_FORMATS = [
  { key: 'docx', label: 'Word', icon: FileSpreadsheet },
  { key: 'pdf', label: 'PDF', icon: FileText },
  { key: 'markdown', label: 'Markdown', icon: FileCode },
];

interface ReportSection {
  key: string;
  title: string;
  icon: React.ElementType;
  content?: string;
}

const getReportSections = (report: any): ReportSection[] => {
  if (!report?.analysis_report) return [];
  const ar = report.analysis_report;
  const baseSections = [
    { key: 'executive_summary', title: '执行摘要', icon: Sparkles, content: ar.executive_summary },
    { key: 'case_background', title: '案例背景', icon: FileText, content: ar.case_background },
    { key: 'four_layer_structure', title: '头-身-足-包四层结构', icon: Layers, content: ar.four_layer_structure },
    { key: 'methodology_framework', title: '方法论框架', icon: Target, content: ar.methodology_framework },
    { key: 'key_steps_analysis', title: '关键步骤详解', icon: CheckCircle, content: ar.key_steps_analysis },
    { key: 'decision_logic_analysis', title: '决策逻辑深度分析', icon: Lightbulb, content: ar.decision_logic_analysis },
    { key: 'process_obstacle_mapping', title: '流程-障碍映射', icon: Table, content: ar.process_obstacle_mapping },
    { key: 'root_cause_analysis', title: '5Why根因链分析', icon: GitBranch, content: ar.root_cause_analysis },
    { key: 'obstacles_and_risks', title: '风险与挑战分析', icon: AlertTriangle, content: ar.obstacles_and_risks },
    { key: 'tools_and_scripts', title: '工具与话术清单', icon: Wrench, content: ar.tools_and_scripts },
    { key: 'application_guidance', title: '应用建议', icon: GraduationCap, content: ar.application_guidance },
    { key: 'critical_success_factors', title: '关键成功因素', icon: Star, content: ar.critical_success_factors },
    { key: 'value_assessment', title: '价值评估', icon: BarChart3, content: ar.value_assessment },
    { key: 'lessons_learned', title: '可迁移的经验教训', icon: BookOpen, content: ar.lessons_learned },
    { key: 'references', title: '相关概念与理论引用', icon: Award, content: ar.references },
    { key: 'three_review_assessment', title: '三审定稿评估', icon: CheckSquare, content: ar.three_review_assessment },
  ];
  return baseSections.filter((s) => typeof s.content === 'string' && s.content.trim().length > 0);
};

const renderMarkdownContent = (content: string) => {
  let html = content
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  html = html.replace(/^### (.*$)/gim, '<h3 class="text-lg font-bold text-gray-900 mt-4 mb-2">$1</h3>');
  html = html.replace(/^## (.*$)/gim, '<h2 class="text-xl font-bold text-gray-900 mt-6 mb-3">$1</h2>');
  html = html.replace(/^# (.*$)/gim, '<h1 class="text-2xl font-bold text-gray-900 mt-8 mb-4">$1</h1>');
  html = html.replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>');
  html = html.replace(/\*(.*?)\*/gim, '<em>$1</em>');
  html = html.replace(/^\> (.*$)/gim, '<blockquote class="border-l-4 border-gray-300 pl-4 my-3 text-gray-600 italic">$1</blockquote>');
  html = html.replace(/`([^`]+)`/gim, '<code class="bg-gray-100 px-1.5 py-0.5 rounded text-sm font-mono text-red-600">$1</code>');
  html = html.replace(/^\- (.*$)/gim, '<li class="ml-4 my-1">$1</li>');
  html = html.replace(/^(\d+\.\s.*$)/gim, '<li class="ml-4 my-1">$1</li>');

  // Markdown tables
  html = html.replace(
    /((?:\s*\|[^\n]*\|\s*(?:\n|$))+)/g,
    (tableBlock: string) => {
      const rows = tableBlock.trim().split('\n').filter((r) => r.trim());
      if (rows.length < 2) return tableBlock;
      const separatorRow = rows[1].trim();
      const isSeparator = /^\|[\s\-:|]+\|$/.test(separatorRow);
      if (!isSeparator) return tableBlock;

      let tableHtml = '<table class="w-full border-collapse border border-gray-300 my-4 text-sm">';
      rows.forEach((row, idx) => {
        if (idx === 1) return;
        const cells = row
          .trim()
          .replace(/^\|/, '')
          .replace(/\|$/, '')
          .split('|')
          .map((c) => c.trim());
        const tag = idx === 0 ? 'th' : 'td';
        const cellClass =
          idx === 0
            ? 'border border-gray-300 px-3 py-2 bg-gray-50 font-semibold text-gray-900 text-left'
            : 'border border-gray-300 px-3 py-2 text-gray-700 text-left';
        tableHtml += '<tr>';
        cells.forEach((cell) => {
          tableHtml += `<${tag} class="${cellClass}">${cell}</${tag}>`;
        });
        tableHtml += '</tr>';
      });
      tableHtml += '</table>';
      return tableHtml;
    }
  );

  html = html.replace(/\n/gim, '<br />');
  return { __html: html };
};

export function TextAnalysisPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isNew = !id || id === 'new';

  // 查看模式状态
  const [analysis, setAnalysis] = useState<TextAnalysis | null>(null);
  const [loading, setLoading] = useState(!isNew);
  const [exporting, setExporting] = useState(false);
  const [showExportDropdown, setShowExportDropdown] = useState(false);
  const [activeSection, setActiveSection] = useState<string | null>(null);
  const [showCleanedContent, setShowCleanedContent] = useState(false);

  // 报告章节和滚动监听（必须在所有早期 return 之前）
  const reportSectionsForToc = getReportSections(analysis?.analysis_report || {});
  const currentSection = useReportScrollSpy({
    enabled: !isNew && !loading && !!analysis && analysis.status === 'completed' && reportSectionsForToc.length > 0,
    sectionKeys: reportSectionsForToc.map((s) => s.key),
    extraIds: showCleanedContent ? ['cleaned-content'] : [],
  });

  // 创建模式状态
  const [formData, setFormData] = useState<TextAnalysisCreateRequest>({
    theme: '',
    background: '',
    expert_role: '',
    raw_text: '',
  });
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);

  useEffect(() => {
    if (id && id !== 'new') {
      loadAnalysis(id);
    }
  }, [id]);

  const loadAnalysis = async (analysisId: string) => {
    try {
      setLoading(true);
      const response = await textAnalysisApi.get(analysisId);
      setAnalysis(response.data);
    } catch (err: any) {
      logger.error('Failed to load text analysis', { error: String(err) });
      setError(err.response?.data?.detail || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = () => {
    if (!formData.theme.trim() || !formData.raw_text.trim()) {
      setError('请填写主题和访谈记录文本');
      return;
    }
    if (formData.raw_text.trim().length < 100) {
      setError('访谈记录文本至少需要100字');
      return;
    }
    setError(null);
    setShowConfirm(true);
  };

  const handleConfirmSubmit = async () => {
    setShowConfirm(false);
    try {
      setAnalyzing(true);
      setError(null);
      await textAnalysisApi.create(formData);
      // 创建成功后跳转到列表页，后台异步执行分析
      navigate('/text-analysis');
    } catch (err: any) {
      logger.error('Text analysis failed', { error: String(err) });
      setError(err.response?.data?.detail || '分析失败，请检查输入文本或稍后重试');
      setAnalyzing(false);
    }
  };

  const scrollToSection = (key: string) => {
    const el = document.getElementById(key);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  const handleExport = async (format: string) => {
    if (!analysis || !id) return;
    try {
      setExporting(true);
      setShowExportDropdown(false);
      const response = await textAnalysisApi.export(id, format);
      const blob = new Blob([response.data]);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const ext = format === 'markdown' ? 'md' : format;
      a.download = `${analysis.theme}_专家版分析报告.${ext}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      logger.error('Export failed', { error: String(err) });
      alert('导出失败，请重试');
    } finally {
      setExporting(false);
    }
  };

  // ========== 创建模式 ==========
  if (isNew) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-8">
        <div className="mb-6">
          <button
            onClick={() => navigate('/text-analysis')}
            className="flex items-center text-gray-500 hover:text-gray-700 transition-colors"
          >
            <ArrowLeft className="w-4 h-4 mr-1" />
            返回列表
          </button>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
          <div className="mb-8">
            <h1 className="text-2xl font-bold text-gray-900 flex items-center">
              <Sparkles className="w-6 h-6 mr-2 text-primary-600" />
              已有访谈文本智能分析
            </h1>
            <p className="text-gray-500 mt-2">
              粘贴已有的经验萃取访谈文字记录，系统将自动识别并清理无效内容，提取有效问答，并生成专家版经验分析报告。
            </p>
          </div>

          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start">
              <AlertTriangle className="w-5 h-5 text-red-500 mr-2 flex-shrink-0 mt-0.5" />
              <p className="text-red-700 text-sm">{error}</p>
            </div>
          )}

          <div className="space-y-6">
            {/* 主题 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                萃取主题 <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={formData.theme}
                onChange={(e) => setFormData({ ...formData, theme: e.target.value })}
                placeholder="例如：客户异议处理、项目风险管理..."
                disabled={analyzing}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none transition-all disabled:bg-gray-100 disabled:text-gray-500"
              />
            </div>

            {/* 业务背景 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">业务背景</label>
              <textarea
                value={formData.background}
                onChange={(e) => setFormData({ ...formData, background: e.target.value })}
                placeholder="描述这次访谈的业务背景，有助于生成更精准的分析报告..."
                rows={3}
                disabled={analyzing}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none transition-all resize-none disabled:bg-gray-100 disabled:text-gray-500"
              />
            </div>

            {/* 专家角色 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">专家角色</label>
              <input
                type="text"
                value={formData.expert_role}
                onChange={(e) => setFormData({ ...formData, expert_role: e.target.value })}
                placeholder="例如：资深销售经理、技术架构师..."
                disabled={analyzing}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none transition-all disabled:bg-gray-100 disabled:text-gray-500"
              />
            </div>

            {/* 访谈记录文本 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                访谈原始文字记录 <span className="text-red-500">*</span>
              </label>
              <div className="relative">
                <textarea
                  value={formData.raw_text}
                  onChange={(e) => setFormData({ ...formData, raw_text: e.target.value })}
                  placeholder="请粘贴完整的访谈文字记录。记录中可以包含访谈者和被访谈者之间的对话，系统会自动识别并清理以下内容：&#10;&#10;- 寒暄问候、开场白、道别语&#10;- 口头禅和填充词（嗯、啊、这个、那个）&#10;- 组织语言时的无效停顿&#10;- 跑题内容和闲聊&#10;- 非对话内容（时间戳、转录标记等）&#10;&#10;保留有价值的问答对、案例细节、方法论描述等核心内容。"
                  rows={16}
                  disabled={analyzing}
                  className={`w-full px-4 py-3 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none transition-all resize-y font-mono text-sm disabled:bg-gray-100 disabled:text-gray-500 ${
                    formData.raw_text.length > 0 && formData.raw_text.length < 100 && !analyzing
                      ? 'border-red-300 bg-red-50/30'
                      : 'border-gray-300'
                  }`}
                />
                <div
                  className={`absolute bottom-3 right-3 text-xs ${
                    formData.raw_text.length > 0 && formData.raw_text.length < 100
                      ? 'text-red-500 font-medium'
                      : 'text-gray-400'
                  }`}
                >
                  {formData.raw_text.length} / 100 字
                  {formData.raw_text.length > 0 && formData.raw_text.length < 100 && '（至少需要100字）'}
                </div>
              </div>
              {formData.raw_text.length > 0 && formData.raw_text.length < 100 && (
                <p className="mt-1.5 text-xs text-red-500 flex items-center">
                  <AlertTriangle className="w-3.5 h-3.5 mr-1" />
                  访谈记录文本至少需要 100 字才能进行分析，当前仅 {formData.raw_text.length} 字
                </p>
              )}
            </div>

            {/* 提交按钮 */}
            <div className="flex items-center justify-between pt-4">
              <div className="text-sm text-gray-500">
                <p>分析过程大约需要 1-3 分钟，请耐心等待</p>
                {(!formData.theme.trim() || formData.raw_text.trim().length < 100) && !analyzing && (
                  <p className="text-xs text-orange-500 mt-1 flex items-center">
                    <AlertTriangle className="w-3.5 h-3.5 mr-1" />
                    {!formData.theme.trim() && !formData.raw_text.trim()
                      ? '请填写主题和访谈记录'
                      : !formData.theme.trim()
                        ? '请填写萃取主题'
                        : '访谈记录至少需要100字'}
                  </p>
                )}
              </div>
              <button
                onClick={handleSubmit}
                disabled={analyzing || !formData.theme.trim() || formData.raw_text.trim().length < 100}
                title={
                  !formData.theme.trim() && !formData.raw_text.trim()
                    ? '请填写主题和访谈记录'
                    : !formData.theme.trim()
                      ? '请填写萃取主题'
                      : formData.raw_text.trim().length < 100
                        ? '访谈记录至少需要100字'
                        : ''
                }
                className="flex items-center px-8 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {analyzing ? (
                  <>
                    <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                    分析中...
                  </>
                ) : (
                  <>
                    <Send className="w-5 h-5 mr-2" />
                    开始分析
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* 二次确认弹窗 */}
        {showConfirm && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
            <div className="bg-white rounded-xl shadow-xl max-w-md w-full mx-4 p-6">
              <div className="flex items-center mb-4">
                <div className="w-10 h-10 bg-primary-100 rounded-full flex items-center justify-center mr-3">
                  <Sparkles className="w-5 h-5 text-primary-600" />
                </div>
                <h3 className="text-lg font-bold text-gray-900">确认开始分析？</h3>
              </div>
              <div className="text-sm text-gray-600 space-y-2 mb-6">
                <p>提交后，系统将自动进行以下处理：</p>
                <ul className="list-disc list-inside space-y-1 ml-1">
                  <li>文本清理（去除寒暄、口头禅等无效内容）</li>
                  <li>结构化内容提取</li>
                  <li>生成专家版分析报告</li>
                </ul>
                <p className="text-orange-600 mt-2">⚠ 分析过程大约需要 1-3 分钟，期间请勿重复提交。</p>
              </div>
              <div className="flex gap-3">
                <button
                  onClick={() => setShowConfirm(false)}
                  className="flex-1 px-4 py-2.5 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors font-medium"
                >
                  取消
                </button>
                <button
                  onClick={handleConfirmSubmit}
                  className="flex-1 px-4 py-2.5 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors font-medium"
                >
                  确认提交
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ========== 加载中 ==========
  if (loading) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-20 flex flex-col items-center">
        <Loader2 className="w-10 h-10 text-primary-600 animate-spin mb-4" />
        <p className="text-gray-500">加载分析结果...</p>
      </div>
    );
  }

  // ========== 错误 ==========
  if (error || !analysis) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-20 text-center">
        <AlertTriangle className="w-12 h-12 text-red-400 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900 mb-2">加载失败</h3>
        <p className="text-gray-500 mb-6">{error || '分析记录不存在'}</p>
        <button
          onClick={() => navigate('/text-analysis')}
          className="px-5 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
        >
          返回列表
        </button>
      </div>
    );
  }

  // ========== 查看模式 ==========
  const report = analysis.analysis_report;
  const sections = getReportSections(report);
  const metadata = report?.metadata || {};

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 relative">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center">
          <button
            onClick={() => navigate('/text-analysis')}
            className="flex items-center text-gray-500 hover:text-gray-700 transition-colors mr-4"
          >
            <ArrowLeft className="w-4 h-4 mr-1" />
            返回
          </button>
          <div>
            <h1 className="text-xl font-bold text-gray-900">{analysis.theme}</h1>
            <div className="flex items-center gap-3 text-sm text-gray-500 mt-1">
              <span>专家版分析报告</span>
              <span>·</span>
              <span>原始文本 {analysis.raw_text_length} 字</span>
              <span>·</span>
              <span>有效内容 {analysis.cleaned_messages.length} 条</span>
              {metadata.word_count > 0 && (
                <>
                  <span>·</span>
                  <span>报告约 {metadata.word_count} 字</span>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Export */}
        <div className="relative">
          <button
            onClick={() => setShowExportDropdown(!showExportDropdown)}
            disabled={exporting}
            className="flex items-center px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
          >
            <Download className="w-4 h-4 mr-2" />
            导出报告
            <ChevronDown className="w-4 h-4 ml-1" />
          </button>
          {showExportDropdown && (
            <div className="absolute right-0 mt-2 w-40 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-10">
              {EXPORT_FORMATS.map((fmt) => (
                <button
                  key={fmt.key}
                  onClick={() => handleExport(fmt.key)}
                  className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
                >
                  <fmt.icon className="w-4 h-4 mr-2" />
                  {fmt.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 清理后的有效内容（可折叠） */}
      <div id="cleaned-content" className="mb-6 bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <button
          onClick={() => setShowCleanedContent(!showCleanedContent)}
          className="flex items-center justify-between w-full px-6 py-4 hover:bg-gray-50 transition-colors"
        >
          <div className="flex items-center">
            <MessageSquare className="w-5 h-5 mr-2 text-primary-600" />
            <span className="font-medium text-gray-900">清理后的有效访谈内容</span>
            <span className="ml-2 text-sm text-gray-500">({analysis.cleaned_messages.length} 条)</span>
          </div>
          <ChevronDown className={`w-5 h-5 text-gray-400 transition-transform ${showCleanedContent ? 'rotate-180' : ''}`} />
        </button>
        {showCleanedContent && (
          <div className="px-6 pb-4 border-t border-gray-100">
            <div className="mt-4 space-y-3 max-h-96 overflow-y-auto">
              {analysis.cleaned_messages.map((msg, idx) => (
                <div key={idx} className={`p-3 rounded-lg ${msg.role === 'interviewer' ? 'bg-blue-50 border border-blue-100' : 'bg-green-50 border border-green-100'}`}>
                  <div className="flex items-center mb-1">
                    {msg.role === 'interviewer' ? (
                      <User className="w-4 h-4 mr-1 text-blue-600" />
                    ) : (
                      <Briefcase className="w-4 h-4 mr-1 text-green-600" />
                    )}
                    <span className={`text-xs font-medium ${msg.role === 'interviewer' ? 'text-blue-600' : 'text-green-600'}`}>
                      {msg.role === 'interviewer' ? '访谈者' : '专家'}
                    </span>
                  </div>
                  <p className="text-sm text-gray-700 whitespace-pre-wrap">{msg.content}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 报告内容 */}
      {analysis.status === 'completed' ? (
        <div className="space-y-6">
          {/* 报告标题 */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
            <h1 className="text-2xl font-bold text-gray-900 text-center mb-2">
              {analysis.theme} — 经验分析报告
            </h1>
            <div className="text-center text-sm text-gray-500 space-x-4">
              <span>专家版</span>
              <span>·</span>
              <span>生成时间：{new Date(analysis.created_at).toLocaleDateString('zh-CN')}</span>
              {metadata.word_count > 0 && (
                <>
                  <span>·</span>
                  <span>约 {metadata.word_count} 字</span>
                </>
              )}
            </div>
          </div>

          {/* 报告章节 */}
          {sections.map((section) => {
            const SectionIcon = section.icon;
            return (
              <div
                key={section.key}
                id={section.key}
                className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden scroll-mt-24"
              >
                <button
                  onClick={() => setActiveSection(activeSection === section.key ? null : section.key)}
                  className="flex items-center w-full px-6 py-4 hover:bg-gray-50 transition-colors"
                >
                  <SectionIcon className="w-5 h-5 mr-3 text-primary-600" />
                  <h3 className="text-lg font-bold text-gray-900 flex-1 text-left">{section.title}</h3>
                  <ChevronDown className={`w-5 h-5 text-gray-400 transition-transform ${activeSection === section.key ? 'rotate-180' : ''}`} />
                </button>
                {(activeSection === section.key || activeSection === null) && (
                  <div className="px-6 pb-6 border-t border-gray-100">
                    <div
                      className="prose prose-indigo max-w-none mt-4 text-gray-700 leading-relaxed"
                      dangerouslySetInnerHTML={renderMarkdownContent(section.content || '')}
                    />
                  </div>
                )}
              </div>
            );
          })}

          {sections.length === 0 && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center">
              <FileText className="w-12 h-12 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-500">报告中暂无内容</p>
            </div>
          )}
        </div>
      ) : analysis.status === 'failed' ? (
        <div className="bg-red-50 border border-red-200 rounded-xl p-8 text-center">
          <AlertTriangle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-red-800 mb-2">分析失败</h3>
          <p className="text-red-600">{analysis.error_message || '未知错误'}</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center">
          <Loader2 className="w-10 h-10 text-primary-600 animate-spin mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">分析进行中</h3>
          <p className="text-gray-500">当前状态：{analysis.status}</p>
        </div>
      )}

      {/* 右侧悬浮章节导航 */}
      <ReportToc
        sections={sections}
        currentSection={currentSection}
        onNavigate={scrollToSection}
        extraItems={
          showCleanedContent
            ? [{ key: 'cleaned-content', title: '有效访谈内容', icon: MessageSquare }]
            : []
        }
        colorScheme="primary"
        visible={analysis.status === 'completed' && sections.length > 0}
      />
    </div>
  );
}
