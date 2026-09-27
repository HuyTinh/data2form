import React, { useState, useEffect, useRef } from 'react';
import {
  Row,
  Col,
  Card,
  Statistic,
  Progress,
  Tag,
  Space,
  Input,
  Radio,
  Button,
  Typography,
  Image,
  Empty,
  Switch,
  Table,
} from 'antd';
import {
  SyncOutlined,
  CheckCircleOutlined,
  SearchOutlined,
  ClearOutlined,
  CameraOutlined,
} from '@ant-design/icons';
import { getAutomationStatus } from '../services/api';
import type { LogItem, ParentResult, RowResult } from '../types';
import { translations, type Language } from '../i18n';

const { Text, Title } = Typography;

interface MonitoringPageProps {
  lang: Language;
  isRunning: boolean;
  setIsRunning: (running: boolean) => void;
}

export const MonitoringPage: React.FC<MonitoringPageProps> = ({
  lang,
  isRunning,
  setIsRunning,
}) => {
  const t = translations[lang];

  const [currentRow, setCurrentRow] = useState(0);
  const [totalRows, setTotalRows] = useState(0);
  const [logs, setLogs] = useState<LogItem[]>([]);
  const [screenshots, setScreenshots] = useState<string[]>([]);
  const [rowResults, setRowResults] = useState<RowResult[]>([]);
  const [detailResults, setDetailResults] = useState<ParentResult[]>([]);
  const [logFilter, setLogFilter] = useState<string>('all');
  const [searchLogQuery, setSearchLogQuery] = useState('');
  const [autoScroll, setAutoScroll] = useState(true);

  const logContainerRef = useRef<HTMLDivElement>(null);

  // Poll status every 1s
  useEffect(() => {
    let timer: ReturnType<typeof setInterval>;


    const fetchStatus = async () => {
      try {
        const data = await getAutomationStatus();
        setIsRunning(data.is_running);
        setCurrentRow(data.current_row);
        setTotalRows(data.total_rows);
        setScreenshots(data.screenshots || []);
        setRowResults(data.row_results || []);
        setDetailResults(data.detail_results || []);

        if (data.logs && data.logs.length > 0) {
          setLogs(data.logs);
        }
      } catch (err) {
        console.error('Error fetching automation status:', err);
      }
    };

    fetchStatus();
    timer = setInterval(fetchStatus, 1000);

    return () => clearInterval(timer);
  }, [setIsRunning]);

  // Auto scroll logs
  useEffect(() => {
    if (autoScroll && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  // Filter logs
  const filteredLogs = logs.filter((item) => {
    const msg = item.message || item.msg || '';
    const matchLevel = logFilter === 'all' || item.level === logFilter;
    const matchQuery =
      !searchLogQuery ||
      msg.toLowerCase().includes(searchLogQuery.toLowerCase()) ||
      Boolean(item.time && item.time.toLowerCase().includes(searchLogQuery.toLowerCase()));
    return matchLevel && matchQuery;
  });

  const percent = totalRows > 0 ? Math.min(100, Math.round((currentRow / totalRows) * 100)) : 0;
  const failedRowCount = rowResults.filter((result) => result.status === 'failed').length;
  const rowResultColumns = [
    { title: t.monitor_row, dataIndex: 'row', key: 'row', width: 80 },
    {
      title: t.monitor_result,
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (status: RowResult['status']) => (
        <Tag color={status === 'completed' ? 'success' : status === 'failed' ? 'error' : 'processing'}>
          {status === 'completed' ? t.monitor_actions_done : status === 'failed' ? t.monitor_row_failed : t.monitor_row_running}
        </Tag>
      ),
    },
    {
      title: t.monitor_details,
      key: 'errors',
      render: (_: unknown, result: RowResult) => result.errors.length
        ? result.errors.map((error) => `${error.field}: ${error.message}`).join(' · ')
        : t.monitor_not_saved_verified,
    },
  ];

  const getLogColor = (level: string) => {
    switch (level) {
      case 'success':
        return '#52c41a';
      case 'warning':
        return '#faad14';
      case 'error':
        return '#ff4d4f';
      default:
        return '#4096ff';
    }
  };

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {/* 1. Statistics Cards & Progress Bar */}
      <Row gutter={[16, 16]}>
        <Col xs={12} sm={6}>
          <Card bordered={false}>
            <Statistic
              title={t.stat_total_rows}
              value={totalRows}
              prefix={<SyncOutlined style={{ color: '#1677ff' }} />}
            />
          </Card>
        </Col>

        <Col xs={12} sm={6}>
          <Card bordered={false}>
            <Statistic
              title={t.stat_completed_rows}
              value={currentRow}
              prefix={<CheckCircleOutlined style={{ color: '#52c41a' }} />}
              suffix={`/ ${totalRows}`}
            />
          </Card>
        </Col>

        <Col xs={12} sm={6}>
          <Card bordered={false}>
            <div style={{ marginBottom: 4 }}>
              <Text type="secondary" style={{ fontSize: 13 }}>
                {t.stat_status}
              </Text>
            </div>
            <div style={{ marginTop: 8 }}>
              {isRunning ? (
                <Tag
                  icon={<SyncOutlined spin />}
                  color="processing"
                  style={{ fontSize: 14, padding: '4px 10px' }}
                >
                  {t.status_running}
                </Tag>
              ) : failedRowCount > 0 ? (
                <Tag icon={<CheckCircleOutlined />} color="error" style={{ fontSize: 14, padding: '4px 10px' }}>
                  {t.monitor_completed_with_errors.replace('{count}', String(failedRowCount))}
                </Tag>
              ) : percent === 100 ? (
                <Tag
                  icon={<CheckCircleOutlined />}
                  color="success"
                  style={{ fontSize: 14, padding: '4px 10px' }}
                >
                  {t.status_completed}
                </Tag>
              ) : (
                <Tag color="default" style={{ fontSize: 14, padding: '4px 10px' }}>
                  {t.status_idle}
                </Tag>
              )}
            </div>
          </Card>
        </Col>

        <Col xs={12} sm={6}>
          <Card bordered={false}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <div style={{ marginBottom: 4 }}>
                  <Text type="secondary" style={{ fontSize: 13 }}>
                    {t.stat_progress}
                  </Text>
                </div>
                <Title level={3} style={{ margin: 0 }}>
                  {percent}%
                </Title>
              </div>
              <Progress
                type="circle"
                percent={percent}
                size={54}
                status={isRunning ? 'active' : failedRowCount > 0 ? 'exception' : percent === 100 ? 'success' : 'normal'}
              />
            </div>
          </Card>
        </Col>
      </Row>

      <Card bordered={false} title={t.monitor_row_results_title}>
        <Table<RowResult>
          size="small"
          rowKey="row"
          dataSource={rowResults}
          columns={rowResultColumns}
          pagination={{ pageSize: 5, hideOnSinglePage: true }}
          locale={{ emptyText: t.monitor_no_row_results }}
          scroll={{ x: 520 }}
        />
      </Card>

      {detailResults.length > 0 && (
        <Card bordered={false} title={t.plan_execution_results}>
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            {detailResults.map((parent) => (
              <Card key={`${parent.parent_key}-${parent.row}`} size="small">
                <Space direction="vertical" size="small" style={{ width: '100%' }}>
                  <Space wrap>
                    <Text strong>{t.plan_parent_key_label}: {parent.parent_key}</Text>
                    <Tag color={parent.status === 'completed' ? 'success' : parent.status === 'failed' ? 'error' : 'processing'}>
                      {parent.status}
                    </Tag>
                    {parent.partial_state && <Tag color="warning">{t.plan_partial_state}</Tag>}
                  </Space>
                  {parent.tables.map((table) => (
                    <div key={table.table_id} style={{ padding: '8px 10px', border: '1px solid #f0f0f0', borderRadius: 8 }}>
                      <Space wrap>
                        <Text strong>{table.name}</Text>
                        <Tag color={table.status === 'completed' ? 'success' : table.status === 'failed' ? 'error' : 'default'}>
                          {table.status === 'skipped' ? t.plan_no_rows : table.status}
                        </Tag>
                        {table.partial_state && <Tag color="warning">{t.plan_partial_state}</Tag>}
                        <Text type="secondary">{table.rows.length} {t.total_records}</Text>
                      </Space>
                      {table.rows.map((row) => (
                        <div key={row.row} style={{ marginTop: 4, paddingLeft: 10 }}>
                          <Text type={row.status === 'failed' ? 'danger' : 'secondary'}>
                            #{row.row} · {row.status}
                            {row.partial_state ? ` · ${t.plan_partial_state}` : ''}
                            {row.errors.length ? ` · ${row.errors.map((error) => `${error.field}: ${error.message}`).join('; ')}` : ''}
                          </Text>
                        </div>
                      ))}
                      {table.errors.map((error, index) => (
                        <div key={`${error.field}-${index}`} style={{ marginTop: 4 }}>
                          <Text type="danger">{error.field}: {error.message}</Text>
                        </div>
                      ))}
                    </div>
                  ))}
                  {parent.errors.map((error, index) => (
                    <Text key={`${error.field}-${index}`} type="danger">{error.field}: {error.message}</Text>
                  ))}
                </Space>
              </Card>
            ))}
          </Space>
        </Card>
      )}

      {/* 2. Console Logs & Screenshots Gallery */}
      <Row gutter={[16, 16]}>
        {/* Terminal Logs (16 cols) */}
        <Col xs={24} lg={16}>
          <Card
            bordered={false}
            title={
              <Space>
                <div
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    background: isRunning ? '#52c41a' : '#d9d9d9',
                    boxShadow: isRunning ? '0 0 8px #52c41a' : 'none',
                  }}
                />
                <span>{t.console_logs_title}</span>
              </Space>
            }
            extra={
              <Space wrap size="small">
                <Input
                  placeholder={t.search_logs}
                  prefix={<SearchOutlined style={{ color: '#bfbfbf' }} />}
                  value={searchLogQuery}
                  onChange={(e) => setSearchLogQuery(e.target.value)}
                  size="small"
                  style={{ width: 140 }}
                  allowClear
                />
                <Radio.Group
                  value={logFilter}
                  onChange={(e) => setLogFilter(e.target.value)}
                  size="small"
                >
                  <Radio.Button value="all">{t.filter_all}</Radio.Button>
                  <Radio.Button value="info">{t.filter_info}</Radio.Button>
                  <Radio.Button value="success">{t.filter_success}</Radio.Button>
                  <Radio.Button value="warning">{t.filter_warning}</Radio.Button>
                  <Radio.Button value="error">{t.filter_error}</Radio.Button>
                </Radio.Group>
                <Button
                  size="small"
                  icon={<ClearOutlined />}
                  onClick={() => setLogs([])}
                  title={t.btn_clear_logs}
                />
              </Space>
            }
          >
            <div
              ref={logContainerRef}
              style={{
                height: 380,
                background: '#0d1117',
                color: '#c9d1d9',
                fontFamily: 'Consolas, Monaco, "Courier New", monospace',
                fontSize: 12,
                padding: '12px 16px',
                borderRadius: 8,
                overflowY: 'auto',
                boxShadow: 'inset 0 2px 6px rgba(0,0,0,0.5)',
              }}
            >
              {filteredLogs.length === 0 ? (
                <div style={{ color: '#8b949e', textAlign: 'center', marginTop: 160 }}>
                  {logs.length === 0 ? '--- Chưa có log ghi nhận ---' : 'Không có log phù hợp bộ lọc'}
                </div>
              ) : (
                filteredLogs.map((log, index) => {
                  const msg = log.message || log.msg || '';
                  return (
                    <div
                      key={index}
                      style={{
                        lineHeight: '22px',
                        borderBottom: '1px solid rgba(255,255,255,0.04)',
                        padding: '2px 0',
                      }}
                    >
                      {log.time ? (
                        <span style={{ color: '#8b949e', marginRight: 8 }}>[{log.time}]</span>
                      ) : null}
                      <span
                        style={{
                          color: getLogColor(log.level),
                          fontWeight: 600,
                          marginRight: 8,
                          textTransform: 'uppercase',
                        }}
                      >
                        [{log.level}]
                      </span>
                      <span style={{ wordBreak: 'break-word' }}>{msg}</span>
                    </div>
                  );
                })
              )}
            </div>

            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginTop: 8,
              }}
            >
              <Text type="secondary" style={{ fontSize: 11 }}>
                Hiển thị {filteredLogs.length} / {logs.length} bản ghi logs
              </Text>
              <Space size="small">
                <Text type="secondary" style={{ fontSize: 11 }}>
                  Cuộn tự động:
                </Text>
                <Switch size="small" checked={autoScroll} onChange={setAutoScroll} />
              </Space>
            </div>
          </Card>
        </Col>

        {/* Screenshots Gallery (8 cols) */}
        <Col xs={24} lg={8}>
          <Card
            bordered={false}
            title={
              <Space>
                <CameraOutlined style={{ color: '#fa8c16' }} />
                <span>{t.screenshots_title}</span>
              </Space>
            }
            extra={
              <Tag color={screenshots.length > 0 ? 'error' : 'default'}>
                {screenshots.length}
              </Tag>
            }
          >
            {screenshots.length === 0 ? (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={t.no_screenshots}
                style={{ margin: '80px 0' }}
              />
            ) : (
              <div style={{ height: 380, overflowY: 'auto', paddingRight: 4 }}>
                <Image.PreviewGroup>
                  <Row gutter={[10, 10]}>
                    {screenshots.map((src, idx) => (
                      <Col span={12} key={idx}>
                        <div
                          style={{
                            borderRadius: 6,
                            overflow: 'hidden',
                            border: '1px solid rgba(0,0,0,0.1)',
                          }}
                        >
                          <Image
                            src={src.startsWith('/') ? src : `/static/${src}`}
                            alt={`Lỗi dòng ${idx + 1}`}
                            style={{ height: 110, objectFit: 'cover', width: '100%' }}
                          />
                          <div
                            style={{
                              padding: '4px 6px',
                              fontSize: 10,
                              background: 'rgba(0,0,0,0.03)',
                              textAlign: 'center',
                            }}
                          >
                            Ảnh lỗi #{idx + 1}
                          </div>
                        </div>
                      </Col>
                    ))}
                  </Row>
                </Image.PreviewGroup>
              </div>
            )}
          </Card>
        </Col>
      </Row>
    </Space>
  );
};
