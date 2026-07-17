import { useNavigate, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  LayoutDashboard, Users, Key, Puzzle,
  MessageSquare, Brain, Palette, Bot, FileText
} from 'lucide-react';

interface MobileMenuProps {
  isOpen: boolean;
  onClose: () => void;
}

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

/** 紫色渐变汉堡图标（三横线） */
function HamburgerIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true">
      <defs>
        <linearGradient id="hamburgerGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#f0a8d0" />
          <stop offset="50%" stopColor="#d9b0ff" />
          <stop offset="100%" stopColor="#b890e8" />
        </linearGradient>
      </defs>
      <rect x="2.5" y="5" width="19" height="2.4" rx="1.2" fill="url(#hamburgerGrad)" />
      <rect x="2.5" y="11" width="19" height="2.4" rx="1.2" fill="url(#hamburgerGrad)" />
      <rect x="2.5" y="17" width="19" height="2.4" rx="1.2" fill="url(#hamburgerGrad)" />
    </svg>
  );
}

export default function MobileMenu({ isOpen, onClose }: MobileMenuProps) {
  const navigate = useNavigate();
  const location = useLocation();

  const handleNavigate = (path: string) => {
    navigate(path);
    onClose();
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* 半透明遮罩 */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
            className="fixed inset-0 top-[60px] bg-black/30 backdrop-blur-sm z-40 lg:hidden"
          />

          {/* 窄竖排侧边栏 */}
          <motion.div
            initial={{ x: '-100%' }}
            animate={{ x: 0 }}
            exit={{ x: '-100%' }}
            transition={{ type: 'spring', damping: 26, stiffness: 220 }}
            className="fixed top-[60px] left-0 bottom-0 w-52 glass-card rounded-l-none rounded-tr-2xl rounded-br-2xl z-50 lg:hidden overflow-y-auto shadow-2xl"
          >
            <nav className="py-2">
              {menuItems.map((item, i) => {
                const isActive = location.pathname === item.path;
                const Icon = item.icon;
                return (
                  <motion.button
                    key={item.path}
                    onClick={() => handleNavigate(item.path)}
                    initial={{ opacity: 0, x: -16 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.04 }}
                    whileTap={{ scale: 0.97 }}
                    className={`w-full flex items-center gap-3 px-5 py-3 transition-all ${
                      isActive
                        ? 'bg-gradient-to-r from-[#f0a8d0] to-[#d9b0ff] text-white shadow-sm'
                        : 'hover:bg-white/40 text-gray-700'
                    }`}
                  >
                    <Icon className="w-5 h-5 flex-shrink-0" />
                    <span className="text-sm font-medium">{item.label}</span>
                  </motion.button>
                );
              })}
            </nav>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

export { HamburgerIcon };
