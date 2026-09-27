import React, { useState, useEffect } from 'react';
import { ConfigProvider, theme } from 'antd';
import viVN from 'antd/locale/vi_VN';
import enUS from 'antd/locale/en_US';
import { AppLayout } from './components/AppLayout';
import { SetupPage } from './pages/SetupPage';
import { MonitoringPage } from './pages/MonitoringPage';
import { HistoryPage } from './pages/HistoryPage';
import { getAutomationStatus } from './services/api';
import type { Language } from './i18n';


export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<string>('setup');
  const [isDarkMode, setIsDarkMode] = useState<boolean>(() => {
    return localStorage.getItem('d2f_theme') === 'dark';
  });
  const [lang, setLang] = useState<Language>(() => {
    return (localStorage.getItem('d2f_lang') as Language) || 'vi';
  });
  const [isRunning, setIsRunning] = useState<boolean>(false);

  // Sync theme to localStorage
  const handleToggleTheme = () => {
    const nextMode = !isDarkMode;
    setIsDarkMode(nextMode);
    localStorage.setItem('d2f_theme', nextMode ? 'dark' : 'light');
  };

  // Sync lang to localStorage
  const handleToggleLang = () => {
    const nextLang = lang === 'vi' ? 'en' : 'vi';
    setLang(nextLang);
    localStorage.setItem('d2f_lang', nextLang);
  };

  // Initial status check
  useEffect(() => {
    getAutomationStatus()
      .then((data) => {
        setIsRunning(data.is_running);
      })
      .catch(() => {});
  }, []);

  return (
    <ConfigProvider
      locale={lang === 'vi' ? viVN : enUS}
      theme={{
        algorithm: isDarkMode ? theme.darkAlgorithm : theme.defaultAlgorithm,
        token: {
          colorPrimary: '#2563eb',
          colorSuccess: '#10b981',
          colorWarning: '#f59e0b',
          colorError: '#ef4444',
          borderRadius: 10,
          fontFamily:
            '"Plus Jakarta Sans", "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
        },
        components: {
          Card: {
            borderRadiusLG: 14,
            boxShadowTertiary: isDarkMode
              ? '0 4px 20px rgba(0,0,0,0.5)'
              : '0 4px 20px rgba(0,0,0,0.03)',
          },
          Button: {
            borderRadius: 8,
            fontWeight: 500,
          },
          Table: {
            borderRadiusLG: 12,
          },
        },
      }}
    >
      <AppLayout
        currentTab={currentTab}
        onTabChange={setCurrentTab}
        isDarkMode={isDarkMode}
        onToggleTheme={handleToggleTheme}
        lang={lang}
        onToggleLang={handleToggleLang}
        isRunning={isRunning}
      >
        {currentTab === 'setup' && (
          <SetupPage
            lang={lang}
            onNavigateToMonitoring={() => setCurrentTab('monitoring')}
            onAutomationStarted={() => setIsRunning(true)}
          />
        )}
        {currentTab === 'monitoring' && (
          <MonitoringPage
            lang={lang}
            isRunning={isRunning}
            setIsRunning={setIsRunning}
          />
        )}
        {currentTab === 'history' && <HistoryPage lang={lang} />}
      </AppLayout>
    </ConfigProvider>
  );
};

export default App;
