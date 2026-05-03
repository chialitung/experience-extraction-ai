import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Settings as SettingsIcon, Info, Database, Server, Trash2, ExternalLink,
  Users, Save, CheckCircle, Lock, Eye, EyeOff, UserCircle,
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import api, { authApi, configApi } from '@/services/api';
import axios from 'axios';
import { logger } from '@/utils/logger';

interface LlmConfig {
  provider: string;
  label: string;
  model: string;
  base_url: string;
  environment: string;
  debug: boolean;
  deepseek_api_key: string;
  deepseek_base_url: string;
  baidu_speech_app_id: string;
  baidu_speech_api_key: string;
  baidu_speech_secret_key: string;
}

export function SettingsPage() {
  const { isAdmin, user, refreshUser } = useAuth();
  const [systemInfo, setSystemInfo] = useState<{ status: string; version: string } | null>(null);
  const [llmConfig, setLlmConfig] = useState<LlmConfig | null>(null);
  const [editableConfig, setEditableConfig] = useState<{
    default_llm_provider: string;
    deepseek_model: string;
    deepseek_api_key: string;
    deepseek_base_url: string;
    baidu_speech_app_id: string;
    baidu_speech_api_key: string;
    baidu_speech_secret_key: string;
  } | null>(null);
  const [configSaved, setConfigSaved] = useState(false);
  const [configSaving, setConfigSaving] = useState(false);

  // Nickname state
  const [nickname, setNickname] = useState(user?.full_name || '');
  const [nicknameSaving, setNicknameSaving] = useState(false);
  const [nicknameSuccess, setNicknameSuccess] = useState(false);

  // Password change state
  const [passwordForm, setPasswordForm] = useState({
    newPassword: '',
    confirmPassword: '',
  });
  const [showPassword, setShowPassword] = useState(false);
  const [passwordError, setPasswordError] = useState('');
  const [passwordSuccess, setPasswordSuccess] = useState('');
  const [passwordSaving, setPasswordSaving] = useState(false);

  useEffect(() => {
    axios.get('/health').then(res => setSystemInfo(res.data)).catch(() => null);
    api.get('/config').then(res => {
      setLlmConfig(res.data);
      setEditableConfig({
        default_llm_provider: res.data.provider,
        deepseek_model: res.data.model || '',
        deepseek_api_key: res.data.deepseek_api_key || '',
        deepseek_base_url: res.data.deepseek_base_url || '',
        baidu_speech_app_id: res.data.baidu_speech_app_id || '',
        baidu_speech_api_key: res.data.baidu_speech_api_key || '',
        baidu_speech_secret_key: res.data.baidu_speech_secret_key || '',
      });
    }).catch(() => null);
  }, []);

  const handleClearLocal = () => {
    if (confirm('确定要清除所有本地缓存数据吗？此操作不可恢复。')) {
      localStorage.clear();
      alert('本地缓存已清除');
      window.location.reload();
    }
  };

  const handleNicknameUpdate = async () => {
    setNicknameSuccess(false);
    setNicknameSaving(true);
    try {
      await authApi.updateMe({ full_name: nickname.trim() || undefined });
      await refreshUser();
      setNicknameSuccess(true);
      setTimeout(() => setNicknameSuccess(false), 3000);
    } catch (error: any) {
      const detail = error.response?.data?.detail || '修改失败';
      logger.error('修改昵称失败', { detail });
      alert(typeof detail === 'string' ? detail : '修改失败');
    } finally {
      setNicknameSaving(false);
    }
  };

  const handlePasswordChange = async () => {
    setPasswordError('');
    setPasswordSuccess('');

    if (passwordForm.newPassword.length < 6) {
      setPasswordError('新密码至少需要 6 位');
      return;
    }
    if (passwordForm.newPassword !== passwordForm.confirmPassword) {
      setPasswordError('两次输入的密码不一致');
      return;
    }

    setPasswordSaving(true);
    try {
      await authApi.updateMe({ password: passwordForm.newPassword });
      setPasswordSuccess('密码修改成功');
      setPasswordForm({ newPassword: '', confirmPassword: '' });
      setTimeout(() => setPasswordSuccess(''), 3000);
    } catch (error: any) {
      const detail = error.response?.data?.detail || '修改失败，请稍后重试';
      setPasswordError(typeof detail === 'string' ? detail : '修改失败');
    } finally {
      setPasswordSaving(false);
    }
  };

  const handleSaveConfig = async () => {
    if (!editableConfig) return;
    setConfigSaving(true);
    try {
      await configApi.update({
        default_llm_provider: editableConfig.default_llm_provider,
        deepseek_model: editableConfig.deepseek_model || undefined,
        deepseek_api_key: editableConfig.deepseek_api_key || undefined,
        deepseek_base_url: editableConfig.deepseek_base_url || undefined,
        baidu_speech_app_id: editableConfig.baidu_speech_app_id || undefined,
        baidu_speech_api_key: editableConfig.baidu_speech_api_key || undefined,
        baidu_speech_secret_key: editableConfig.baidu_speech_secret_key || undefined,
      });
      setConfigSaved(true);
      setTimeout(() => setConfigSaved(false), 3000);
    } catch {
      alert('保存配置失败');
    } finally {
      setConfigSaving(false);
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
        {/* 系统状态 — 仅管理员 */}
        {isAdmin && (
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
        )}

        {/* 账号设置 */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <UserCircle className="w-5 h-5 mr-2 text-primary-600" />
            账号设置
          </h2>
          <div className="space-y-4">
            <div className="flex justify-between items-center py-2 border-b border-gray-100">
              <span className="text-gray-600">当前邮箱</span>
              <span className="font-medium text-gray-900">{user?.email || '-'}</span>
            </div>

            {/* 昵称 */}
            <div className="space-y-3 pt-2">
              <h3 className="text-sm font-medium text-gray-700 flex items-center">
                <UserCircle className="w-4 h-4 mr-1.5 text-gray-500" />
                修改昵称
              </h3>
              <div className="flex gap-3">
                <input
                  type="text"
                  value={nickname}
                  onChange={(e) => setNickname(e.target.value)}
                  placeholder="您的昵称"
                  className="flex-1 border rounded-lg px-3 py-2 text-sm"
                />
                <button
                  onClick={handleNicknameUpdate}
                  disabled={nicknameSaving}
                  className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
                >
                  {nicknameSaving ? '保存中...' : '保存'}
                </button>
              </div>
              {nicknameSuccess && (
                <p className="text-sm text-green-600 flex items-center">
                  <CheckCircle className="w-4 h-4 mr-1" />
                  昵称已更新
                </p>
              )}
            </div>

            <div className="space-y-3 pt-2">
              <h3 className="text-sm font-medium text-gray-700 flex items-center">
                <Lock className="w-4 h-4 mr-1.5 text-gray-500" />
                修改密码
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={passwordForm.newPassword}
                    onChange={(e) => setPasswordForm({ ...passwordForm, newPassword: e.target.value })}
                    placeholder="新密码（至少 6 位）"
                    className="w-full border rounded-lg px-3 py-2 text-sm pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={passwordForm.confirmPassword}
                  onChange={(e) => setPasswordForm({ ...passwordForm, confirmPassword: e.target.value })}
                  placeholder="确认新密码"
                  className="w-full border rounded-lg px-3 py-2 text-sm"
                />
              </div>
              {passwordError && (
                <p className="text-sm text-red-600">{passwordError}</p>
              )}
              {passwordSuccess && (
                <p className="text-sm text-green-600 flex items-center">
                  <CheckCircle className="w-4 h-4 mr-1" />
                  {passwordSuccess}
                </p>
              )}
              <button
                onClick={handlePasswordChange}
                disabled={passwordSaving || !passwordForm.newPassword || !passwordForm.confirmPassword}
                className="inline-flex items-center px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
              >
                <Lock className="w-4 h-4 mr-2" />
                {passwordSaving ? '保存中...' : '修改密码'}
              </button>
            </div>
          </div>
        </div>

        {/* AI 模型配置 — 仅管理员 */}
        {isAdmin && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <Database className="w-5 h-5 mr-2 text-primary-600" />
            AI 模型配置
          </h2>

          {editableConfig ? (
            <div className="space-y-4">
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-4">
                <p className="text-sm text-amber-800">
                  管理员模式：修改配置后保存，<strong>需重启后端服务</strong>方可生效。
                </p>
              </div>

              {/* DeepSeek 配置 */}
              <div className="space-y-3">
                <h3 className="text-sm font-semibold text-gray-800 border-b border-gray-200 pb-2">DeepSeek AI 模型</h3>
                <div className="flex justify-between items-center py-2 border-b border-gray-100">
                  <span className="text-gray-600">模型名称</span>
                  <input
                    type="text"
                    value={editableConfig.deepseek_model}
                    onChange={(e) => setEditableConfig({ ...editableConfig, deepseek_model: e.target.value })}
                    placeholder="例如：deepseek-chat"
                    className="border rounded-lg px-3 py-1.5 text-sm w-64"
                  />
                </div>
                <div className="flex justify-between items-center py-2 border-b border-gray-100">
                  <span className="text-gray-600">API Key</span>
                  <input
                    type="text"
                    value={editableConfig.deepseek_api_key}
                    onChange={(e) => setEditableConfig({ ...editableConfig, deepseek_api_key: e.target.value })}
                    placeholder="sk-..."
                    className="border rounded-lg px-3 py-1.5 text-sm w-64"
                  />
                </div>
                <div className="flex justify-between items-center py-2 border-b border-gray-100">
                  <span className="text-gray-600">Base URL</span>
                  <input
                    type="text"
                    value={editableConfig.deepseek_base_url}
                    onChange={(e) => setEditableConfig({ ...editableConfig, deepseek_base_url: e.target.value })}
                    placeholder="https://api.deepseek.com/v1"
                    className="border rounded-lg px-3 py-1.5 text-sm w-64"
                  />
                </div>
              </div>

              {/* 百度语音配置 */}
              <div className="space-y-3 pt-2">
                <h3 className="text-sm font-semibold text-gray-800 border-b border-gray-200 pb-2">百度实时语音转文字</h3>
                <div className="flex justify-between items-center py-2 border-b border-gray-100">
                  <span className="text-gray-600">App ID</span>
                  <input
                    type="text"
                    value={editableConfig.baidu_speech_app_id}
                    onChange={(e) => setEditableConfig({ ...editableConfig, baidu_speech_app_id: e.target.value })}
                    placeholder="百度语音 App ID"
                    className="border rounded-lg px-3 py-1.5 text-sm w-64"
                  />
                </div>
                <div className="flex justify-between items-center py-2 border-b border-gray-100">
                  <span className="text-gray-600">API Key</span>
                  <input
                    type="text"
                    value={editableConfig.baidu_speech_api_key}
                    onChange={(e) => setEditableConfig({ ...editableConfig, baidu_speech_api_key: e.target.value })}
                    placeholder="百度语音 API Key"
                    className="border rounded-lg px-3 py-1.5 text-sm w-64"
                  />
                </div>
                <div className="flex justify-between items-center py-2 border-b border-gray-100">
                  <span className="text-gray-600">Secret Key</span>
                  <input
                    type="text"
                    value={editableConfig.baidu_speech_secret_key}
                    onChange={(e) => setEditableConfig({ ...editableConfig, baidu_speech_secret_key: e.target.value })}
                    placeholder="百度语音 Secret Key"
                    className="border rounded-lg px-3 py-1.5 text-sm w-64"
                  />
                </div>
              </div>

              <div className="flex items-center gap-3 pt-2">
                <button
                  onClick={handleSaveConfig}
                  disabled={configSaving}
                  className="inline-flex items-center px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
                >
                  <Save className="w-4 h-4 mr-2" />
                  {configSaving ? '保存中...' : '保存配置'}
                </button>
                {configSaved && (
                  <span className="text-sm text-green-600 flex items-center">
                    <CheckCircle className="w-4 h-4 mr-1" />
                    已保存，请重启后端服务
                  </span>
                )}
              </div>
            </div>
          ) : (
            <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-500">
              加载配置中...
            </div>
          )}
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
        )}

        {/* 管理员专属：用户管理 */}
        {isAdmin && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
              <Users className="w-5 h-5 mr-2 text-primary-600" />
              用户管理
            </h2>
            <p className="text-gray-600 text-sm mb-4">
              查看和管理系统中的所有用户账户，包括调整权限和账户状态。
            </p>
            <Link
              to="/admin/users"
              className="inline-flex items-center px-4 py-2.5 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors"
            >
              <Users className="w-4 h-4 mr-2" />
              进入用户管理
            </Link>
          </div>
        )}

        {/* 数据管理 — 仅管理员 */}
        {isAdmin && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <Database className="w-5 h-5 mr-2 text-primary-600" />
            数据管理
          </h2>
          <button
            onClick={handleClearLocal}
            className="flex items-center px-4 py-2.5 bg-red-50 text-red-700 rounded-lg hover:bg-red-100 transition-colors text-sm font-medium"
          >
            <Trash2 className="w-4 h-4 mr-2" />
            清除本地缓存数据
          </button>
          <p className="text-xs text-gray-400 mt-2">此操作将清除浏览器本地存储的访谈状态等临时数据，不会删除后端数据库中的访谈记录。</p>
        </div>
        )}

        {/* 关于 — 仅管理员 */}
        {isAdmin && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <Info className="w-5 h-5 mr-2 text-primary-600" />
            关于系统
          </h2>
          <p className="text-gray-600 text-sm leading-relaxed mb-4">
            经验萃取 AI 系统是一套基于 BEST 高能经验萃取方法论和五维价值评估标准的智能化访谈辅助系统。
            通过多轮对话引导，帮助萃取专家从业务高手处高效挖掘、结构化并封装高价值经验。
          </p>
          <div className="text-xs text-gray-400 space-y-1">
            <p>技术栈：FastAPI + React + TailwindCSS + SQLite</p>
            <p>AI 引擎：{llmConfig ? `${llmConfig.label} (${llmConfig.model})` : '-'}</p>
            <p>项目路径：experience-extraction-ai</p>
          </div>
        </div>
        )}
      </div>
    </div>
  );
}
