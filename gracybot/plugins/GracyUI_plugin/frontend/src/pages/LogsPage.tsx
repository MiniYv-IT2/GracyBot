import { useEffect, useState, useRef, useCallback } from 'react';
import { motion } from 'framer-motion';
import { RefreshCw, Filter, ChevronDown } from 'lucide-react';

interface LogEntry {
  time: string;
  level: string;
  source: string;
  message: string;
}

const LEVEL_COLORS: Record<string, string> = {
  INFO: '#4ade80',
  WARNING: '#fbbf24',
  WARN: '#fbbf24',
  ERROR: '#f87171',
  CRITICAL: '#ef4444',
  DEBUG: '#60a5fa',
};

const LEVEL_BG: Record<string, string> = {
  ERROR: 'rgba(248,113,113,0.08)',
  CRITICAL: 'rgba(239,68,68,0.12)',
  WARNING: 'rgba(251,191,36,0.06)',
  WARN: 'rgba(251,191,36,0.06)',
};

export default function LogsPage() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');
  const [showFilter, setShowFilter] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const fetchLogs = useCallback(async () => {
    try {
      const url = filter ? `/api/logs?page=1&page_size=200&level=${filter}` : '/api/logs?page=1&page_size=200';
      const res = await fetch(url);
      const data = await res.json();
      setLogs(data.entries || []);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  useEffect(() => {
    if (!autoRefresh) return;
    const t = setInterval(fetchLogs, 5000);
    return () => clearInterval(t);
  }, [autoRefresh, fetchLogs]);

  // Auto-scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const formatTime = (t: string) => {
    if (!t) return '';
    // Show only HH:mm:ss for brevity
    return t.length >= 19 ? t.slice(11, 19) : t;
  };

  return (
    <div className="h-[calc(100vh-60px)] flex flex-col overflow-hidden">
      {/* 顶部操作栏 */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-wrap items-center gap-3 flex-shrink-0 pb-3"
      >
        <button
          onClick={fetchLogs}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/70 border border-pink-200 text-pink-600 text-sm hover:bg-pink-50 transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          刷新
        </button>

        <div className="relative">
          <button
            onClick={() => setShowFilter(!showFilter)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/70 border border-purple-200 text-purple-600 text-sm hover:bg-purple-50 transition-colors"
          >
            <Filter className="w-4 h-4" />
            {filter || '全部'}
            <ChevronDown className="w-3 h-3" />
          </button>
          {showFilter && (
            <div className="absolute top-full mt-1 left-0 bg-white rounded-lg shadow-lg border border-purple-100 z-10 py-1 min-w-[100px]">
              {['', 'INFO', 'WARNING', 'ERROR', 'DEBUG'].map((lvl) => (
                <button
                  key={lvl}
                  onClick={() => { setFilter(lvl); setShowFilter(false); }}
                  className="block w-full text-left px-4 py-1.5 text-sm hover:bg-purple-50 transition-colors"
                  style={{ color: lvl ? (LEVEL_COLORS[lvl] || '#666') : '#666' }}
                >
                  {lvl || '全部'}
                </button>
              ))}
            </div>
          )}
        </div>

        <label className="flex items-center gap-1.5 text-xs text-gray-500 ml-auto">
          <input
            type="checkbox"
            checked={autoRefresh}
            onChange={(e) => setAutoRefresh(e.target.checked)}
            className="w-3.5 h-3.5 accent-pink-400"
          />
          自动刷新
        </label>
      </motion.div>

      {/* 日志窗口 — 二次元风 */}
      <motion.div
        ref={containerRef}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="flex-1 min-h-0 flex flex-col overflow-hidden rounded-2xl relative"
        style={{
          background: 'linear-gradient(135deg, #fff5f9 0%, #fdf2ff 50%, #f5f3ff 100%)',
          boxShadow: `
            0 0 0 2px rgba(236, 72, 153, 0.15),
            0 4px 24px rgba(168, 85, 247, 0.1),
            inset 0 0 0 1px rgba(255,255,255,0.6)
          `,
        }}
      >
        {/* 装饰边框 */}
        <div className="absolute inset-0 rounded-2xl pointer-events-none"
          style={{
            border: '2px solid transparent',
            background: 'linear-gradient(135deg, #f9a8d4, #d8b4fe, #a5b4fc) border-box',
            WebkitMask: 'linear-gradient(#fff 0 0) padding-box, linear-gradient(#fff 0 0)',
            WebkitMaskComposite: 'xor',
            maskComposite: 'exclude',
          }}
        />

        {/* 日志标题栏 */}
        <div className="flex items-center gap-2 px-5 py-3 border-b border-pink-100 relative z-[1]">
          <div className="flex gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full bg-red-400" />
            <div className="w-2.5 h-2.5 rounded-full bg-yellow-400" />
            <div className="w-2.5 h-2.5 rounded-full bg-green-400" />
          </div>
          <span className="text-sm font-medium text-gray-500 ml-3 select-none">
            📋 GracyBot 日志中枢
          </span>
          <span className="text-xs text-gray-400 ml-auto select-none">
            {logs.length} 条
          </span>
        </div>

        {/* 日志内容区 */}
        <div className="flex-1 min-h-0 overflow-y-auto relative z-[1]"
          style={{
            fontFamily: '"Cascadia Code", "Fira Code", "JetBrains Mono", "Consolas", "Monaco", monospace',
          }}
        >
          {loading && logs.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <RefreshCw className="w-6 h-6 animate-spin text-pink-400" />
            </div>
          ) : (
            <div className="py-3">
              {logs.map((log, i) => {
                const isError = log.level === 'ERROR' || log.level === 'CRITICAL';
                const isWarn = log.level === 'WARNING' || log.level === 'WARN';
                return (
                  <div
                    key={i}
                    className="flex items-start gap-3 px-5 py-[3px] transition-colors hover:bg-white/40"
                    style={{
                      backgroundColor: LEVEL_BG[log.level],
                      minHeight: 'fit-content',
                    }}
                  >
                    {/* 时间戳 */}
                    <span className="text-[11px] sm:text-xs text-gray-400 whitespace-nowrap select-none shrink-0 leading-relaxed pt-px"
                      style={{ fontFamily: 'monospace' }}
                    >
                      {formatTime(log.time)}
                    </span>

                    {/* 等级标签 */}
                    <span
                      className="text-[10px] sm:text-[11px] font-bold px-1.5 py-px rounded shrink-0 select-none leading-relaxed"
                      style={{
                        color: LEVEL_COLORS[log.level] || '#888',
                        backgroundColor: `${LEVEL_COLORS[log.level] || '#888'}18`,
                        border: `0.5px solid ${LEVEL_COLORS[log.level] || '#888'}33`,
                        minWidth: '44px',
                        textAlign: 'center',
                      }}
                    >
                      {log.level}
                    </span>

                    {/* 消息内容 */}
                    <span
                      className="text-xs sm:text-sm leading-relaxed break-all whitespace-pre-wrap"
                      style={{
                        color: isError ? '#dc2626' : isWarn ? '#b45309' : '#374151',
                        fontWeight: isError ? 600 : 400,
                        lineHeight: '1.6',
                        // Mobile: ~40 chars/line, Desktop: ~100 chars/line
                        maxWidth: 'calc(100vw - 160px)',
                      }}
                    >
                      {log.message}
                    </span>
                  </div>
                );
              })}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        {/* 右下角装饰 */}
        <div className="absolute bottom-3 right-4 text-4xl opacity-10 select-none pointer-events-none z-[1]">
          🌸
        </div>
      </motion.div>
    </div>
  );
}
