import { motion } from 'framer-motion';
const Page = ({ title }: { title: string }) => (
  <div className="space-y-6">
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="glass-card p-6">
      <h2 className="text-2xl font-bold text-gradient mb-4">{title}</h2>
    </motion.div>
  </div>
);
export default function PluginsPage() { return <Page title="插件商店" />; }
export function SessionsPage() { return <Page title="会话管理" />; }
export function MemoriesPage() { return <Page title="记忆管理" />; }
export function CharactersPage() { return <Page title="人物卡工坊" />; }
export function AdapterPage() { return <Page title="适配器连接" />; }
