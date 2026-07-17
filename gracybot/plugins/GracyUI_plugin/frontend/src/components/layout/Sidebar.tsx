import { useNavigate, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  LayoutDashboard, Users, Key, Puzzle,
  MessageSquare, Brain, Palette, Bot, FileText
} from 'lucide-react';

const menuItems = [
  { path: '/dashboard', icon: LayoutDashboard, label: '仪表盘' },
  { path: '/friends', icon: Users, label: '好友管理' },
  { path: '/api-config', icon: Key, label: 'API配置' },
  { path: '/plugins', icon: Puzzle, label: '插件商店' },
  { path: '/sessions', icon: MessageSquare, label: '会话管理' },
  { path: '/memories', icon: Brain, label: '记忆管理' },
  { path: '/characters', icon: Palette, label: '人物卡工坊' },
  { path: '/adapter', icon: Bot, label: '适配器连接' },
  { path: '/logs', icon: FileText, label: '日志中心' },
];

export default function Sidebar() {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <motion.aside
      initial={{ x: -80, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      transition={{ type: 'spring', damping: 22, stiffness: 180, delay: 0.1 }}
      className="fixed left-0 top-[60px] bottom-0 w-[240px] glass-card rounded-tl-none z-40 overflow-y-auto hidden lg:block"
    >
      <nav className="p-4 space-y-1">
        {menuItems.map((item, i) => {
          const isActive = location.pathname === item.path;
          const Icon = item.icon;

          return (
            <motion.button
              key={item.path}
              onClick={() => navigate(item.path)}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.15 + i * 0.04, type: 'spring', stiffness: 200 }}
              whileHover={{ x: 4 }}
              whileTap={{ scale: 0.97 }}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
                isActive
                  ? 'bg-gradient-to-r from-[#f0a8d0] to-[#d9b0ff] text-white shadow-md'
                  : 'hover:bg-white/40 text-gray-700'
              }`}
            >
              <Icon className="w-5 h-5 flex-shrink-0" />
              <span className="font-medium">{item.label}</span>
            </motion.button>
          );
        })}
      </nav>
    </motion.aside>
  );
}