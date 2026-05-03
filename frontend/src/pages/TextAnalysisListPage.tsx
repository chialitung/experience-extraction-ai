import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileText, Plus, Trash2, Loader2, Clock, AlertCircle, CheckCircle } from 'lucide-react';
import { textAnalysisApi } from '@/services/api';
import type { TextAnalysis } from '@/types';
import { logger } from '@/utils/logger';

export function TextAnalysisListPage() {
  const navigate = useNavigate();
  const [analyses, setAnalyses] = useState<TextAnalysis[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState<string | null>(null);

  useEffect(() => {
    loadAnalyses();
  }, []);

  const loadAnalyses = async () => {
    try {
      setLoading(true);
      const response = await textAnalysisApi.list(0, 50);
      setAnalyses(response.data.items);
    } catch (error) {
      logger.error('Failed to load text analyses', { error: String(error) });
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm('确定要删除这条分析记录吗？删除后不可恢复。')) {
      return;
    }
    try {
      setDeleting(id);
      await textAnalysisApi.delete(id);
      setAnalyses((prev) => prev.filter((a) => a.id !== id));
    } catch (error) {
      logger.error('Failed to delete text analysis', { error: String(error) });
      alert('删除失败，请重试');
    } finally {
      setDeleting(null);
    }
  };

  const getStatusInfo = (status: string) => {
    switch (status) {
      case 'completed':
        return { label: '已完成', color: 'text-green-600', bg: 'bg-green-50', icon: CheckCircle };
      case 'pending':
        return { label: '等待中', color: 'text-gray-500', bg: 'bg-gray-50', icon: Clock };
      case 'cleaning':
      case 'extracting':
      case 'reporting':
        return { label: '分析中', color: 'text-blue-600', bg: 'bg-blue-50', icon: Loader2 };
      case 'failed':
        return { label: '失败', color: 'text-red-600', bg: 'bg-red-50', icon: AlertCircle };
      default:
        return { label: status, color: 'text-gray-500', bg: 'bg-gray-50', icon: Clock };
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">文本分析</h1>
          <p className="text-gray-500 mt-1">粘贴已有访谈记录，AI自动清理并生成专家版分析报告</p>
        </div>
        <button
          onClick={() => navigate('/text-analysis/new')}
          className="flex items-center px-5 py-2.5 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors font-medium"
        >
          <Plus className="w-5 h-5 mr-2" />
          新建分析
        </button>
      </div>

      {/* List */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 text-primary-600 animate-spin" />
          <span className="ml-3 text-gray-500">加载中...</span>
        </div>
      ) : analyses.length === 0 ? (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center">
          <FileText className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">暂无分析记录</h3>
          <p className="text-gray-500 mb-6">粘贴已有的经验萃取访谈文字记录，系统将自动清理无效内容并生成专家版分析报告</p>
          <button
            onClick={() => navigate('/text-analysis/new')}
            className="inline-flex items-center px-5 py-2.5 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors font-medium"
          >
            <Plus className="w-5 h-5 mr-2" />
            开始分析
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {analyses.map((analysis) => {
            const statusInfo = getStatusInfo(analysis.status);
            const StatusIcon = statusInfo.icon;
            return (
              <div
                key={analysis.id}
                onClick={() => navigate(`/text-analysis/${analysis.id}`)}
                className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 hover:shadow-md hover:border-primary-200 transition-all cursor-pointer"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-lg font-semibold text-gray-900 truncate">{analysis.theme}</h3>
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${statusInfo.bg} ${statusInfo.color}`}>
                        <StatusIcon className={`w-3.5 h-3.5 mr-1 ${analysis.status === 'cleaning' || analysis.status === 'extracting' || analysis.status === 'reporting' ? 'animate-spin' : ''}`} />
                        {statusInfo.label}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 text-sm text-gray-500">
                      <span>原始文本 {analysis.raw_text_length} 字</span>
                      {analysis.cleaned_messages.length > 0 && (
                        <span>有效内容 {analysis.cleaned_messages.length} 条</span>
                      )}
                      <span>{formatDate(analysis.created_at)}</span>
                    </div>
                    {analysis.error_message && (
                      <p className="text-sm text-red-600 mt-2">{analysis.error_message}</p>
                    )}
                  </div>
                  <button
                    onClick={(e) => handleDelete(analysis.id, e)}
                    disabled={deleting === analysis.id}
                    className="ml-4 p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                    title="删除"
                  >
                    {deleting === analysis.id ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Trash2 className="w-4 h-4" />
                    )}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
