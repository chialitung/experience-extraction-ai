import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Users, ArrowLeft, Loader2, Trash2, Shield, ShieldOff,
  UserCheck, UserX, AlertTriangle,
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { authApi } from '@/services/api';
import type { User } from '@/types';

export function AdminUsersPage() {
  const { user: currentUser, isAdmin } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  const fetchUsers = async () => {
    if (!isAdmin) return;
    setLoading(true);
    setError(null);
    try {
      const res = await authApi.listUsers(0, 100);
      setUsers(res.data.items);
    } catch (err: any) {
      setError(err.response?.data?.detail || '加载用户列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!isAdmin) return;
    fetchUsers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAdmin]);

  const toggleActive = async (targetUser: User) => {
    if (!currentUser) return;
    if (targetUser.id === currentUser.id) {
      alert('不能禁用您自己的账户');
      return;
    }
    setUpdatingId(targetUser.id);
    try {
      await authApi.updateUser(targetUser.id, { is_active: !targetUser.is_active });
      setUsers(prev => prev.map(u => u.id === targetUser.id ? { ...u, is_active: !u.is_active } : u));
    } catch (err: any) {
      alert(err.response?.data?.detail || '操作失败');
    } finally {
      setUpdatingId(null);
    }
  };

  const toggleSuperuser = async (targetUser: User) => {
    if (!currentUser) return;
    if (targetUser.id === currentUser.id) {
      alert('不能取消您自己的管理员权限');
      return;
    }
    setUpdatingId(targetUser.id);
    try {
      await authApi.updateUser(targetUser.id, { is_superuser: !targetUser.is_superuser });
      setUsers(prev => prev.map(u => u.id === targetUser.id ? { ...u, is_superuser: !u.is_superuser } : u));
    } catch (err: any) {
      alert(err.response?.data?.detail || '操作失败');
    } finally {
      setUpdatingId(null);
    }
  };

  const handleDelete = async (targetUser: User) => {
    if (!currentUser) return;
    if (targetUser.id === currentUser.id) {
      alert('不能删除您自己的账户');
      return;
    }
    if (!confirm(`确定要删除用户 "${targetUser.full_name || targetUser.email}" 吗？此操作不可恢复，其所有访谈记录也将被删除。`)) {
      return;
    }
    setDeletingId(targetUser.id);
    try {
      await authApi.deleteUser(targetUser.id);
      setUsers(prev => prev.filter(u => u.id !== targetUser.id));
    } catch (err: any) {
      alert(err.response?.data?.detail || '删除失败');
    } finally {
      setDeletingId(null);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto p-8">
      <div className="mb-6">
        <Link
          to="/settings"
          className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700 mb-4"
        >
          <ArrowLeft className="w-4 h-4 mr-1" />
          返回设置
        </Link>
        <h1 className="text-2xl font-bold text-gray-900 flex items-center">
          <Users className="w-7 h-7 mr-3 text-primary-600" />
          用户管理
        </h1>
        <p className="text-gray-500 mt-2">管理系统中的所有用户账户</p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 flex items-center">
          <AlertTriangle className="w-5 h-5 text-red-600 mr-3" />
          <p className="text-red-700 text-sm">{error}</p>
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-6 py-3 font-medium text-gray-700">邮箱</th>
                <th className="text-left px-6 py-3 font-medium text-gray-700">昵称</th>
                <th className="text-left px-6 py-3 font-medium text-gray-700">状态</th>
                <th className="text-left px-6 py-3 font-medium text-gray-700">角色</th>
                <th className="text-left px-6 py-3 font-medium text-gray-700">创建时间</th>
                <th className="text-right px-6 py-3 font-medium text-gray-700">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {users.length === 0 && !loading && (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-gray-400">
                    暂无用户
                  </td>
                </tr>
              )}
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-6 py-4 text-gray-900">{u.email}</td>
                  <td className="px-6 py-4 text-gray-600">{u.full_name || '-'}</td>
                  <td className="px-6 py-4">
                    <button
                      onClick={() => toggleActive(u)}
                      disabled={updatingId === u.id}
                      className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
                        u.is_active
                          ? 'bg-green-100 text-green-700 hover:bg-green-200'
                          : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                      }`}
                    >
                      {u.is_active ? (
                        <><UserCheck className="w-3.5 h-3.5 mr-1" />已启用</>
                      ) : (
                        <><UserX className="w-3.5 h-3.5 mr-1" />已禁用</>
                      )}
                    </button>
                  </td>
                  <td className="px-6 py-4">
                    <button
                      onClick={() => toggleSuperuser(u)}
                      disabled={updatingId === u.id}
                      className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
                        u.is_superuser
                          ? 'bg-amber-100 text-amber-700 hover:bg-amber-200'
                          : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                      }`}
                    >
                      {u.is_superuser ? (
                        <><Shield className="w-3.5 h-3.5 mr-1" />管理员</>
                      ) : (
                        <><ShieldOff className="w-3.5 h-3.5 mr-1" />普通用户</>
                      )}
                    </button>
                  </td>
                  <td className="px-6 py-4 text-gray-500">
                    {new Date(u.created_at).toLocaleDateString('zh-CN')}
                  </td>
                  <td className="px-6 py-4 text-right">
                    <button
                      onClick={() => handleDelete(u)}
                      disabled={deletingId === u.id}
                      className="inline-flex items-center px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5 mr-1" />
                      {deletingId === u.id ? '删除中...' : '删除'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
