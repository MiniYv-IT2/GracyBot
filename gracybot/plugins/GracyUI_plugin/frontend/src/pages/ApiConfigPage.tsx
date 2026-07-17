import { motion } from 'framer-motion';
export default function ApiConfigPage() {
  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="glass-card p-6">
        <h2 className="text-2xl font-bold text-gradient mb-4">API密钥与提供商设置</h2>
      </motion.div>
    </div>
  );
}
