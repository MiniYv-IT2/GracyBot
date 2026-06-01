# AI Bot 前端管理面板

一个基于 React + TypeScript 的二次元风格 AI Bot 管理前端面板，采用纯前端架构设计（无后端）。

## ✨ 特性

- 🎨 **二次元视觉风格** - 粉紫渐变主题 + 玻璃拟态设计
- 📱 **响应式布局** - PC端侧边栏 + 移动端底部导航
- 🔐 **模拟登录系统** - 前端认证（admin/admin）
- 📊 **实时设备监控** - CPU/内存/磁盘动态圆环图
- 💾 **持久化存储** - localStorage 保存所有配置
- 🎭 **10个功能模块** - 仪表盘、好友、API、插件、会话、记忆、人物卡、OneBot、日志

## 🚀 快速开始

### 安装依赖

```bash
npm install
```

### 启动开发服务器

```bash
npm run dev
```

访问 http://localhost:5173

### 构建生产版本

```bash
npm run build
```

## 📁 项目结构

```
ai-bot-frontend/
├── src/
│   ├── components/          # 组件
│   │   ├── layout/         # 布局组件
│   │   │   ├── TopBar.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   ├── BottomNav.tsx
│   │   │   └── ContentWrapper.tsx
│   │   └── ProtectedRoute.tsx
│   │
│   ├── pages/              # 页面
│   │   ├── LoginPage.tsx   # 登录页
│   │   ├── DashboardPage.tsx  # 仪表盘
│   │   ├── FriendsPage.tsx
│   │   ├── ApiConfigPage.tsx
│   │   └── OtherPages.tsx  # 其他页面占位
│   │
│   ├── stores/             # Zustand状态管理
│   │   ├── authStore.ts
│   │   ├── dashboardStore.ts
│   │   ├── deviceMonitorStore.ts
│   │   ├── apiConfigStore.ts
│   │   ├── hyperParamsStore.ts
│   │   ├── pluginStore.ts
│   │   ├── characterStore.ts
│   │   ├── memoryStore.ts
│   │   ├── onebotStore.ts
│   │   ├── logStore.ts
│   │   ├── friendStore.ts
│   │   └── sessionStore.ts
│   │
│   ├── types/              # TypeScript类型定义
│   │   └── index.ts
│   │
│   ├── App.tsx             # 主应用组件
│   ├── main.tsx            # 入口文件
│   └── index.css           # 全局样式（TailwindCSS）
│
├── tailwind.config.js      # Tailwind配置
├── postcss.config.js       # PostCSS配置
└── package.json
```

## 🎯 技术栈

| 类别 | 技术 |
|------|------|
| 框架 | React 18 + TypeScript |
| 构建工具 | Vite |
| 状态管理 | Zustand + persist中间件 |
| 路由 | React Router v6 |
| UI样式 | TailwindCSS |
| 图表 | ECharts |
| 动画 | Framer Motion |
| 通知 | react-hot-toast |
| 图标 | Lucide React |
| 日期 | dayjs |
| 文件导出 | file-saver |

## 🎨 设计规范

### 颜色主题
- **主色调**: 粉紫渐变 `#f8c8e8` → `#d9b0ff`
- **辅助色**: 淡蓝 `#a8d8ff` → `#7ec8ff`
- **背景**: 渐变 `from-pink-50 via-purple-50 to-blue-50`

### 组件样式
- **玻璃拟态卡片**: `glass-card` / `glass-card-hover`
- **按钮**: `btn-primary` / `btn-secondary` / `btn-danger`
- **输入框**: `input-field`
- **徽章**: `badge-success` / `badge-warning` / `badge-error` / `badge-info`

### 响应式断点
- **PC端**: ≥1024px - 固定侧边栏240px
- **平板**: 641px-1023px - 抽屉式菜单
- **手机**: ≤640px - 底部Tab导航

## 🔑 默认账号

- **用户名**: admin
- **密码**: admin

## 📦 状态管理

所有数据通过 Zustand stores 管理，并持久化到 localStorage：

1. **authStore** - 登录状态
2. **dashboardStore** - 仪表盘数据
3. **deviceMonitorStore** - 设备监控（CPU/内存/磁盘）
4. **apiConfigStore** - API配置
5. **hyperParamsStore** - 微调参数
6. **pluginStore** - 插件管理
7. **characterStore** - 人物卡
8. **memoryStore** - 记忆管理
9. **onebotStore** - OneBot连接
10. **logStore** - 日志中心
11. **friendStore** - 好友与用户组
12. **sessionStore** - 会话管理

## 🌟 核心功能

### 1. 登录页面
- 二次元飘浮背景动画
- 玻璃拟态登录卡片
- 模拟登录验证

### 2. 仪表盘
- 欢迎横幅
- 关键指标卡片（好友数、活跃会话、人物卡）
- 设备状态圆环图（ECharts动态渲染）
- 快捷操作按钮
- 最近日志摘要

### 3. 布局系统
- **顶部栏**: Logo、页面标题、设备状态、用户信息
- **侧边栏** (PC): 9个功能模块导航
- **底部导航** (移动): 5个常用入口 + 更多

### 4. 其他模块（占位页面）
- 好友管理
- API配置
- 插件商店
- 会话管理
- 记忆管理
- 人物卡工坊
- OneBot对接
- 日志中心

## 🔧 开发说明

### 添加新页面

1. 在 `src/pages/` 创建页面组件
2. 在 `src/App.tsx` 中添加路由
3. 在 `Sidebar.tsx` 和 `BottomNav.tsx` 中添加菜单项

### 自定义样式

编辑 `tailwind.config.js` 扩展主题：

```javascript
theme: {
  extend: {
    colors: { /* ... */ },
    animation: { /* ... */ },
  }
}
```

### 状态管理示例

```typescript
import { useDashboardStore } from '../stores/dashboardStore';

const { friendCount, refreshDashboard } = useDashboardStore();
```

## 📝 后续优化建议

1. **完善各功能模块页面** - 目前大部分为占位页面
2. **添加更多动画效果** - 页面切换、加载状态
3. **国际化支持** - i18n多语言
4. **主题切换** - 深色/浅色模式
5. **性能优化** - 代码分割、懒加载
6. **单元测试** - Jest + React Testing Library
7. **E2E测试** - Cypress / Playwright

## 📄 License

MIT

---

**开发者**: 灵羽工作室  
**版本**: v2.5.0 "星梦版"  
**最后更新**: 2026-05-24
