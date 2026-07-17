import { useNavigate, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import { 
  LayoutDashboard, Users, Puzzle, MessageSquare, MoreHorizontal
} from 'lucide-react';

// 移动端只显示5个主要入口
const mobileMenuItems = [
  { path: '/dashboard', icon: LayoutDashboard, label: '首页' },
  { path: '/friends', icon: Users, label: '好友' },
  { path: '/plugins', icon: Puzzle, label: '插件' },
  { path: '/sessions', icon: MessageSquare, label: '会话' },
];

export default function BottomNav() {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <nav className="fixed bottom-0 left-0 right-0 h-[60px] glass-card border-b-0 rounded-bl-none rounded-br-none z-40 lg:hidden">
      <div className="flex items-center justify-around h-full px-2">
        {mobileMenuItems.map((item) => {
          const isActive = location.pathname === item.path;
          const Icon = item.icon;
          
          return (
            <motion.button
              key={item.path}
              onClick={() => navigate(item.path)}
              whileTap={{ scale: 0.9 }}
              className={`flex flex-col items-center gap-1 px-3 py-2 rounded-lg transition-all ${
                isActive
                  ? 'text-primary'
                  : 'text-gray-600'
              }`}
            >
              <Icon className="w-5 h-5" />
              <span className="text-xs">{item.label}</span>
            </motion.button>
          );
        })}
        
        {/* 更多按钮 */}
        <motion.button
          onClick={() => navigate('/characters')}
          whileTap={{ scale: 0.9 }}
          className="flex flex-col items-center gap-1 px-3 py-2 rounded-lg text-gray-600"
        >
          <MoreHorizontal className="w-5 h-5" />
          <span className="text-xs">更多</span>
        </motion.button>
      </div>
    </nav>
  );
}
