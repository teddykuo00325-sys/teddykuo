/**
 * 凌策公司 - 後端 API 伺服器
 * AI Agent 協作平台核心服務
 */
const express = require('express');
const cors = require('cors');
const path = require('path');
const { v4: uuidv4 } = require('uuid');

const app = express();
const PORT = process.env.PORT || 3001;

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, '../frontend/dist')));

// ── In-memory data store ──
const store = {
  agents: [
    { id: 'orch-001', name: 'Orchestrator', department: '指揮中心', status: 'active', tasksCompleted: 47, model: 'Claude Opus 4.6' },
    { id: 'bd-001', name: 'BD Agent', department: '業務開發', status: 'active', tasksCompleted: 23, model: 'Claude Sonnet 4.6' },
    { id: 'cs-001', name: '客服 Agent', department: '業務開發', status: 'active', tasksCompleted: 18, model: 'Claude Sonnet 4.6' },
    { id: 'prop-001', name: '提案 Agent', department: '業務開發', status: 'active', tasksCompleted: 12, model: 'Claude Sonnet 4.6' },
    { id: 'fe-001', name: '前端 Agent', department: '技術研發', status: 'active', tasksCompleted: 35, model: 'Claude Code (Sonnet)' },
    { id: 'be-001', name: '後端 Agent', department: '技術研發', status: 'active', tasksCompleted: 41, model: 'Claude Code (Sonnet)' },
    { id: 'qa-001', name: 'QA Agent', department: '技術研發', status: 'active', tasksCompleted: 29, model: 'Claude Code + 本地模型' },
    { id: 'fin-001', name: '財務 Agent', department: '營運管理', status: 'active', tasksCompleted: 15, model: '本地模型（離線）' },
    { id: 'legal-001', name: '法務 Agent', department: '營運管理', status: 'active', tasksCompleted: 11, model: '本地模型（離線）' },
    { id: 'doc-001', name: '文件 Agent', department: '營運管理', status: 'active', tasksCompleted: 20, model: 'Claude Haiku' },
  ],
  tasks: [],
  clients: [
    { id: 'client-addwii', name: 'addwii', status: 'in_progress', certificationProgress: 65, contact: 'pending', proposalSent: true },
    { id: 'client-microjet', name: 'microjet', status: 'in_progress', certificationProgress: 40, contact: 'pending', proposalSent: true },
    { id: 'client-weiming', name: '維明', status: 'in_progress', certificationProgress: 30, contact: 'pending', proposalSent: false },
  ],
  tokenUsage: {
    total: 0,
    daily: [],
    byModel: { 'opus': 0, 'sonnet': 0, 'haiku': 0, 'local': 0 },
    budget: 10000000,
  },
  timeline: [
    { day: 1, date: '2026-04-13', title: '基礎建設', status: 'completed', deliverables: ['在線/離線 AI 系統', 'Agent 協作框架', 'RAG 知識庫初版'] },
    { day: 2, date: '2026-04-14', title: '組織啟動 + 客戶接洽', status: 'completed', deliverables: ['客戶需求分析報告', '初步提案書', '技術平台 v0.1'] },
    { day: 3, date: '2026-04-15', title: '開發衝刺 I', status: 'completed', deliverables: ['維明提案', 'addwii MVP Demo', '方案調整'] },
    { day: 4, date: '2026-04-16', title: '開發衝刺 II', status: 'in_progress', deliverables: ['addwii Demo 完成', 'microjet Demo 開始', 'addwii 認證展示'] },
    { day: 5, date: '2026-04-17', title: '認證衝刺 I', status: 'pending', deliverables: ['microjet Demo 完成', 'microjet 認證展示'] },
    { day: 6, date: '2026-04-18', title: '認證衝刺 II', status: 'pending', deliverables: ['維明 Demo + 展示', '最終修正'] },
    { day: 7, date: '2026-04-19', title: '收尾與保險日', status: 'pending', deliverables: ['最終衝刺', '文件歸檔', '成本報告'] },
  ]
};

// Simulate token usage
function simulateTokenUsage() {
  const models = ['sonnet', 'haiku', 'local'];
  const model = models[Math.floor(Math.random() * models.length)];
  const tokens = Math.floor(Math.random() * 500) + 100;
  store.tokenUsage.total += tokens;
  store.tokenUsage.byModel[model] += tokens;
}
setInterval(simulateTokenUsage, 10000);

// ── API Routes ──

// Dashboard summary
app.get('/api/dashboard', (req, res) => {
  const activeAgents = store.agents.filter(a => a.status === 'active').length;
  const totalTasks = store.agents.reduce((sum, a) => sum + a.tasksCompleted, 0);
  const certifiedClients = store.clients.filter(c => c.status === 'certified').length;
  const avgProgress = Math.round(store.clients.reduce((sum, c) => sum + c.certificationProgress, 0) / store.clients.length);

  res.json({
    overview: {
      activeAgents,
      totalAgents: store.agents.length,
      totalTasksCompleted: totalTasks,
      clientsCertified: certifiedClients,
      totalClients: store.clients.length,
      avgCertificationProgress: avgProgress,
      currentDay: 4,
      totalDays: 7,
      tokenUsage: store.tokenUsage,
    },
    agents: store.agents,
    clients: store.clients,
    timeline: store.timeline,
  });
});

// Agents
app.get('/api/agents', (req, res) => res.json(store.agents));
app.get('/api/agents/:id', (req, res) => {
  const agent = store.agents.find(a => a.id === req.params.id);
  agent ? res.json(agent) : res.status(404).json({ error: 'Agent not found' });
});

// Clients
app.get('/api/clients', (req, res) => res.json(store.clients));
app.get('/api/clients/:id', (req, res) => {
  const client = store.clients.find(c => c.id === req.params.id);
  client ? res.json(client) : res.status(404).json({ error: 'Client not found' });
});
app.patch('/api/clients/:id', (req, res) => {
  const client = store.clients.find(c => c.id === req.params.id);
  if (!client) return res.status(404).json({ error: 'Client not found' });
  Object.assign(client, req.body);
  res.json(client);
});

// Tasks
app.post('/api/tasks', (req, res) => {
  const task = {
    id: uuidv4(),
    ...req.body,
    createdAt: new Date().toISOString(),
    status: 'pending',
  };
  store.tasks.push(task);
  res.status(201).json(task);
});
app.get('/api/tasks', (req, res) => res.json(store.tasks));

// Token usage
app.get('/api/tokens', (req, res) => res.json(store.tokenUsage));

// Timeline
app.get('/api/timeline', (req, res) => res.json(store.timeline));

// Agent orchestration - dispatch task
app.post('/api/orchestrate', (req, res) => {
  const { agentId, action, payload } = req.body;
  const agent = store.agents.find(a => a.id === agentId);
  if (!agent) return res.status(404).json({ error: 'Agent not found' });

  agent.tasksCompleted += 1;
  const result = {
    taskId: uuidv4(),
    agentId,
    action,
    status: 'completed',
    timestamp: new Date().toISOString(),
    result: `Task "${action}" dispatched to ${agent.name} successfully`,
  };
  res.json(result);
});

// Health check
app.get('/api/health', (req, res) => {
  res.json({
    status: 'healthy',
    company: '凌策公司',
    version: '1.0.0',
    uptime: process.uptime(),
    timestamp: new Date().toISOString(),
  });
});

// SPA fallback
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, '../frontend/dist/index.html'));
});

app.listen(PORT, () => {
  console.log(`🚀 凌策公司 API Server running on port ${PORT}`);
  console.log(`📊 Dashboard: http://localhost:${PORT}`);
});
