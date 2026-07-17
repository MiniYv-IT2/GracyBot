import { create } from 'zustand';
import type { DeviceMonitorState } from '../types';

export const useDeviceMonitorStore = create<DeviceMonitorState>((set) => {
  let timer: ReturnType<typeof setInterval> | null = null;

  return {
    cpuPercent: 0,
    cpuName: '',
    memoryPercent: 0,
    memoryUsedGb: 0,
    memoryTotalGb: 0,
    diskPercent: 0,
    diskUsedGb: 0,
    diskTotalGb: 0,

    fetchSystem: async () => {
      try {
        const res = await fetch('/api/dashboard/system');
        const data = await res.json();
        set({
          cpuPercent: data.cpu_percent ?? 0,
          cpuName: data.cpu_name ?? '',
          memoryPercent: data.memory_percent ?? 0,
          memoryUsedGb: data.memory_used_gb ?? 0,
          memoryTotalGb: data.memory_total_gb ?? 0,
          diskPercent: data.disk_percent ?? 0,
          diskUsedGb: data.disk_used_gb ?? 0,
          diskTotalGb: data.disk_total_gb ?? 0,
        });
      } catch {
        // 静默失败
      }
    },

    // 启动轮询（每 3 秒）
    startPolling: () => {
      const store = useDeviceMonitorStore.getState();
      store.fetchSystem();
      if (!timer) {
        timer = setInterval(() => {
          useDeviceMonitorStore.getState().fetchSystem();
        }, 3000);
      }
    },

    // 停止轮询
    stopPolling: () => {
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
    },
  } as DeviceMonitorState & { startPolling: () => void; stopPolling: () => void };
}) as any;
