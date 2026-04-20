import React from 'react'

function StatCard({ label, value, sub, color = 'blue' }) {
  const colors = {
    blue: 'from-blue-600 to-blue-800 shadow-blue-600/20',
    green: 'from-green-600 to-green-800 shadow-green-600/20',
    amber: 'from-amber-600 to-amber-800 shadow-amber-600/20',
    purple: 'from-purple-600 to-purple-800 shadow-purple-600/20',
  }
  return (
    <div className={`bg-gradient-to-br ${colors[color]} rounded-xl p-5 shadow-lg`}>
      <p className="text-sm text-white/70">{label}</p>
      <p className="text-3xl font-bold text-white mt-1">{value}</p>
      {sub && <p className="text-xs text-white/60 mt-2">{sub}</p>}
    </div>
  )
}

function AgentRow({ agent }) {
  const statusColors = { active: 'bg-green-400', idle: 'bg-yellow-400', error: 'bg-red-400' }
  return (
    <tr className="border-b border-slate-700/50 hover:bg-slate-800/50 transition">
      <td className="py-3 px-4">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${statusColors[agent.status] || 'bg-gray-400'}`} />
          <span className="font-medium text-white">{agent.name}</span>
        </div>
      </td>
      <td className="py-3 px-4 text-slate-400 text-sm">{agent.department}</td>
      <td className="py-3 px-4 text-slate-400 text-sm">{agent.model}</td>
      <td className="py-3 px-4 text-right">
        <span className="text-blue-400 font-mono">{agent.tasksCompleted}</span>
      </td>
    </tr>
  )
}

function ClientCard({ client }) {
  const barColor = client.certificationProgress >= 60 ? 'bg-green-500' : client.certificationProgress >= 40 ? 'bg-amber-500' : 'bg-blue-500'
  return (
    <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
      <div className="flex justify-between items-center mb-3">
        <h3 className="text-lg font-bold text-white">{client.name}</h3>
        <span className={`text-xs px-2 py-1 rounded-full ${
          client.proposalSent ? 'bg-green-900 text-green-300' : 'bg-slate-700 text-slate-400'
        }`}>
          {client.proposalSent ? '提案已送出' : '準備中'}
        </span>
      </div>
      <div className="mb-2 flex justify-between text-sm">
        <span className="text-slate-400">認證進度</span>
        <span className="text-white font-mono">{client.certificationProgress}%</span>
      </div>
      <div className="w-full bg-slate-700 rounded-full h-2">
        <div className={`${barColor} h-2 rounded-full transition-all duration-500`}
          style={{ width: `${client.certificationProgress}%` }} />
      </div>
    </div>
  )
}

export default function Dashboard({ data }) {
  if (!data) return <div className="text-slate-400 text-center mt-20">載入中...</div>

  const { overview, agents, clients, timeline } = data
  const currentTask = timeline?.find(t => t.status === 'in_progress')
  const tokenPercent = Math.round((overview.tokenUsage.total / overview.tokenUsage.budget) * 100)

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-white">凌策公司 — AI 協作指揮中心</h1>
          <p className="text-slate-400 mt-1">
            Day {overview.currentDay}/{overview.totalDays} — {currentTask?.title || '進行中'}
          </p>
        </div>
        <div className="text-right">
          <div className="text-xs text-slate-500">Palantir AIP 模式</div>
          <div className="text-sm text-green-400 flex items-center gap-1 justify-end">
            <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            全系統運行中
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard label="活躍 Agent 數" value={overview.activeAgents} sub={`共 ${overview.totalAgents} 個 Agent`} color="blue" />
        <StatCard label="已完成任務" value={overview.totalTasksCompleted} sub="累計任務數" color="green" />
        <StatCard label="客戶認證進度" value={`${overview.avgCertificationProgress}%`} sub={`${overview.clientsCertified}/${overview.totalClients} 已認證`} color="amber" />
        <StatCard label="Token 使用率" value={`${tokenPercent}%`} sub={`${(overview.tokenUsage.total / 1000000).toFixed(1)}M / ${(overview.tokenUsage.budget / 1000000).toFixed(0)}M`} color="purple" />
      </div>

      {/* Main Content: Agents + Clients */}
      <div className="grid grid-cols-3 gap-6">
        {/* Agent Table */}
        <div className="col-span-2 bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-700">
            <h2 className="text-lg font-bold text-white">AI Agent 狀態總覽</h2>
          </div>
          <table className="w-full">
            <thead>
              <tr className="text-xs text-slate-500 border-b border-slate-700">
                <th className="py-2 px-4 text-left">Agent</th>
                <th className="py-2 px-4 text-left">部門</th>
                <th className="py-2 px-4 text-left">模型</th>
                <th className="py-2 px-4 text-right">已完成</th>
              </tr>
            </thead>
            <tbody>
              {agents?.map(a => <AgentRow key={a.id} agent={a} />)}
            </tbody>
          </table>
        </div>

        {/* Client Cards */}
        <div className="space-y-4">
          <h2 className="text-lg font-bold text-white">客戶認證追蹤</h2>
          {clients?.map(c => <ClientCard key={c.id} client={c} />)}
        </div>
      </div>

      {/* Timeline */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 p-5">
        <h2 className="text-lg font-bold text-white mb-4">七日作戰進度</h2>
        <div className="flex gap-2">
          {timeline?.map(t => {
            const colors = {
              completed: 'bg-green-600 border-green-500',
              in_progress: 'bg-blue-600 border-blue-400 glow',
              pending: 'bg-slate-700 border-slate-600',
            }
            return (
              <div key={t.day} className={`flex-1 rounded-lg border p-3 ${colors[t.status]}`}>
                <div className="text-xs text-white/70">Day {t.day}</div>
                <div className="text-sm font-bold text-white mt-1">{t.title}</div>
                <div className="text-xs text-white/50 mt-1">{t.date}</div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
