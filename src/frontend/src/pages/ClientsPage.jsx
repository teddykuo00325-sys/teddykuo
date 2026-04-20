import React from 'react'

const CLIENT_DETAILS = {
  addwii: {
    fullName: 'addwii',
    industry: '數位科技 / 互動體驗',
    proposal: 'AI Agent 智慧客服與數據分析平台',
    steps: [
      { name: '需求分析', done: true },
      { name: '提案書送出', done: true },
      { name: 'MVP Demo 開發', done: true },
      { name: '認證展示', done: false },
      { name: '客戶簽核', done: false },
    ],
  },
  microjet: {
    fullName: 'microjet',
    industry: '精密製造 / 噴墨技術',
    proposal: 'AI 驅動智慧製造品質監控系統',
    steps: [
      { name: '需求分析', done: true },
      { name: '提案書送出', done: true },
      { name: 'MVP Demo 開發', done: false },
      { name: '認證展示', done: false },
      { name: '客戶簽核', done: false },
    ],
  },
  '維明': {
    fullName: '維明',
    industry: '企業服務 / 系統整合',
    proposal: 'AI Agent 企業流程自動化解決方案',
    steps: [
      { name: '需求分析', done: true },
      { name: '提案書送出', done: false },
      { name: 'MVP Demo 開發', done: false },
      { name: '認證展示', done: false },
      { name: '客戶簽核', done: false },
    ],
  },
}

function ClientDetailCard({ client }) {
  const details = CLIENT_DETAILS[client.name] || {}
  const completedSteps = details.steps?.filter(s => s.done).length || 0
  const totalSteps = details.steps?.length || 5

  return (
    <div className="bg-slate-800 rounded-xl border border-slate-700 p-6">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h2 className="text-xl font-bold text-white">{client.name}</h2>
          <p className="text-sm text-slate-400">{details.industry}</p>
        </div>
        <div className="text-right">
          <div className="text-3xl font-bold text-blue-400">{client.certificationProgress}%</div>
          <div className="text-xs text-slate-500">認證進度</div>
        </div>
      </div>

      {/* Progress bar */}
      <div className="w-full bg-slate-700 rounded-full h-3 mb-4">
        <div
          className={`h-3 rounded-full transition-all duration-700 ${
            client.certificationProgress >= 60 ? 'bg-green-500' : client.certificationProgress >= 40 ? 'bg-amber-500' : 'bg-blue-500'
          }`}
          style={{ width: `${client.certificationProgress}%` }}
        />
      </div>

      {/* Proposal */}
      <div className="bg-slate-900 rounded-lg p-4 mb-4">
        <div className="text-xs text-slate-500 mb-1">提案方案</div>
        <div className="text-sm text-white font-medium">{details.proposal}</div>
      </div>

      {/* Steps */}
      <div className="space-y-2">
        <div className="text-xs text-slate-500 mb-2">認證流程 ({completedSteps}/{totalSteps})</div>
        {details.steps?.map((step, i) => (
          <div key={i} className="flex items-center gap-3">
            <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
              step.done ? 'bg-green-600 text-white' : 'bg-slate-700 text-slate-400'
            }`}>
              {step.done ? '✓' : i + 1}
            </span>
            <span className={`text-sm ${step.done ? 'text-green-400' : 'text-slate-400'}`}>
              {step.name}
            </span>
            {!step.done && i === completedSteps && (
              <span className="text-xs bg-blue-600 text-white px-2 py-0.5 rounded-full animate-pulse">進行中</span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

export default function ClientsPage({ data }) {
  if (!data) return <div className="text-slate-400 text-center mt-20">載入中...</div>
  const { clients } = data

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">客戶認證進度追蹤</h1>
        <p className="text-slate-400 mt-1">三家客戶認證狀態 — 目標：4/20 前全部通過</p>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-gradient-to-br from-green-700 to-green-900 rounded-xl p-4 text-center">
          <div className="text-3xl font-bold text-white">{clients.filter(c => c.certificationProgress >= 60).length}</div>
          <div className="text-sm text-green-200">進展順利</div>
        </div>
        <div className="bg-gradient-to-br from-amber-700 to-amber-900 rounded-xl p-4 text-center">
          <div className="text-3xl font-bold text-white">{clients.filter(c => c.certificationProgress >= 30 && c.certificationProgress < 60).length}</div>
          <div className="text-sm text-amber-200">開發中</div>
        </div>
        <div className="bg-gradient-to-br from-blue-700 to-blue-900 rounded-xl p-4 text-center">
          <div className="text-3xl font-bold text-white">{clients.filter(c => c.status === 'certified').length}</div>
          <div className="text-sm text-blue-200">已認證</div>
        </div>
      </div>

      {/* Client Cards */}
      <div className="grid grid-cols-3 gap-6">
        {clients.map(c => <ClientDetailCard key={c.id} client={c} />)}
      </div>
    </div>
  )
}
