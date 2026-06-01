// 认证相关类型
export interface AuthState {
  isLoggedIn: boolean;
  userRole: 'admin' | 'user';
  username: string;
  token: string;
  login: (username: string, password: string) => Promise<boolean>;
  logout: () => void;
  checkAuth: () => Promise<void>;
}

// 仪表盘相关类型
export interface DashboardState {
  friendCount: number;
  groupCount: number;
  systemVersion: string;
  lastUpdate: number;
  loading: boolean;
  fetchStats: () => Promise<void>;
}

// 设备监控相关类型
export interface DeviceStats {
  cpuPercent: number;
  cpuName: string;
  memoryPercent: number;
  memoryUsedGb: number;
  memoryTotalGb: number;
  diskPercent: number;
  diskUsedGb: number;
  diskTotalGb: number;
}

export interface DeviceMonitorState extends DeviceStats {
  fetchSystem: () => Promise<void>;
}

// API配置相关类型
export type ApiProvider = 'openai' | 'oneapi' | 'custom';

export interface ApiConfigState {
  provider: ApiProvider;
  apiKey: string;
  baseUrl: string;
  model: string;
  testConnection: () => Promise<boolean>;
  saveConfig: () => void;
}

// 微调参数相关类型
export type ParamPreset = 'creative' | 'balanced' | 'precise';

export interface HyperParamsState {
  temperature: number;
  topP: number;
  presencePenalty: number;
  frequencyPenalty: number;
  maxTokens: number;
  preset: ParamPreset;
  applyPreset: (preset: ParamPreset) => void;
  resetToDefault: () => void;
  updateParam: (key: keyof HyperParamsState, value: number) => void;
}

// 插件相关类型
export interface Plugin {
  id: string;
  name: string;
  description: string;
  version: string;
  author: string;
  icon: string;
  enabled: boolean;
  installed: boolean;
}

export interface PluginStoreState {
  installedPlugins: Plugin[];
  availablePlugins: Plugin[];
  installPlugin: (pluginId: string) => void;
  uninstallPlugin: (pluginId: string) => void;
  togglePlugin: (pluginId: string, enabled: boolean) => void;
  fetchPlugins: () => void;
}

// 人物卡相关类型
export type CharacterScope = 'group' | 'private' | 'all';

export interface Character {
  id: string;
  name: string;
  avatar: string;
  description: string;
  systemPrompt: string;
  scope: CharacterScope;
  adminOnly: boolean;
  createdAt: number;
}

export interface CharacterStoreState {
  characters: Character[];
  currentCharacter: Character | null;
  createCharacter: (data: Omit<Character, 'id' | 'createdAt'>) => void;
  updateCharacter: (id: string, data: Partial<Character>) => void;
  deleteCharacter: (id: string) => void;
  setCurrentCharacter: (character: Character | null) => void;
  generatePrompt: (description: string) => Promise<string>;
  importCharacter: (json: string) => void;
  exportCharacter: (id: string) => void;
}

// 记忆相关类型
export interface Memory {
  id: string;
  key: string;
  value: string;
  createdAt: number;
}

export interface MemoryStoreState {
  globalMemories: Memory[];
  sessionMemories: Record<string, Memory[]>;
  similarityThreshold: number;
  addGlobalMemory: (key: string, value: string) => void;
  deleteGlobalMemory: (id: string) => void;
  addSessionMemory: (sessionId: string, key: string, value: string) => void;
  clearSessionMemories: (sessionId: string) => void;
  setSimilarityThreshold: (threshold: number) => void;
  exportMemories: () => void;
  importMemories: (json: string) => void;
}

// 适配器相关类型
export type AdapterStatus = 'connected' | 'disconnected' | 'connecting';
export type AdapterProtocol = 'ws' | 'http';

export interface AdapterState {
  status: AdapterStatus;
  wsUrl: string;
  accessToken: string;
  protocol: AdapterProtocol;
  autoReconnect: boolean;
  connect: () => void;
  disconnect: () => void;
  testConnection: () => void;
  updateConfig: (config: Partial<AdapterState>) => void;
}

// 日志相关类型
export type LogLevel = 'info' | 'warn' | 'error';

export interface LogEntry {
  id: string;
  timestamp: number;
  level: LogLevel;
  message: string;
}

export interface LogStoreState {
  logs: LogEntry[];
  filterLevel: LogLevel | 'all';
  addLog: (level: LogLevel, message: string) => void;
  clearLogs: () => void;
  setFilterLevel: (level: LogLevel | 'all') => void;
  exportLogs: () => void;
  simulateLog: () => void;
}

// 好友相关类型
export interface Friend {
  uid: string; // QQ号
  nickname: string;
  remark?: string;
  permission: 'user' | 'admin';
}

export interface UserGroup {
  id: string;
  name: string;
  members: string[]; // UID列表
  isAdmin: boolean;
}

export interface FriendStoreState {
  friends: Friend[];
  userGroups: UserGroup[];
  addFriend: (friend: Friend) => void;
  removeFriend: (uid: string) => void;
  updateFriend: (uid: string, data: Partial<Friend>) => void;
  addUserGroup: (group: Omit<UserGroup, 'id'>) => void;
  removeUserGroup: (id: string) => void;
  updateUserGroup: (id: string, data: Partial<UserGroup>) => void;
}

// 会话相关类型
export interface Session {
  id: string;
  type: 'private' | 'group';
  targetId: string;
  lastMessageTime: number;
  messageCount: number;
  isActive: boolean;
}

export interface SessionStoreState {
  sessions: Session[];
  blacklist: string[];
  whitelist: string[];
  clearSession: (sessionId: string) => void;
  addToBlacklist: (targetId: string) => void;
  removeFromBlacklist: (targetId: string) => void;
  addToWhitelist: (targetId: string) => void;
  removeFromWhitelist: (targetId: string) => void;
}
