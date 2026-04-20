import React from 'react'

const DAY_DETAILS = {
  1: { tasks: ['架設在線系統：Claude Code、MCP、LiteLLM', '架設離線系統：vLLM、本地模型、加密磁碟', '建立 RAG 知識庫、匯入初始資料', '部署 Orchestrator Agent、測試通訊'] },
  2: { tasks: ['BD Agent 分析三家客戶背景', '法務 Agent 完成合規框架', '向 addwii 提出初步合作方案', '後端建構核心技術平台', '向 microjet 提出初步合作方案'] },
  3: { tasks: ['向維明提出初步合作方案', '針對 addwii 需求開發 MVP Demo', '根據客戶反饋調整方案'] },
  4: { tasks: ['完成 addwii Demo', '開始 microjet Demo', '安排 addwii 認證展示', 'addwii 認證展示與答辯'] },
  5: { tasks: ['處理 addwii 認證反饋', '完成 microjet Demo', 'microjet 認證展示'] },
  6: { tasks: ['完成維明 Demo 並展示', '處理所有客戶最終修正需求'] },
  7: { tasks: ['未完成認證客戶最終衝刺', '完成文件歸檔與成果整理', 'Token 用量統計與成本報告'] },
}

const STATUS_STYLES = {
  completed: { bg: 'bg-green-900/30', border: 'border-green-500', dot: 'bg-green-500', text: 'text-green-400', label: '已完成' },
  in_progress: { bg: 'bg-blue-900/30', border: 'border-blue-500', dot: 'bg-blue-500', text: 'text-blue-400', label: '進行中' },
  pending: { bg: 'bg-slate-800', border: 'border-slate-600', dot: 'bg-slate-500', text: 'text-slate-400', label: '待執行' },
}

export default function TimelinePage({ data }) {
  if (!data) return <div className="text-slate-400 text-center mt-20">載入中...</div>
  const { timeline } = data

  const completedDays = timeline.filter(t => t.status === 'completed').length
  const progress = Math.round((completedDays / 7) * 100)

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-white">七日作戰計劃</h1>
          <p className="text-slate-400 mt-1">2026/04/13 — 2026/04/19</p>
        </div>
        <div className="text-right">
          <div className="text-3xl font-bold text-blue-400">{progress}%</div>
          <div className="text-xs text-slate-500">總體進度</div>
        </div>
      </div>

      {/* Progress bar */}
      <div className="w-full bg-slate-700 rounded-full h-4">
        <div className="bg-gradient-to-r from-green-500 to-blue-500 h-4 rounded-full transition-all"
          style={{ width: `${progress}%` }} />
      </div>

      {/* Timeline */}
      <div className="relative">
        {/* Vertical line */}
        <div className="absolute left-6 top-0 bottom-0 w-0.5 bg-slate-700" />

        <div className="space-y-4">
          {timeline.map(t => {
            const style = STATUS_STYLES[t.status]
            const details = DAY_DETAILS[t.day]
            return (
              <div key={t.day} className={`relative ml-14 ${style.bg} border ${style.border} rounded-xl p-5`}>
                {/* Dot on timeline */}
                <div className={`absolute -left-[2.55rem] top-6 w-4 h-4 rounded-full ${style.dot} border-4 border-slate-900 ${t.status === 'in_progress' ? 'animate-pulse' : ''}`} />

                <div className="flex justify-between items-start mb-3">
                  <div>
                    <span className="text-xs text-slate-500">Day {t.day} — {t.date}</span>
                    <h3 className="text-lg font-bold text-white">{t.title}</h3>
                  </div>
                  <span className={`text-xs px-3 py-1 rounded-full ${style.bg} ${style.text} border ${style.border}`}>
                    {style.label}
                  </span>
                </div>

                {/* Tasks */}
                <div className="space-y-1.5">
                  {details?.tasks.map((task, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm">
                      <span className={`w-1.5 h-1.5 rounded-full ${t.status === 'completed' ? 'bg-green-400' : 'bg-slate-500'}`} />
                      <span className={t.status === 'completed' ? 'text-slate-300 line-through opacity-60' : 'text-slate-300'}>
                        {task}
                      </span>
                    </div>
                  ))}
                </div>

                {/* Deliverables */}
                <div className="mt-3 pt-3 border-t border-slate-700/50">
                  <span className="text-xs text-slate-500">交付物：</span>
                  <div className="flex flex-wrap gap-2 mt-1">
                    {t.deliverables.map((d, i) => (
                      <span key={i} className="text-xs bg-slate-700 text-slate-300 px-2 py-1 rounded">
                        {d}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
