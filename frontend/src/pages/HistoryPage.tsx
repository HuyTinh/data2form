import React, { useState, useEffect } from 'react';
import {
  Card,
  Table,
  Tag,
  Button,
  Space,
  Input,
  Modal,
  Typography,
  message,
} from 'antd';
import {
  HistoryOutlined,
  EyeOutlined,
  DownloadOutlined,
  ReloadOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import { getHistory, getHistoryLogs, getDownloadUrl } from '../services/api';
import type { HistoryItem, LogItem } from '../types';
import { translations, type Language } from '../i18n';


const { Text } = Typography;

interface HistoryPageProps {
  lang: Language;
}

export const HistoryPage: React.FC<HistoryPageProps> = ({ lang }) => {
  const t = translations[lang];

  const [historyList, setHistoryList] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  // Modal Logs State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalLogs, setModalLogs] = useState<LogItem[]>([]);
  const [modalLoading, setModalLoading] = useState(false);
  const [selectedItem, setSelectedItem] = useState<HistoryItem | null>(null);

  const fetchHistoryData = async () => {
    try {
      setLoading(true);
      const data = await getHistory();
      setHistoryList(data);
    } catch {
      message.error('Lỗi khi tải lịch sử thực thi!');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistoryData();
  }, []);

  const handleOpenLogs = async (item: HistoryItem) => {
    setSelectedItem(item);
    setIsModalOpen(true);
    try {
      setModalLoading(true);
      const logs = await getHistoryLogs(item.id);
      setModalLogs(logs);
    } catch {
      message.error('Lỗi khi tải nhật ký chi tiết!');
    } finally {
      setModalLoading(false);
    }
  };

  const filteredHistory = historyList.filter(
    (item) =>
      item.filename.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.start_time.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.status.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const columns = [
    {
      title: t.hist_col_id,
      dataIndex: 'id',
      key: 'id',
      width: 70,
      align: 'center' as const,
    },
    {
      title: t.hist_col_time,
      dataIndex: 'start_time',
      key: 'start_time',
      width: 170,
    },
    {
      title: t.hist_col_filename,
      dataIndex: 'filename',
      key: 'filename',
      ellipsis: true,
      render: (text: string) => <Text strong>{text}</Text>,
    },
    {
      title: t.hist_col_rows,
      dataIndex: 'total_rows',
      key: 'total_rows',
      width: 100,
      align: 'center' as const,
    },
    {
      title: t.hist_col_status,
      dataIndex: 'status',
      key: 'status',
      width: 180,
      render: (status: string) => {
        if (status === 'Success' || status.includes('thành công')) {
          return <Tag color="success">✓ Thành công</Tag>;
        }
        if (status.includes('errors') || status.includes('lỗi')) {
          return <Tag color="warning">⚠ Hoàn thành có lỗi</Tag>;
        }
        return <Tag color="default">{status}</Tag>;
      },
    },
    {
      title: t.hist_col_actions,
      key: 'actions',
      width: 280,
      align: 'center' as const,
      render: (_: any, record: HistoryItem) => (
        <Space size="small" wrap={false}>
          <Button
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handleOpenLogs(record)}
          >
            {t.btn_view_logs}
          </Button>
          <Button
            size="small"
            type="primary"
            ghost
            icon={<DownloadOutlined />}
            href={getDownloadUrl(record.id)}
            target="_blank"
          >
            {t.btn_download_zip}
          </Button>
        </Space>
      ),
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
    <Card
      bordered={false}
      title={
        <Space>
          <HistoryOutlined style={{ color: '#1677ff' }} />
          <span>{t.hist_title}</span>
        </Space>
      }
      extra={
        <Space>
          <Input
            placeholder="Tìm kiếm lịch sử..."
            prefix={<SearchOutlined style={{ color: '#bfbfbf' }} />}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ width: 220 }}
            allowClear
          />
          <Button icon={<ReloadOutlined />} onClick={fetchHistoryData} loading={loading}>
            Làm mới
          </Button>
        </Space>
      }
    >
      <Table
        dataSource={filteredHistory}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 10, showSizeChanger: true }}
        size="middle"
        scroll={{ x: 'max-content' }}
      />

      {/* Modal View Logs */}
      <Modal
        title={
          <div>
            <span>{t.modal_logs_title}</span>
            {selectedItem && (
              <div style={{ fontSize: 12, fontWeight: 'normal', color: '#8c8c8c', marginTop: 4 }}>
                Tệp: {selectedItem.filename} | Bắt đầu: {selectedItem.start_time} | {selectedItem.total_rows} dòng
              </div>
            )}
          </div>
        }
        open={isModalOpen}
        onCancel={() => setIsModalOpen(false)}
        footer={[
          <Button key="close" type="primary" onClick={() => setIsModalOpen(false)}>
            Đóng
          </Button>,
        ]}
        width={780}
      >
        <div
          style={{
            maxHeight: 480,
            overflowY: 'auto',
            background: '#0d1117',
            padding: 16,
            borderRadius: 8,
            fontFamily: 'Consolas, Monaco, monospace',
            fontSize: 12,
            color: '#c9d1d9',
          }}
        >
          {modalLoading ? (
            <div style={{ textAlign: 'center', padding: '40px 0', color: '#8b949e' }}>
              Đang tải dữ liệu nhật ký...
            </div>
          ) : modalLogs.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px 0', color: '#8b949e' }}>
              {t.no_logs}
            </div>
          ) : (
            modalLogs.map((log, idx) => {
              const msg = log.message || log.msg || '';
              return (
                <div
                  key={idx}
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
      </Modal>
    </Card>
  );
};
