import { useState, useEffect } from 'react';
import { Settings as SettingsIcon, Info, Database, Server, Trash2, ExternalLink } from 'lucide-react';
import api from '@/services/api';
import axios from 'axios';

interface LlmConfig {
  provider: string;
  label: string;
  model: string;
  base_url: string;
  environment: string;
  debug: boolean;
}

export function SettingsPage() {
  const [systemInfo, setSystemInfo] = useState<{ status: string; version: string } | null>(null);
  const [llmConfig, setLlmConfig] = useState<LlmConfig | null>(null);
  const clearing = false;

  useEffect(() => {
    // 健康检查直接访问 /health（不在 /api/v1 下）
    axios.get('/health').then(res => setSystemInfo(res.data)).catch(() => null);
    // config 在 /api/v1/config，使用 api 实例
    api.get('/config').then(res => setLlmConfig(res.data)).catch(() => null);
  }, []);

  const handleClearLocal = () => {
    if (confirm('确定要清除所有本地缓存数据吗？此操作不可恢复。')) {
      localStorage.clear();
      alert('本地缓存已清除');
      window.location.reload();
    }
  };

  return (
    <div className="max-w-3xl mx-auto p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center">
          <SettingsIcon className="w-7 h-7 mr-3 text-primary-600" />
          系统设置
        </h1>
        <p className="text-gray-500 mt-2">管理系统配置与查看运行状态</p>
      </div>

      <div className="space-y-6">
        {/* 系统状态 */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <Server className="w-5 h-5 mr-2 text-primary-600" />
            系统状态
          </h2>
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-gray-50 rounded-lg p-4">
              <p className="text-sm text-gray-500 mb-1">后端状态</p>
              <div className="flex items-center">
                <span className={`w-2.5 h-2.5 rounded-full mr-2 ${systemInfo ? 'bg-green-500' : 'bg-red-500'}`} />
                <span className="font-medium text-gray-900">
                  {systemInfo ? '正常运行' : '连接失败'}
                </span>
              </div>
            </div>
            <div className="bg-gray-50 rounded-lg p-4">
              <p className="text-sm text-gray-500 mb-1">系统版本</p>
              <p className="font-medium text-gray-900">{systemInfo?.version || '-'}</p>
            </div>
          </div>
        </div>

        {/* AI 配置 */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <Database className="w-5 h-5 mr-2 text-primary-600" />
            AI 模型配置
          </h2>
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-4">
            <p className="text-sm text-amber-800">
              当前使用 <strong>{llmConfig ? `${llmConfig.label} (${llmConfig.model})` : '...'}</strong>。
              如需修改，请编辑后端 <code className="bg-amber-100 px-1.5 py-0.5 rounded text-amber-900 font-mono text-xs">backend/.env</code> 文件并重启服务。
            </p>
          </div>
          <div className="space-y-3">
            <div className="flex justify-between items-center py-2 border-b border-gray-100">
              <span className="text-gray-600">默认供应商</span>
              <span className="font-medium text-gray-900">{llmConfig?.label || '-'}</span>
            </div>
            <div className="flex justify-between items-center py-2 border-b border-gray-100">
              <span className="text-gray-600">当前模型</span>
              <span className="font-medium text-gray-900">{llmConfig?.model || '-'}</span>
            </div>
            <div className="flex justify-between items-center py-2 border-b border-gray-100">
              <span className="text-gray-600">API 地址</span>
              <span className="font-medium text-gray-900 font-mono text-sm">{llmConfig?.base_url || '-'}</span>
            </div>
            <div className="flex justify-between items-center py-2 border-b border-gray-100">
              <span className="text-gray-600">运行环境</span>
              <span className="font-medium text-gray-900">{llmConfig?.environment || '-'}</span>
            </div>
          </div>
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center mt-4 text-sm text-primary-600 hover:text-primary-700"
          >
            <ExternalLink className="w-4 h-4 mr-1" />
            查看后端 API 文档
          </a>
        </div>

        {/* 数据管理 */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <Database className="w-5 h-5 mr-2 text-primary-600" />
            数据管理
          </h2>
          <button
            onClick={handleClearLocal}
            disabled={clearing}
            className="flex items-center px-4 py-2.5 bg-red-50 text-red-700 rounded-lg hover:bg-red-100 transition-colors text-sm font-medium"
          >
            <Trash2 className="w-4 h-4 mr-2" />
            清除本地缓存数据
          </button>
          <p className="text-xs text-gray-400 mt-2">此操作将清除浏览器本地存储的访谈状态等临时数据，不会删除后端数据库中的访谈记录。</p>
        </div>

        {/* 关于 */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <Info className="w-5 h-5 mr-2 text-primary-600" />
            关于系统
          </h2>
          <p className="text-gray-600 text-sm leading-relaxed mb-4">
            经验萃取 AI 系统是一套基于 BEST 高能经验萃取方法论和「金木水火土」价值标准的智能化访谈辅助系统。
            通过多轮对话引导，帮助萃取专家从业务高手处高效挖掘、结构化并封装高价值经验。
          </p>
          <div className="text-xs text-gray-400 space-y-1">
            <p>技术栈：FastAPI + React + TailwindCSS + SQLite</p>
            <p>AI 引擎：{llmConfig ? `${llmConfig.label} (${llmConfig.model})` : '-'}</p>
            <p>项目路径：experience-extraction-ai</p>
          </div>
        </div>
      </div>
    </div>
  );
}
