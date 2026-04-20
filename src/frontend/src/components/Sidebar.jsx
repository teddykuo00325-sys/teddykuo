import React from 'react'

const NAV_ITEMS = [
  { id: 'dashboard', label: '總覽儀表板', icon: '📊' },
  { id: 'agents', label: 'AI Agent 管理', icon: '🤖' },
  { id: 'clients', label: '客戶認證進度', icon: '🏢' },
  { id: 'timeline', label: '七日作戰計劃', icon: '📅' },
  { id: 'tokens', label: 'Token 成本監控', icon: '💰' },
]

export default function Sidebar({ currentPage, onNavigate }) {
  return (
    <aside className="w-64 bg-slate-800 border-r border-slate-700 flex flex-col">
      {/* Logo */}
      <div className="p-6 border-b border-slate-700">
        <h1 className="text-xl font-bold text-white">
          <span className="text-blue-400">凌策</span>公司
        </h1>
        <p className="text-xs text-slate-400 mt-1">AI Agent 協作平台 v1.0</p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-1">
        {NAV_ITEMS.map(item => (
          <button
            key={item.id}
            onClick={() => onNavigate(item.id)}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm transition-all ${
              currentPage === item.id
                ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/20'
                : 'text-slate-300 hover:bg-slate-700 hover:text-white'
            }`}
          >
            <span className="text-lg">{item.icon}</span>
            <span>{item.label}</span>
          </button>
        ))}
      </nav>

      {/* Status */}
      <div className="p-4 border-t border-slate-700">
        <div className="flex items-center gap-2 mb-2">
          <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
          <span className="text-xs text-slate-400">系統運行中</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-blue-400" />
          <span className="text-xs text-slate-400">Day 4 / 7 — 開發衝刺 II</span>
        </div>
        <div className="mt-3 text-xs text-slate-500">
          Palantir AI Agent 協同模式
        </div>
      </div>
    </aside>
  )
}
