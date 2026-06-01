import { useNavigate, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import toast from 'react-hot-toast';
import { useAuthStore } from '../../stores/authStore';
import { useDeviceMonitorStore } from '../../stores/deviceMonitorStore';
import { LogOut, Cpu, MemoryStick, HardDrive, Menu } from 'lucide-react';
import { useEffect, useState } from 'react';
import MobileMenu from './MobileMenu';

export default function TopBar() {
  const navigate = useNavigate();
  const location = useLocation();
  const { logout } = useAuthStore();
  const { cpuPercent, memoryPercent, diskPercent, startPolling, stopPolling } =
    useDeviceMonitorStore() as any;
  const [menuOpen, setMenuOpen] = useState(false);
  const [avatarUrl, setAvatarUrl] = useState('');
  const [botName, setBotName] = useState('Bot');

  useEffect(() => {
    startPolling?.();
    fetch('/api/bot-info')
      .then((r) => r.json())
      .then((d) => {
        setAvatarUrl(d.avatar_url || '');
        setBotName(d.nickname || 'Bot');
      })
      .catch(() => {});
    return () => stopPolling?.();
  }, []);

  const handleLogout = () => {
    logout();
    toast.success('已安全退出~');
    navigate('/login');
  };

  const getPageTitle = () => {
    const path = location.pathname;
    const titles: Record<string, string> = {
      '/dashboard': '仪表盘',
      '/friends': '好友管理',
      '/api-config': 'API配置',
      '/plugins': '插件商店',
      '/sessions': '会话管理',
      '/memories': '记忆管理',
      '/characters': '人物卡工坊',
      '/adapter': '适配器连接',
      '/logs': '日志中心',
    };
    return titles[path] || 'AI Bot 管理中枢';
  };

  return (
    <>
      <motion.header
        initial={{ y: -100 }}
        animate={{ y: 0 }}
        className="fixed top-0 left-0 right-0 h-[60px] glass-card z-50 px-6 flex items-center justify-between"
      >
        {/* 移动端汉堡菜单按钮 */}
        <motion.button
          whileTap={{ scale: 0.9 }}
          onClick={() => setMenuOpen(prev => !prev)}
          className="lg:hidden p-1.5 -ml-1.5 mr-0.5 rounded-lg hover:bg-purple-100/30 transition-colors"
          aria-label="切换菜单"
        >
          <Menu className="w-[22px] h-[22px] text-[#d9b0ff]" />
        </motion.button>

        {/* Logo和标题 */}
        <div className="flex items-center gap-2 sm:gap-3">
          <img
            src="/gracy.png"
            alt="GracyUI"
            className="w-9 h-9 sm:w-10 sm:h-10 object-contain"
          />
          <div>
            <h1 className="font-bold text-sm sm:text-lg text-gradient">{getPageTitle()}</h1>
            <p className="text-[10px] sm:text-xs text-gray-500">GracyUI</p>
          </div>
        </div>

        {/* 设备状态 */}
        <div className="hidden md:flex items-center gap-4 text-sm">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/50">
            <Cpu className="w-4 h-4 text-primary" />
            <span>CPU: {cpuPercent.toFixed(0)}%</span>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/50">
            <MemoryStick className="w-4 h-4 text-secondary" />
            <span>内存: {memoryPercent.toFixed(0)}%</span>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/50">
            <HardDrive className="w-4 h-4 text-purple-500" />
            <span>磁盘: {diskPercent.toFixed(0)}%</span>
          </div>
        </div>

        {/* 用户信息 */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-gradient-to-r from-primary-light to-primary text-white">
            {avatarUrl ? (
              <img
                src={avatarUrl}
                alt="Bot"
                className="w-6 h-6 rounded-full object-cover border border-white/30"
              />
            ) : (
              <span className="text-sm">🤖</span>
            )}
            <span className="text-sm font-medium hidden sm:inline">{botName}</span>
          </div>
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={handleLogout}
            className="p-2 rounded-full hover:bg-red-100 text-gray-600 hover:text-red-600 transition-colors"
            title="退出登录"
          >
            <LogOut className="w-5 h-5" />
          </motion.button>
        </div>
      </motion.header>

      {/* 移动端滑出菜单 — 放在 header 外面避免层级冲突 */}
      <MobileMenu isOpen={menuOpen} onClose={() => setMenuOpen(false)} />
    </>
  );
}