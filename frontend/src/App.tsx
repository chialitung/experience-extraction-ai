import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from '@/contexts/AuthContext';
import { ProtectedRoute, AdminRoute } from '@/components/ProtectedRoute';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { Layout } from '@/components/Layout';
import { HomePage } from '@/pages/HomePage';
import { InterviewListPage } from '@/pages/InterviewListPage';
import { InterviewCreatePage } from '@/pages/InterviewCreatePage';
import { BlueprintPage } from '@/pages/BlueprintPage';
import { InterviewChatPage } from '@/pages/InterviewChatPage';
import { ReportPage } from '@/pages/ReportPage';
import { SettingsPage } from '@/pages/SettingsPage';
import { AuthPage } from '@/pages/AuthPage';
import { ForgotPasswordPage } from '@/pages/ForgotPasswordPage';
import { ResetPasswordPage } from '@/pages/ResetPasswordPage';
import { AdminUsersPage } from '@/pages/AdminUsersPage';
import { SKIP_AUTH } from '@/config/auth';

function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* 公开路由 */}
            <Route path="/login" element={<AuthPage />} />
            <Route path="/auth" element={<AuthPage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />

            {/* 受保护路由 —— 根据 SKIP_AUTH 决定是否跳过登录 */}
            <Route path="/" element={
              SKIP_AUTH ? <Layout /> : (
                <ProtectedRoute>
                  <Layout />
                </ProtectedRoute>
              )
            }>
              <Route index element={
                <ErrorBoundary>
                  <HomePage />
                </ErrorBoundary>
              } />
              <Route path="interviews" element={
                <ErrorBoundary>
                  <InterviewListPage />
                </ErrorBoundary>
              } />
              <Route path="interviews/new" element={
                <ErrorBoundary>
                  <InterviewCreatePage />
                </ErrorBoundary>
              } />
              <Route path="interviews/:id/blueprint" element={
                <ErrorBoundary>
                  <BlueprintPage />
                </ErrorBoundary>
              } />
              <Route path="interviews/:id/chat" element={
                <ErrorBoundary>
                  <InterviewChatPage />
                </ErrorBoundary>
              } />
              <Route path="interviews/:id/output" element={
                <ErrorBoundary>
                  <ReportPage defaultView="materials" />
                </ErrorBoundary>
              } />
              <Route path="interviews/:id/report" element={
                <ErrorBoundary>
                  <ReportPage defaultView="report" />
                </ErrorBoundary>
              } />
              <Route path="settings" element={
                <ErrorBoundary>
                  <SettingsPage />
                </ErrorBoundary>
              } />
              <Route path="admin/users" element={
                <AdminRoute>
                  <ErrorBoundary>
                    <AdminUsersPage />
                  </ErrorBoundary>
                </AdminRoute>
              } />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ErrorBoundary>
  );
}

export default App;
