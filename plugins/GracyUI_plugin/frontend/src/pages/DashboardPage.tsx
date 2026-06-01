import { useEffect, useRef, useState } from 'react';
import * as echarts from 'echarts';
import { motion } from 'framer-motion';
import { Users, MessageSquare, RefreshCw, Zap } from 'lucide-react';
import { useDashboardStore } from '../stores/dashboardStore';
import { useDeviceMonitorStore } from '../stores/deviceMonitorStore';

export default function DashboardPage() {
  const { friendCount, groupCount, systemVersion, fetchStats } = useDashboardStore();
  const { cpuPercent, cpuName, memoryPercent, memoryUsedGb, memoryTotalGb, diskPercent, diskUsedGb, diskTotalGb, startPolling, stopPolling } =
    useDeviceMonitorStore() as any;

  const [uptime, setUptime] = useState('');
  const [osInfo, setOsInfo] = useState('');
  const [hostname, setHostname] = useState('');

  const cpuChartRef = useRef<HTMLDivElement>(null);
  const memoryChartRef = useRef<HTMLDivElement>(null);
  const diskChartRef = useRef<HTMLDivElement>(null);

  const [cpuChart, setCpuChart] = useState<echarts.ECharts | null>(null);
  const [memoryChart, setMemoryChart] = useState<echarts.ECharts | null>(null);
  const [diskChart, setDiskChart] = useState<echarts.ECharts | null>(null);

  // 首次加载
  useEffect(() => {
    fetchStats();
    fetchSystemInfo();
    startPolling?.();
    return () => stopPolling?.();
  }, []);

  const fetchSystemInfo = async () => {
    try {
      const res = await fetch('/api/dashboard/system');
      const data = await res.json();
      setUptime(data.uptime ?? '');
      setOsInfo(data.os ?? '');
      setHostname(data.hostname ?? '');
    } catch {}
  };

  // 初始化圆环图
  useEffect(() => {
    const initChart = (ref: HTMLDivElement | null) => {
      if (!ref) return null;
      const chart = echarts.init(ref);
      return chart;
    };
    const cpu = initChart(cpuChartRef.current);
    const memory = initChart(memoryChartRef.current);
    const disk = initChart(diskChartRef.current);
    setCpuChart(cpu);
    setMemoryChart(memory);
    setDiskChart(disk);
    const handleResize = () => {
      cpu?.resize();
      memory?.resize();
      disk?.resize();
    };
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
      cpu?.dispose();
      memory?.dispose();
      disk?.dispose();
    };
  }, []);

  // 更新仪表盘数据
  useEffect(() => {
    const updateChart = (chart: echarts.ECharts | null, value: number, name: string) => {
      if (!chart) return;
      const option = {
        series: [{
          type: 'gauge',
          radius: '90%',
          startAngle: 225,
          endAngle: -45,
          min: 0, max: 100,
          itemStyle: { color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
            { offset: 0, color: '#f8c8e8' }, { offset: 1, color: '#d9b0ff' }
          ])},
          progress: { show: true, width: 18, roundCap: true },
          pointer: { show: false },
          axisLine: { lineStyle: { width: 18, color: [[1, '#f0f0f0']] } },
          axisTick: { show: false },
          splitLine: { show: false },
          axisLabel: { show: false },
          anchor: { show: false },
          title: { show: true, offsetCenter: [0, '70%'], fontSize: 14, color: '#999' },
          detail: { valueAnimation: true, offsetCenter: [0, '30%'], fontSize: 32, fontWeight: 'bold', color: '#666', formatter: '{value}%' },
          data: [{ value: Math.round(value), name }],
        }],
      };
      chart.setOption(option, true);
    };
    updateChart(cpuChart, cpuPercent, 'CPU');
    updateChart(memoryChart, memoryPercent, '内存');
    updateChart(diskChart, diskPercent, '磁盘');
  }, [cpuChart, memoryChart, diskChart, cpuPercent, memoryPercent, diskPercent]);

  const stats = [
    { icon: Users, label: '好友数量', value: friendCount, color: 'from-pink-400 to-pink-500' },
    { icon: MessageSquare, label: '群聊数量', value: groupCount, color: 'from-purple-400 to-purple-500' },
  ];

  return (
    <div className="space-y-6">
      {/* 欢迎横幅 */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-card p-6 bg-gradient-to-r from-primary-light/30 to-secondary/30"
      >
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div>
            <h2 className="text-2xl font-bold text-gradient mb-2">
              主人，今天Bot也很精神哦~ ✨
            </h2>
            <p className="text-gray-600">系统运行正常，所有服务状态良好</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <div className="bg-white/60 backdrop-blur-sm px-4 py-2 rounded-lg border border-white/40">
              <p className="text-xs text-gray-500 mb-1">系统版本</p>
              <p className="text-sm font-semibold text-gray-800">{systemVersion || '—'}</p>
            </div>
            <div className="bg-white/60 backdrop-blur-sm px-4 py-2 rounded-lg border border-white/40">
              <p className="text-xs text-gray-500 mb-1">操作系统</p>
              <p className="text-sm font-semibold text-gray-800">{osInfo || '—'}</p>
            </div>
            <div className="bg-white/60 backdrop-blur-sm px-4 py-2 rounded-lg border border-white/40">
              <p className="text-xs text-gray-500 mb-1">主机名</p>
              <p className="text-sm font-semibold text-gray-800">{hostname || '—'}</p>
            </div>
            <div className="bg-white/60 backdrop-blur-sm px-4 py-2 rounded-lg border border-white/40">
              <p className="text-xs text-gray-500 mb-1">运行时间</p>
              <p className="text-sm font-semibold text-gray-800">{uptime || '—'}</p>
            </div>
          </div>
        </div>
      </motion.div>

      {/* 关键指标 (2 张卡片) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {stats.map((stat, index) => {
          const Icon = stat.icon;
          return (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
              className="glass-card-hover p-6"
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600 mb-1">{stat.label}</p>
                  <p className="text-3xl font-bold text-gradient">{stat.value}</p>
                </div>
                <div className={`p-3 rounded-full bg-gradient-to-r ${stat.color} text-white`}>
                  <Icon className="w-6 h-6" />
                </div>
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* 系统状态圆环 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* CPU */}
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.3 }}
          className="glass-card p-6 flex flex-col items-center"
        >
          <div ref={cpuChartRef} className="h-[180px] w-full" />
          <p className="text-xs text-gray-500 mt-1 text-center truncate max-w-full px-2" title={cpuName}>
            {cpuName || '检测中...'}
          </p>
        </motion.div>
        {/* 内存 */}
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.4 }}
          className="glass-card p-6 flex flex-col items-center"
        >
          <div ref={memoryChartRef} className="h-[180px] w-full" />
          <p className="text-xs text-gray-500 mt-1">
            {memoryUsedGb > 0 ? `${memoryUsedGb} GB / ${memoryTotalGb} GB` : '检测中...'}
          </p>
        </motion.div>
        {/* 磁盘 */}
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.5 }}
          className="glass-card p-6 flex flex-col items-center"
        >
          <div ref={diskChartRef} className="h-[180px] w-full" />
          <p className="text-xs text-gray-500 mt-1">
            {diskUsedGb > 0 ? `${diskUsedGb} GB / ${diskTotalGb} GB` : '检测中...'}
          </p>
        </motion.div>
      </div>

      {/* 快捷操作 */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6 }}
        className="glass-card p-6"
      >
        <h3 className="text-lg font-bold mb-4 text-gradient">快捷操作</h3>
        <div className="flex flex-wrap gap-3">
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => { fetchStats(); fetchSystemInfo(); }}
            className="btn-secondary flex items-center gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            刷新数据
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className="btn-primary flex items-center gap-2"
          >
            <Zap className="w-4 h-4" />
            一键连接适配器
          </motion.button>
        </div>
      </motion.div>
    </div>
  );
}
