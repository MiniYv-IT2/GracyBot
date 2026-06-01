import { motion } from 'framer-motion';
import { Users } from 'lucide-react';

export default function FriendsPage() {
  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="glass-card p-6">
        <div className="flex items-center gap-3 mb-4">
          <Users className="w-8 h-8 text-primary" />
          <h2 className="text-2xl font-bold text-gradient">好友与用户组管理</h2>
        </div>
      </motion.div>
    </div>
  );
}
