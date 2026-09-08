import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { LandingLayout } from './components/layout/LandingLayout'
import { AuthLayout } from './components/layout/AuthLayout'
import { DashboardLayout } from './components/layout/DashboardLayout'
import { ProtectedRoute, GuestRoute } from './components/auth/ProtectedRoute'
import { LandingPage } from './pages/LandingPage'
import { LoginPage } from './pages/auth/LoginPage'
import { SignupPage } from './pages/auth/SignupPage'
import { ForgotPasswordPage } from './pages/auth/ForgotPasswordPage'
import { OtpPage } from './pages/auth/OtpPage'
import { GitHubCallbackPage } from './pages/auth/GitHubCallbackPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { DashboardHomePage } from './pages/dashboard/DashboardHomePage'
import { ChatPage } from './pages/dashboard/ChatPage'
import { ProjectsPage } from './pages/dashboard/ProjectsPage'
import { LogsPage } from './pages/dashboard/LogsPage'
import { ChangesPage } from './pages/dashboard/ChangesPage'
import { ReportsPage } from './pages/dashboard/ReportsPage'
import { SettingsPage } from './pages/dashboard/SettingsPage'

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<LandingLayout />}>
          <Route index element={<LandingPage />} />
        </Route>

        <Route path="auth/callback" element={<GitHubCallbackPage />} />

        <Route element={<GuestRoute />}>
          <Route element={<AuthLayout />}>
            <Route path="login" element={<LoginPage />} />
            <Route path="signup" element={<SignupPage />} />
            <Route path="forgot-password" element={<ForgotPasswordPage />} />
            <Route path="verify-otp" element={<OtpPage />} />
          </Route>
        </Route>

        <Route element={<ProtectedRoute />}>
          <Route path="dashboard" element={<DashboardLayout />}>
            <Route index element={<DashboardHomePage />} />
            <Route path="chat" element={<ChatPage />} />
            <Route path="projects" element={<ProjectsPage />} />
            <Route path="logs" element={<LogsPage />} />
            <Route path="changes" element={<ChangesPage />} />
            <Route path="reports" element={<ReportsPage />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  )
}
