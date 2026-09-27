import React, { useState } from 'react';
import { Layout, Menu, Button, Space, Typography, Tag, Switch, Grid } from 'antd';
import {
  SettingOutlined,
  DashboardOutlined,
  HistoryOutlined,
  SunOutlined,
  MoonOutlined,
  GlobalOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from '@ant-design/icons';
import { translations, type Language } from '../i18n';


const { Header, Sider, Content } = Layout;
const { Title, Text } = Typography;

interface AppLayoutProps {
  currentTab: string;
  onTabChange: (tab: string) => void;
  isDarkMode: boolean;
  onToggleTheme: () => void;
  lang: Language;
  onToggleLang: () => void;
  isRunning: boolean;
  children: React.ReactNode;
}

export const AppLayout: React.FC<AppLayoutProps> = ({
  currentTab,
  onTabChange,
  isDarkMode,
  onToggleTheme,
  lang,
  onToggleLang,
  isRunning,
  children,
}) => {
  const t = translations[lang];
  const screens = Grid.useBreakpoint();
  const isMobile = !screens.md;
  const [userCollapsed, setUserCollapsed] = useState<boolean | null>(null);
  const collapsed = userCollapsed ?? !screens.lg;

  const menuItems = [
    {
      key: 'setup',
      icon: <SettingOutlined />,
      label: t.nav_setup,
    },
    {
      key: 'monitoring',
      icon: <DashboardOutlined />,
      label: (
        <Space>
          <span>{t.nav_monitoring}</span>
          {isRunning && <span className="ant-badge-status-dot ant-badge-status-processing" />}
        </Space>
      ),
    },
    {
      key: 'history',
      icon: <HistoryOutlined />,
      label: t.nav_history,
    },
  ];

  return (
    <Layout style={{ height: '100vh', overflow: 'hidden' }}>
      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        width={220}
        collapsedWidth={isMobile ? 0 : 80}
        style={{
          height: '100vh',
          position: isMobile && !collapsed ? 'fixed' : 'sticky',
          top: 0,
          left: 0,
          background: isDarkMode ? '#141414' : '#ffffff',
          borderRight: isDarkMode
            ? '1px solid rgba(255,255,255,0.08)'
            : '1px solid rgba(0,0,0,0.06)',
          boxShadow: isDarkMode
            ? '1px 0 6px rgba(0,0,0,0.4)'
            : '1px 0 6px rgba(0,0,0,0.05)',
          zIndex: 10,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <div
          style={{
            height: 64,
            padding: collapsed ? '16px 0' : '16px 20px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-start',
            gap: 10,
            background: isDarkMode ? '#141414' : '#ffffff',
            borderBottom: isDarkMode
              ? '1px solid rgba(255,255,255,0.08)'
              : '1px solid rgba(0,0,0,0.06)',
            transition: 'all 0.2s',
          }}
        >
          <div
            style={{
              width: 32,
              height: 32,
              minWidth: 32,
              borderRadius: 8,
              background: '#1677ff',
              color: '#fff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 'bold',
              fontSize: 14,
              boxShadow: '0 2px 8px rgba(22, 119, 255, 0.4)',
            }}
          >
            D2F
          </div>
          {!collapsed && (
            <div style={{ overflow: 'hidden', whiteSpace: 'nowrap' }}>
              <Title level={5} style={{ margin: 0, lineHeight: 1.2 }}>
                Data2Form <span style={{ color: '#1677ff' }}>Pro</span>
              </Title>
              <Text type="secondary" style={{ fontSize: 10 }}>
                v2.5.0
              </Text>
            </div>
          )}
        </div>

        <Menu
          mode="inline"
          selectedKeys={[currentTab]}
          items={menuItems}
          onClick={({ key }) => {
            onTabChange(key);
            if (isMobile) setUserCollapsed(true);
          }}
          style={{
            flex: 1,
            overflowY: 'auto',
            borderRight: 0,
            marginTop: 8,
            background: 'transparent',
          }}
        />
      </Sider>

      {isMobile && !collapsed && (
        <div
          aria-hidden="true"
          onClick={() => setUserCollapsed(true)}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.28)',
            zIndex: 9,
          }}
        />
      )}

      <Layout style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <Header
          style={{
            padding: isMobile ? '0 12px' : '0 24px',
            background: isDarkMode ? '#141414' : '#ffffff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: isDarkMode
              ? '1px solid rgba(255,255,255,0.08)'
              : '1px solid rgba(0,0,0,0.06)',
            boxShadow: '0 1px 4px rgba(0,0,0,0.03)',
            height: 64,
            flexShrink: 0,
          }}
        >
          <Space size={isMobile ? 8 : 'middle'} style={{ minWidth: 0, flex: 1, overflow: 'hidden' }}>
            <Button
              type="text"
              icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => setUserCollapsed(!collapsed)}
              aria-label={collapsed ? 'Mở menu' : 'Thu gọn menu'}
              title={collapsed ? 'Mở menu' : 'Thu gọn menu'}
              style={{ fontSize: '16px', width: 36, height: 36 }}
            />
            <Title
              level={isMobile ? 5 : 4}
              style={{
                margin: 0,
                fontWeight: 600,
                minWidth: 0,
                maxWidth: isMobile ? 110 : undefined,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {currentTab === 'setup' && t.nav_setup}
              {currentTab === 'monitoring' && t.nav_monitoring}
              {currentTab === 'history' && t.nav_history}
            </Title>
            {isRunning ? (
              <Tag color="processing" style={{ padding: isMobile ? '1px 5px' : '2px 8px', borderRadius: 12, whiteSpace: 'nowrap' }}>
                ● {t.status_running}
              </Tag>
            ) : (
              <Tag color="default" style={{ padding: isMobile ? '1px 5px' : '2px 8px', borderRadius: 12, whiteSpace: 'nowrap' }}>
                {t.status_idle}
              </Tag>
            )}
          </Space>

          <Space size={isMobile ? 4 : 'middle'} style={{ flexShrink: 0 }}>
            <Button
              type="text"
              icon={<GlobalOutlined />}
              onClick={onToggleLang}
              style={{ fontWeight: 500 }}
            >
              {lang.toUpperCase()}
            </Button>
            <Space size="small">
              <Switch
                checked={isDarkMode}
                onChange={onToggleTheme}
                checkedChildren={<MoonOutlined />}
                unCheckedChildren={<SunOutlined />}
              />
            </Space>
          </Space>
        </Header>

        <Content
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: isMobile ? '12px' : '20px 24px',
            minHeight: 0,
          }}
        >
          {children}
        </Content>
      </Layout>
    </Layout>
  );
};
