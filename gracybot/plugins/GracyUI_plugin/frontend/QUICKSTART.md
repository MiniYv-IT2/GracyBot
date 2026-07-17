# 快速使用指南

## 🎯 项目已完成功能

### ✅ 核心架构
- [x] React + TypeScript + Vite 项目初始化
- [x] TailwindCSS 二次元主题配置
- [x] Zustand 状态管理（12个stores）
- [x] React Router 路由系统
- [x] 响应式布局（PC/移动端）

### ✅ 页面组件
- [x] 登录页面（含动画背景）
- [x] 仪表盘首页（完整功能）
- [x] 其他9个模块占位页面

### ✅ 布局系统
- [x] 顶部导航栏（TopBar）
- [x] PC端侧边栏（Sidebar）
- [x] 移动端底部导航（BottomNav）
- [x] 内容区包装器（ContentWrapper）

### ✅ 状态管理 Stores
- [x] authStore - 认证管理
- [x] dashboardStore - 仪表盘数据
- [x] deviceMonitorStore - 设备监控
- [x] apiConfigStore - API配置
- [x] hyperParamsStore - 微调参数
- [x] pluginStore - 插件管理
- [x] characterStore - 人物卡
- [x] memoryStore - 记忆管理
- [x] onebotStore - OneBot对接
- [x] logStore - 日志中心
- [x] friendStore - 好友管理
- [x] sessionStore - 会话管理

## 🚀 立即体验

### 1. 启动项目
开发服务器已经在运行：http://localhost:5173

如果未运行，执行：
```bash
npm run dev
```

### 2. 登录系统
- 用户名：`admin`
- 密码：`admin`

### 3. 浏览功能

#### 仪表盘（默认页面）
- ✨ 欢迎横幅动画
- 📊 三个指标卡片（好友数、活跃会话、人物卡）
- 🔄 三个设备圆环图（CPU/内存/磁盘，实时更新）
- ⚡ 快捷操作按钮
- 📝 最近3条日志摘要

#### 其他页面
点击侧边栏或底部导航可切换到其他模块（目前为占位页面）

## 🎨 设计亮点

### 1. 视觉效果
- **粉紫渐变主题**：从 `#f8c8e8` 到 `#d9b0ff`
- **玻璃拟态卡片**：半透明模糊背景
- **动态圆环图**：ECharts弹性动画
- **飘浮背景**：登录页星星/花朵动画

### 2. 交互体验
- **平滑过渡**：Framer Motion动画
- **Toast提示**：react-hot-toast通知
- **悬停效果**：卡片上浮、按钮缩放
- **加载动画**：登录按钮旋转loading

### 3. 响应式设计
- **PC端**：固定侧边栏 + 三列布局
- **平板**：抽屉菜单 + 双列布局
- **手机**：底部Tab + 单列堆叠

## 📦 数据存储

所有数据自动保存到浏览器 localStorage：

```javascript
// 查看存储的数据
console.log(localStorage.getItem('ai-bot-auth'));
console.log(localStorage.getItem('ai-bot-dashboard'));
console.log(localStorage.getItem('ai-bot-device'));
// ... 等等
```

## 🔧 自定义修改

### 修改主题颜色
编辑 `tailwind.config.js`：

```javascript
colors: {
  primary: {
    light: '#你的颜色',
    DEFAULT: '#你的颜色',
    dark: '#你的颜色',
  },
}
```

### 添加新页面
1. 创建文件 `src/pages/NewPage.tsx`
2. 在 `src/App.tsx` 添加路由
3. 在 `Sidebar.tsx` 添加菜单项

### 修改模拟数据
编辑对应的 store 文件，例如：
- `src/stores/dashboardStore.ts` - 修改仪表盘初始数据
- `src/stores/logStore.ts` - 修改日志示例

## 🌟 下一步建议

### 优先级高
1. 完善好友管理页面（增删改查）
2. 完善API配置页面（表单验证）
3. 完善人物卡工坊（AI生成Prompt）
4. 完善日志中心（筛选/导出）

### 优先级中
5. 添加深色模式切换
6. 添加国际化支持
7. 优化移动端体验
8. 添加更多动画效果

### 优先级低
9. 性能优化（代码分割）
10. 单元测试
11. E2E测试
12. PWA支持

## 💡 技术要点

### Zustand Store 使用
```typescript
import { useDashboardStore } from './stores/dashboardStore';

function MyComponent() {
  const { friendCount, refreshDashboard } = useDashboardStore();
  
  return (
    <button onClick={refreshDashboard}>
      好友数: {friendCount}
    </button>
  );
}
```

### ECharts 圆环图
参考 `DashboardPage.tsx` 中的实现，使用 gauge 类型图表。

### Framer Motion 动画
```typescript
<motion.div
  initial={{ opacity: 0, y: 20 }}
  animate={{ opacity: 1, y: 0 }}
  transition={{ duration: 0.5 }}
>
  内容
</motion.div>
```

## 📞 技术支持

如有问题，请检查：
1. 浏览器控制台是否有错误
2. Node.js 版本是否 >= 18
3. 依赖是否正确安装（`node_modules` 存在）

---

**祝使用愉快！** 🎉
