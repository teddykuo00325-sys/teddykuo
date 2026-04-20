import React from 'react'

const DEPT_COLORS = {
  '指揮中心': { bg: 'bg-purple-900/50', border: 'border-purple-500', badge: 'bg-purple-700' },
  '業務開發': { bg: 'bg-blue-900/50', border: 'border-blue-500', badge: 'bg-blue-700' },
  '技術研發': { bg: 'bg-green-900/50', border: 'border-green-500', badge: 'bg-green-700' },
  '營運管理': { bg: 'bg-amber-900/50', border: 'border-amber-500', badge: 'bg-amber-700' },
}

function AgentCard({ agent }) {
  const dept = DEPT_COLORS[agent.department] || DEPT_COLORS['營運管理']
  return (
    <div className={`${dept.bg} border ${dept.border} rounded-xl p-5 hover:scale-[1.02] transition-transform`}>
      <div className="flex justify-between items-start mb-3">
        <div>
          <h3 className="text-lg font-bold text-white">{agent.name}</h3>
          <span className={`text-xs px-2 py-0.5 rounded-full ${dept.badge} text-white`}>
            {agent.department}
          </span>
        </div>
        <span className="flex items-center gap-1 text-xs text-green-400">
          <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
          {agent.status === 'active' ? '運行中' : '閒置'}
        </span>
      </div>
      <div className="space-y-2 mt-4">
        <div className="flex justify-between text-sm">
          <span className="text-slate-400">使用模型</span>
          <span className="text-slate-200 font-mono text-xs">{agent.model}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-slate-400">已完成任務</span>
          <span className="text-white font-bold">{agent.tasksCompleted}</span>
        </div>
        <div className="w-full bg-slate-700 rounded-full h-1.5 mt-2">
          <div className="bg-blue-500 h-1.5 rounded-full" style={{ width: `${Math.min(agent.tasksCompleted * 2, 100)}%` }} />
        </div>
      </div>
    </div>
  )
}

export default function AgentsPage({ data }) {
  if (!data) return <div className="text-slate-400 text-center mt-20">載入中...</div>
  const { agents } = data

  const departments = [...new Set(agents.map(a => a.department))]

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">AI Agent 管理中心</h1>
        <p className="text-slate-400 mt-1">Palantir 模組化 Agent 架構 — 每個 Agent 負責單一職能</p>
      </div>

      {/* Organization chart summary */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 p-5">
        <h2 className="text-lg font-bold text-white mb-3">組織架構</h2>
        <div className="grid grid-cols-4 gap-3 text-center">
          <div className="bg-slate-900 rounded-lg p-3 col-span-4 border border-purple-500/30">
            <div className="text-xs text-slate-400">人類領導人（監管/決策/風控）</div>
            <div className="text-white font-bold mt-1">↓</div>
            <div className="text-sm text-purple-400 font-bold">Orchestrator Agent</div>
          </div>
          {departments.filter(d => d !== '指揮中心').map(dept => (
            <div key={dept} className={`rounded-lg p-3 border ${DEPT_COLORS[dept]?.border || 'border-slate-600'} ${DEPT_COLORS[dept]?.bg || ''}`}>
              <div className="text-sm font-bold text-white">{dept}</div>
              <div className="text-xs text-slate-400 mt-1">
                {agents.filter(a => a.department === dept).length} Agent
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Agent Cards by Department */}
      {departments.map(dept => (
        <div key={dept}>
          <h2 className="text-lg font-bold text-white mb-3 flex items-center gap-2">
            <span className={`w-3 h-3 rounded-full ${DEPT_COLORS[dept]?.badge || 'bg-slate-500'}`} />
            {dept}
          </h2>
          <div className="grid grid-cols-3 gap-4">
            {agents.filter(a => a.department === dept).map(a => (
              <AgentCard key={a.id} agent={a} />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
