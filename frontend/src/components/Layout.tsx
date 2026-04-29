import { Outlet, Link, useLocation } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { MessageSquare, Plus, Settings, Home, LogOut, User, Menu, X, LogIn, Users } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';

export function Layout() {
  const location = useLocation();
  const { user, logout, isAdmin } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // 路由切换时自动关闭移动端菜单
  useEffect(() => {
    setMobileMenuOpen(false);
  }, [location.pathname]);

  const navItems = [
    { path: '/', icon: Home, label: '首页' },
    { path: '/interviews', icon: MessageSquare, label: '访谈列表' },
    { path: '/interviews/new', icon: Plus, label: '新建访谈' },
    ...(isAdmin ? [{ path: '/admin/users', icon: Users, label: '用户管理' }] : []),
  ];

  const isSettingsActive = location.pathname === '/settings';

  return (
    <div className="flex h-screen bg-gray-50">
      {/* 桌面端 Sidebar */}
      <aside className="hidden md:flex w-64 bg-white border-r border-gray-200 flex-col">
        <div className="p-6 border-b border-gray-200">
          <h1 className="text-xl font-bold text-gray-900">经验萃取AI</h1>
          <p className="text-sm text-gray-500 mt-1">智能化访谈辅助系统</p>
        </div>

        <nav className="flex-1 p-4 space-y-1">
          {navItems.map((item) => {
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center px-4 py-3 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-primary-50 text-primary-700'
                    : 'text-gray-700 hover:bg-gray-100'
                }`}
              >
                <item.icon className="w-5 h-5 mr-3" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* User Info & Logout */}
        <div className="p-4 border-t border-gray-200 space-y-1">
          {user && (
            <div className="flex items-center gap-2 px-4 py-2 text-sm text-gray-600">
              <div className="w-7 h-7 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600">
                <User className="w-4 h-4" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-medium truncate">
                  {user.full_name || user.email}
                  {isAdmin && <span className="ml-1.5 text-xs text-amber-600 font-medium">[管理员]</span>}
                </p>
                <p className="text-xs text-gray-400 truncate">{user.email}</p>
              </div>
            </div>
          )}
          <Link
            to="/settings"
            className={`flex items-center px-4 py-3 w-full rounded-lg text-sm font-medium transition-colors ${
              isSettingsActive
                ? 'bg-primary-50 text-primary-700'
                : 'text-gray-700 hover:bg-gray-100'
            }`}
          >
            <Settings className="w-5 h-5 mr-3" />
            设置
          </Link>
          {user ? (
            <button
              onClick={logout}
              className="flex items-center px-4 py-3 w-full rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-100 transition-colors"
            >
              <LogOut className="w-5 h-5 mr-3" />
              退出登录
            </button>
          ) : (
            <Link
              to="/login"
              className="flex items-center px-4 py-3 w-full rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-100 transition-colors"
            >
              <LogIn className="w-5 h-5 mr-3" />
              登录
            </Link>
          )}
        </div>
      </aside>

      {/* 移动端顶部导航栏 */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-40 bg-white border-b border-gray-200">
        <div className="flex items-center justify-between px-4 py-3">
          <div>
            <h1 className="text-lg font-bold text-gray-900">经验萃取AI</h1>
          </div>
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="p-2 rounded-lg hover:bg-gray-100"
          >
            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>

        {/* 移动端下拉菜单 */}
        {mobileMenuOpen && (
          <div className="border-t border-gray-200 p-4 space-y-1 bg-white">
            {navItems.map((item) => {
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`flex items-center px-4 py-3 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-primary-50 text-primary-700'
                      : 'text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  <item.icon className="w-5 h-5 mr-3" />
                  {item.label}
                </Link>
              );
            })}
            <Link
              to="/settings"
              className={`flex items-center px-4 py-3 rounded-lg text-sm font-medium transition-colors ${
                isSettingsActive
                  ? 'bg-primary-50 text-primary-700'
                  : 'text-gray-700 hover:bg-gray-100'
              }`}
            >
              <Settings className="w-5 h-5 mr-3" />
              设置
            </Link>
            {user && (
              <div className="flex items-center gap-2 px-4 py-3 text-sm text-gray-600 border-t border-gray-100 mt-2">
                <div className="w-7 h-7 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600">
                  <User className="w-4 h-4" />
                </div>
                <span className="font-medium truncate">{user.full_name || user.email}</span>
              </div>
            )}
            {user ? (
              <button
                onClick={logout}
                className="flex items-center px-4 py-3 w-full rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-100 transition-colors"
              >
                <LogOut className="w-5 h-5 mr-3" />
                退出登录
              </button>
            ) : (
              <Link
                to="/login"
                className="flex items-center px-4 py-3 w-full rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-100 transition-colors"
              >
                <LogIn className="w-5 h-5 mr-3" />
                登录
              </Link>
            )}
          </div>
        )}
      </div>

      {/* Main Content */}
      <main className="flex-1 overflow-auto pt-14 md:pt-0">
        <Outlet />
      </main>
    </div>
  );
}
