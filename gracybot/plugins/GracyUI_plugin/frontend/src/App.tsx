import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { useEffect } from 'react';
import { useAuthStore } from './stores/authStore';
import TopBar from './components/layout/TopBar';
import Sidebar from './components/layout/Sidebar';
import ContentWrapper from './components/layout/ContentWrapper';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import FriendsPage from './pages/FriendsPage';
import ApiConfigPage from './pages/ApiConfigPage';
import PluginsPage, { SessionsPage, MemoriesPage, CharactersPage, AdapterPage } from './pages/OtherPages';
import LogsPage from './pages/LogsPage';

function AppContent() {
  const checkAuth = useAuthStore((state) => state.checkAuth);
  const isLoggedIn = useAuthStore((state) => state.isLoggedIn);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  if (!isLoggedIn) {
    return (
      <>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
        <Toaster position="top-center" toastOptions={{
          style: {
            background: 'rgba(255, 255, 255, 0.9)',
            backdropFilter: 'blur(10px)',
            border: '1px solid rgba(217, 176, 255, 0.3)',
          },
        }} />
      </>
    );
  }

  return (
    <>
      <TopBar />
      <Sidebar />
      <ContentWrapper>
        <Routes>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/friends" element={<FriendsPage />} />
          <Route path="/api-config" element={<ApiConfigPage />} />
          <Route path="/plugins" element={<PluginsPage />} />
          <Route path="/sessions" element={<SessionsPage />} />
          <Route path="/memories" element={<MemoriesPage />} />
          <Route path="/characters" element={<CharactersPage />} />
          <Route path="/adapter" element={<AdapterPage />} />
          <Route path="/logs" element={<LogsPage />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </ContentWrapper>
      <Toaster position="top-center" toastOptions={{
        style: {
          background: 'rgba(255, 255, 255, 0.9)',
          backdropFilter: 'blur(10px)',
          border: '1px solid rgba(217, 176, 255, 0.3)',
        },
      }} />
    </>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
}

export default App;
