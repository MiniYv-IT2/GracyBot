import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
  ],
  // 优化构建性能
  optimizeDeps: {
    // 预构建依赖，减少启动时的编译
    include: ['react', 'react-dom', 'framer-motion', 'echarts', 'zustand'],
    // 排除不需要预构建的包
    exclude: [],
  },
  // 开发服务器优化
  server: {
    // 监听所有IPv4地址
    host: '0.0.0.0',
    port: 5173,
    // 允许外部域名访问
    allowedHosts: ['d.ztso.xyz', 'localhost', '127.0.0.1'],
    // 启用热更新
    hmr: {
      overlay: true,
    },
    // 监听优化
    watch: {
      // 忽略 node_modules 和 .git
      ignored: ['**/node_modules/**', '**/.git/**'],
      // 使用轮询模式（更稳定）
      usePolling: false,
    },
    // 减少日志输出
    open: false,
  },
  // 构建优化
  build: {
    // 代码分割
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('react') || id.includes('react-dom')) {
              return 'react-vendor';
            }
            if (id.includes('framer-motion')) {
              return 'animation';
            }
            if (id.includes('echarts')) {
              return 'charts';
            }
            if (id.includes('zustand')) {
              return 'state';
            }
          }
        },
      },
    },
    // 启用 sourcemap（生产环境可关闭）
    sourcemap: false,
    // 压缩输出
    minify: 'esbuild',
  },
  // 减少控制台输出
  logLevel: 'warn',
  // 清除控制台
  clearScreen: true,
})
