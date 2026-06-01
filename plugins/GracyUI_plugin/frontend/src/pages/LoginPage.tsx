import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import toast from 'react-hot-toast';
import { useAuthStore } from '../stores/authStore';
import { Lock, User } from 'lucide-react';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const login = useAuthStore((state) => state.login);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) {
      toast.error('请输入用户名和密码');
      return;
    }
    setIsLoading(true);

    const success = await login(username, password);

    if (success) {
      toast.success('欢迎回来，主人~ ✨');
      navigate('/dashboard');
    } else {
      toast.error('密码错误，请重试');
    }

    setIsLoading(false);
  };

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden bg-gradient-to-br from-pink-100 via-purple-100 to-blue-100">
      {/* 背景装饰 */}
      <div className="absolute inset-0 overflow-hidden">
        {[...Array(20)].map((_, i) => (
          <motion.div
            key={i}
            className="absolute text-4xl opacity-20"
            initial={{ 
              x: Math.random() * window.innerWidth,
              y: Math.random() * window.innerHeight,
            }}
            animate={{ 
              y: [null, Math.random() * -100],
              rotate: [0, 360],
            }}
            transition={{ 
              duration: 10 + Math.random() * 10,
              repeat: Infinity,
              ease: "linear",
            }}
          >
            {['⭐', '🌸', '✨', '💫', '🎀'][Math.floor(Math.random() * 5)]}
          </motion.div>
        ))}
      </div>

      {/* 登录卡片 */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="glass-card p-8 w-full max-w-md mx-4 relative z-10"
      >
        {/* Logo和标题 */}
        <div className="text-center mb-8">
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ delay: 0.2, type: "spring", stiffness: 200 }}
            className="mb-4"
          >
            <img
              src="/gracy.png"
              alt="GracyUI"
              className="w-36 h-36 sm:w-40 sm:h-40 mx-auto object-contain drop-shadow-lg"
            />
          </motion.div>
          <h1 className="text-3xl font-bold text-gradient mb-2">
            GracyUI
          </h1>
          <p className="text-pink-400 text-sm font-medium">
            叮咚！Gracy酱喊你登录管理面板啦~
          </p>
        </div>

        {/* 登录表单 */}
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* 用户名输入 */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 block">
              用户名
            </label>
            <div className="relative">
              <User className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="input-field pl-10"
                placeholder="请输入用户名"
                required
              />
            </div>
          </div>

          {/* 密码输入 */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 block">
              密码
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input-field pl-10"
                placeholder="请输入密码"
                required
              />
            </div>
          </div>

          {/* 登录按钮 */}
          <motion.button
            type="submit"
            disabled={isLoading}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            className="btn-primary w-full py-3 text-base"
          >
            {isLoading ? (
              <span className="flex items-center justify-center gap-2">
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                  className="w-5 h-5 border-2 border-white border-t-transparent rounded-full"
                />
                登录中...
              </span>
            ) : (
              '登录'
            )}
          </motion.button>
        </form>

        {/* 底部提示 */}
        <div className="mt-6 text-center text-xs text-gray-500 space-y-1">
          <p>系统版本 v1.9.2 "GracyUI"</p>
          <p className="text-gray-400">© 2025-2026 GracyBot. All rights reserved.</p>
        </div>
      </motion.div>
    </div>
  );
}
