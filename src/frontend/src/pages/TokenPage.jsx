import React from 'react'

const MODEL_INFO = {
  opus: { name: 'Claude Opus', color: 'bg-purple-500', textColor: 'text-purple-400', price: '$15/1M' },
  sonnet: { name: 'Claude Sonnet', color: 'bg-blue-500', textColor: 'text-blue-400', price: '$3/1M' },
  haiku: { name: 'Claude Haiku', color: 'bg-green-500', textColor: 'text-green-400', price: '$0.25/1M' },
  local: { name: '本地模型', color: 'bg-amber-500', textColor: 'text-amber-400', price: '$0 (本地)' },
}

const STRATEGIES = [
  { name: 'Prompt Caching', saving: '30-50%', desc: '對重複的系統提示與上下文做快取', status: 'active' },
  { name: '模型分流', saving: '20-30%', desc: '簡單任務用 Haiku、複雜決策用 Sonnet', status: 'active' },
  { name: '本地模型分擔', saving: '15-25%', desc: '法務、財務交給離線模型', status: 'active' },
  { name: 'RAG 精準檢索', saving: '10-15%', desc: '精準上下文減少冗長 Prompt', status: 'active' },
  { name: '任務去重', saving: '5-10%', desc: 'Orchestrator 確保不重複分派', status: 'active' },
]

export default function TokenPage({ data }) {
  if (!data) return <div className="text-slate-400 text-center mt-20">載入中...</div>

  const { tokenUsage } = data.overview
  const totalUsed = tokenUsage.total
  const budget = tokenUsage.budget
  const usagePercent = Math.round((totalUsed / budget) * 100)
  const remaining = budget - totalUsed
  const byModel = tokenUsage.byModel

  // Calculate total for percentages
  const modelTotal = Object.values(byModel).reduce((a, b) => a + b, 0) || 1

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Token 成本監控中心</h1>
        <p className="text-slate-400 mt-1">即時追蹤 Token 使用量 — 評選標準第二指標</p>
      </div>

      {/* Main Stats */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-gradient-to-br from-blue-700 to-blue-900 rounded-xl p-5">
          <div className="text-sm text-blue-200">已使用</div>
          <div className="text-2xl font-bold text-white mt-1">{(totalUsed / 1000000).toFixed(2)}M</div>
        </div>
        <div className="bg-gradient-to-br from-green-700 to-green-900 rounded-xl p-5">
          <div className="text-sm text-green-200">剩餘預算</div>
          <div className="text-2xl font-bold text-white mt-1">{(remaining / 1000000).toFixed(2)}M</div>
        </div>
        <div className="bg-gradient-to-br from-purple-700 to-purple-900 rounded-xl p-5">
          <div className="text-sm text-purple-200">使用率</div>
          <div className="text-2xl font-bold text-white mt-1">{usagePercent}%</div>
        </div>
        <div className="bg-gradient-to-br from-amber-700 to-amber-900 rounded-xl p-5">
          <div className="text-sm text-amber-200">預估總成本</div>
          <div className="text-2xl font-bold text-white mt-1">
            ${((byModel.opus * 15 + byModel.sonnet * 3 + byModel.haiku * 0.25) / 1000000).toFixed(2)}
          </div>
        </div>
      </div>

      {/* Budget bar */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 p-5">
        <div className="flex justify-between mb-2">
          <span className="text-sm text-slate-400">預算使用進度</span>
          <span className="text-sm text-white font-mono">{(totalUsed / 1000000).toFixed(2)}M / {(budget / 1000000).toFixed(0)}M</span>
        </div>
        <div className="w-full bg-slate-700 rounded-full h-6 overflow-hidden">
          <div
            className={`h-6 rounded-full transition-all flex items-center justify-center text-xs font-bold ${
              usagePercent > 80 ? 'bg-red-500' : usagePercent > 50 ? 'bg-amber-500' : 'bg-green-500'
            }`}
            style={{ width: `${Math.max(usagePercent, 5)}%` }}
          >
            {usagePercent}%
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Model breakdown */}
        <div className="bg-slate-800 rounded-xl border border-slate-700 p-5">
          <h2 className="text-lg font-bold text-white mb-4">各模型 Token 分佈</h2>
          <div className="space-y-4">
            {Object.entries(byModel).map(([key, value]) => {
              const info = MODEL_INFO[key]
              const pct = Math.round((value / modelTotal) * 100)
              return (
                <div key={key}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className={info.textColor}>{info.name}</span>
                    <span className="text-slate-400">
                      {(value / 1000).toFixed(0)}K ({pct}%) — {info.price}
                    </span>
                  </div>
                  <div className="w-full bg-slate-700 rounded-full h-2">
                    <div className={`${info.color} h-2 rounded-full`} style={{ width: `${pct}%` }} />
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Cost strategies */}
        <div className="bg-slate-800 rounded-xl border border-slate-700 p-5">
          <h2 className="text-lg font-bold text-white mb-4">成本控制策略</h2>
          <div className="space-y-3">
            {STRATEGIES.map((s, i) => (
              <div key={i} className="bg-slate-900 rounded-lg p-3">
                <div className="flex justify-between items-center">
                  <span className="text-sm text-white font-medium">{s.name}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-green-400 font-mono">{s.saving}</span>
                    <span className="w-2 h-2 rounded-full bg-green-400" />
                  </div>
                </div>
                <p className="text-xs text-slate-400 mt-1">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
