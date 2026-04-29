import { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  Plus, MessageSquare, Clock, ChevronRight, Trash2, AlertTriangle,
  Search, Archive, ArchiveRestore, Loader2, X,
} from 'lucide-react';
import { interviewApi } from '@/services/api';
import { InterviewListSkeleton } from '@/components/Skeleton';
import { logger } from '@/utils/logger';
import type { Interview } from '@/types';

const STATUS_TABS = [
  { value: '', label: '全部' },
  { value: 'active', label: '进行中' },
  { value: 'completed', label: '已完成' },
  { value: 'archived', label: '已归档' },
] as const;

export function InterviewListPage() {
  const [interviews, setInterviews] = useState<Interview[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeStatus, setActiveStatus] = useState('');
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [archivingId, setArchivingId] = useState<string | null>(null);
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [confirmTheme, setConfirmTheme] = useState('');

  const loadInterviews = useCallback(async () => {
    try {
      setLoading(true);
      const response = await interviewApi.list(0, 20, activeStatus || undefined, searchQuery || undefined);
      setInterviews(response.data.items);
    } catch (error) {
      logger.error('加载访谈列表失败', { error: (error as Error).message });
    } finally {
      setLoading(false);
    }
  }, [activeStatus, searchQuery]);

  useEffect(() => {
    loadInterviews();
  }, [loadInterviews]);

  const handleDeleteClick = (e: React.MouseEvent, interview: Interview) => {
    e.preventDefault();
    e.stopPropagation();
    setConfirmId(interview.id);
    setConfirmTheme(interview.theme);
  };

  const handleConfirmDelete = async () => {
    if (!confirmId) return;
    try {
      setDeletingId(confirmId);
      await interviewApi.delete(confirmId);
      setInterviews((prev) => prev.filter((i) => i.id !== confirmId));
    } catch (error) {
      logger.error('删除访谈失败', { error: (error as Error).message });
      alert('删除失败，请稍后重试');
    } finally {
      setDeletingId(null);
      setConfirmId(null);
      setConfirmTheme('');
    }
  };

  const handleCancelDelete = () => {
    setConfirmId(null);
    setConfirmTheme('');
  };

  const handleArchive = async (interview: Interview) => {
    const newStatus = interview.status === 'archived' ? 'active' : 'archived';
    try {
      setArchivingId(interview.id);
      await interviewApi.update(interview.id, { status: newStatus as any });
      setInterviews((prev) =>
        prev.map((i) => (i.id === interview.id ? { ...i, status: newStatus } : i))
      );
    } catch (error) {
      logger.error('归档操作失败', { error: (error as Error).message });
      alert('操作失败，请稍后重试');
    } finally {
      setArchivingId(null);
    }
  };

  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      active: 'bg-blue-100 text-blue-700',
      completed: 'bg-green-100 text-green-700',
      paused: 'bg-yellow-100 text-yellow-700',
      archived: 'bg-gray-100 text-gray-600',
    };
    const labels: Record<string, string> = {
      active: '进行中',
      completed: '已完成',
      paused: '已暂停',
      archived: '已归档',
    };
    return (
      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${styles[status] || styles.active}`}>
        {labels[status] || status}
      </span>
    );
  };

  const getStateName = (state: string) => {
    const names: Record<string, string> = {
      event_review: '复盘事件',
      framework_build: '建构框架',
      detail_mining: '挖掘细节',
      obstacle_identify: '识别障碍',
      tool_extract: '提炼工具',
      confirmation: '复述确认',
      completed: '已完成',
    };
    return names[state] || state;
  };

  return (
    <div className="p-8 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">访谈列表</h1>
          <p className="text-gray-500 mt-1">管理您的经验萃取访谈</p>
        </div>
        <Link
          to="/interviews/new"
          className="inline-flex items-center px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors text-sm font-medium"
        >
          <Plus className="w-4 h-4 mr-2" />
          新建访谈
        </Link>
      </div>

      {/* Search & Filter */}
      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="搜索访谈主题、背景、专家角色..."
            className="w-full pl-10 pr-10 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none text-sm"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
        <div className="flex gap-1 bg-gray-100 p-1 rounded-lg">
          {STATUS_TABS.map((tab) => (
            <button
              key={tab.value}
              onClick={() => setActiveStatus(tab.value)}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                activeStatus === tab.value
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* List */}
      {loading ? (
        <InterviewListSkeleton />
      ) : interviews.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-xl border border-gray-100">
          <MessageSquare className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            {searchQuery ? '未找到匹配的访谈' : '还没有访谈'}
          </h3>
          <p className="text-gray-500 mb-6">
            {searchQuery ? '尝试更换搜索关键词' : '创建您的第一个经验萃取访谈'}
          </p>
          {!searchQuery && (
            <Link
              to="/interviews/new"
              className="inline-flex items-center px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors text-sm font-medium"
            >
              <Plus className="w-4 h-4 mr-2" />
              开始萃取
            </Link>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          {interviews.map((interview) => (
            <div
              key={interview.id}
              className="group bg-white rounded-xl p-5 hover:shadow-md transition-shadow border border-gray-100"
            >
              <div className="flex items-center justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                    <h3 className="text-base font-semibold text-gray-900 truncate">
                      {interview.theme}
                    </h3>
                    {getStatusBadge(interview.status)}
                  </div>
                  <div className="flex items-center gap-4 text-sm text-gray-500 flex-wrap">
                    <span className="flex items-center">
                      <MessageSquare className="w-3.5 h-3.5 mr-1" />
                      {getStateName(interview.current_state)}
                    </span>
                    {interview.expert_role && (
                      <span>专家: {interview.expert_role}</span>
                    )}
                    {interview.expected_duration && (
                      <span className="flex items-center">
                        <Clock className="w-3.5 h-3.5 mr-1" />
                        {interview.expected_duration}分钟
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <Link
                    to={
                      interview.status === 'completed'
                        ? `/interviews/${interview.id}/output`
                        : `/interviews/${interview.id}/chat`
                    }
                    className="inline-flex items-center px-3 py-1.5 text-sm font-medium text-indigo-600 bg-indigo-50 rounded-lg hover:bg-indigo-100 transition-colors"
                  >
                    {interview.status === 'completed' ? '查看成果' : '进入访谈'}
                    <ChevronRight className="w-4 h-4 ml-1" />
                  </Link>
                  <button
                    onClick={() => handleArchive(interview)}
                    disabled={archivingId === interview.id}
                    className="inline-flex items-center px-3 py-1.5 text-sm font-medium text-gray-600 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors disabled:opacity-50"
                    title={interview.status === 'archived' ? '取消归档' : '归档'}
                  >
                    {archivingId === interview.id ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : interview.status === 'archived' ? (
                      <ArchiveRestore className="w-4 h-4" />
                    ) : (
                      <Archive className="w-4 h-4" />
                    )}
                  </button>
                  <button
                    onClick={(e) => handleDeleteClick(e, interview)}
                    disabled={deletingId === interview.id}
                    className="inline-flex items-center px-3 py-1.5 text-sm font-medium text-red-600 bg-red-50 rounded-lg hover:bg-red-100 transition-colors disabled:opacity-50"
                    title="删除访谈"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Delete Confirm Modal */}
      {confirmId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4 p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-red-100 rounded-full">
                <AlertTriangle className="w-6 h-6 text-red-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900">确认删除</h3>
            </div>
            <p className="text-gray-600 mb-6">
              确定要删除访谈 <span className="font-medium text-gray-900">「{confirmTheme}」</span> 吗？
              <br />
              <span className="text-sm text-red-500 mt-1 inline-block">
                此操作不可恢复，访谈的所有消息记录和萃取内容将被一并删除。
              </span>
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={handleCancelDelete}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
              >
                取消
              </button>
              <button
                onClick={handleConfirmDelete}
                disabled={!!deletingId}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50"
              >
                {deletingId ? '删除中...' : '确认删除'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
