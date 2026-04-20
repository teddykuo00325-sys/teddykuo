import React, { useState, useEffect } from 'react'
import Sidebar from './components/Sidebar'
import Dashboard from './pages/Dashboard'
import AgentsPage from './pages/AgentsPage'
import ClientsPage from './pages/ClientsPage'
import TimelinePage from './pages/TimelinePage'
import TokenPage from './pages/TokenPage'

const PAGES = {
  dashboard: Dashboard,
  agents: AgentsPage,
  clients: ClientsPage,
  timeline: TimelinePage,
  tokens: TokenPage,
}

export default function App() {
  const [page, setPage] = useState('dashboard')
  const [data, setData] = useState(null)

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 5000)
    return () => clearInterval(interval)
  }, [])

  async function fetchData() {
    try {
      const res = await fetch('/api/dashboard')
      const json = await res.json()
      setData(json)
    } catch {
      // Use mock data when API is not available
      setData(getMockData())
    }
  }

  const PageComponent = PAGES[page] || Dashboard

  return (
    <div className="flex h-screen bg-slate-900">
      <Sidebar currentPage={page} onNavigate={setPage} />
      <main className="flex-1 overflow-auto p-6">
        <PageComponent data={data} />
      </main>
    </div>
  )
}

function getMockData() {
  return {
    overview: {
      activeAgents: 10, totalAgents: 10, totalTasksCompleted: 251,
      clientsCertified: 0, totalClients: 3, avgCertificationProgress: 45,
      currentDay: 4, totalDays: 7,
      tokenUsage: { total: 2847500, budget: 10000000, byModel: { opus: 312000, sonnet: 1580000, haiku: 643500, local: 312000 } }
    },
    agents: [
      { id: 'orch-001', name: 'Orchestrator', department: '指揮中心', status: 'active', tasksCompleted: 47, model: 'Claude Opus 4.6' },
      { id: 'bd-001', name: 'BD Agent', department: '業務開發', status: 'active', tasksCompleted: 23, model: 'Claude Sonnet 4.6' },
      { id: 'cs-001', name: '客服 Agent', department: '業務開發', status: 'active', tasksCompleted: 18, model: 'Claude Sonnet 4.6' },
      { id: 'prop-001', name: '提案 Agent', department: '業務開發', status: 'active', tasksCompleted: 12, model: 'Claude Sonnet 4.6' },
      { id: 'fe-001', name: '前端 Agent', department: '技術研發', status: 'active', tasksCompleted: 35, model: 'Claude Code' },
      { id: 'be-001', name: '後端 Agent', department: '技術研發', status: 'active', tasksCompleted: 41, model: 'Claude Code' },
      { id: 'qa-001', name: 'QA Agent', department: '技術研發', status: 'active', tasksCompleted: 29, model: 'Claude Code' },
      { id: 'fin-001', name: '財務 Agent', department: '營運管理', status: 'active', tasksCompleted: 15, model: '本地模型' },
      { id: 'legal-001', name: '法務 Agent', department: '營運管理', status: 'active', tasksCompleted: 11, model: '本地模型' },
      { id: 'doc-001', name: '文件 Agent', department: '營運管理', status: 'active', tasksCompleted: 20, model: 'Claude Haiku' },
    ],
    clients: [
      { id: 'client-addwii', name: 'addwii', status: 'in_progress', certificationProgress: 65, proposalSent: true },
      { id: 'client-microjet', name: 'microjet', status: 'in_progress', certificationProgress: 40, proposalSent: true },
      { id: 'client-weiming', name: '維明', status: 'in_progress', certificationProgress: 30, proposalSent: false },
    ],
    timeline: [
      { day: 1, date: '2026-04-13', title: '基礎建設', status: 'completed', deliverables: ['在線/離線 AI 系統', 'Agent 協作框架', 'RAG 知識庫初版'] },
      { day: 2, date: '2026-04-14', title: '組織啟動 + 客戶接洽', status: 'completed', deliverables: ['客戶需求分析報告', '初步提案書', '技術平台 v0.1'] },
      { day: 3, date: '2026-04-15', title: '開發衝刺 I', status: 'completed', deliverables: ['維明提案', 'addwii MVP Demo', '方案調整'] },
      { day: 4, date: '2026-04-16', title: '開發衝刺 II', status: 'in_progress', deliverables: ['addwii Demo 完成', 'microjet Demo 開始', 'addwii 認證展示'] },
      { day: 5, date: '2026-04-17', title: '認證衝刺 I', status: 'pending', deliverables: ['microjet Demo', 'microjet 認證展示'] },
      { day: 6, date: '2026-04-18', title: '認證衝刺 II', status: 'pending', deliverables: ['維明 Demo + 展示', '最終修正'] },
      { day: 7, date: '2026-04-19', title: '收尾與保險日', status: 'pending', deliverables: ['最終衝刺', '文件歸檔', '成本報告'] },
    ],
  }
}
