#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
凌策公司 — Orchestrator Agent（協調指揮 Agent）
Palantir AIP 模式核心：接收人類指令，分派任務給各部門 Agent，彙整進度。
"""

import json
import time
from datetime import datetime
from typing import Dict, List, Optional


class Agent:
    """代表一個 AI Agent 的基本類別"""
    def __init__(self, agent_id: str, name: str, department: str, model: str):
        self.id = agent_id
        self.name = name
        self.department = department
        self.model = model
        self.status = "active"
        self.tasks_completed = 0
        self.current_task = None
        self.task_history: List[Dict] = []

    def assign_task(self, task: Dict) -> Dict:
        """分派任務給此 Agent"""
        self.current_task = task
        self.status = "busy"
        return {
            "agent_id": self.id,
            "agent_name": self.name,
            "task": task,
            "assigned_at": datetime.now().isoformat(),
            "status": "assigned"
        }

    def complete_task(self, result: str) -> Dict:
        """完成目前任務"""
        completed = {
            "task": self.current_task,
            "result": result,
            "completed_at": datetime.now().isoformat()
        }
        self.task_history.append(completed)
        self.tasks_completed += 1
        self.current_task = None
        self.status = "active"
        return completed

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "department": self.department,
            "model": self.model,
            "status": self.status,
            "tasks_completed": self.tasks_completed,
            "current_task": self.current_task,
        }


class Orchestrator:
    """
    協調指揮 Agent — 凌策公司的中央控制系統

    職責：
    1. 接收人類領導人指令
    2. 分析任務並分派給最適合的 Agent
    3. 追蹤所有 Agent 的進度
    4. 彙整並回報狀態
    """

    def __init__(self):
        self.agents: Dict[str, Agent] = {}
        self.task_queue: List[Dict] = []
        self.completed_tasks: List[Dict] = []
        self.started_at = datetime.now()
        self._init_agents()

    def _init_agents(self):
        """初始化所有 AI Agent"""
        agent_configs = [
            ("bd-001", "BD Agent", "業務開發", "Claude Sonnet 4.6"),
            ("cs-001", "客服 Agent", "業務開發", "Claude Sonnet 4.6"),
            ("prop-001", "提案 Agent", "業務開發", "Claude Sonnet 4.6"),
            ("fe-001", "前端 Agent", "技術研發", "Claude Code (Sonnet)"),
            ("be-001", "後端 Agent", "技術研發", "Claude Code (Sonnet)"),
            ("qa-001", "QA Agent", "技術研發", "Claude Code + 本地模型"),
            ("fin-001", "財務 Agent", "營運管理", "本地模型（離線）"),
            ("legal-001", "法務 Agent", "營運管理", "本地模型（離線）"),
            ("doc-001", "文件 Agent", "營運管理", "Claude Haiku"),
        ]
        for aid, name, dept, model in agent_configs:
            self.agents[aid] = Agent(aid, name, dept, model)
        print(f"[Orchestrator] 已初始化 {len(self.agents)} 個 Agent")

    def dispatch(self, task_description: str, target_agent_id: Optional[str] = None) -> Dict:
        """
        分派任務

        Args:
            task_description: 任務描述
            target_agent_id: 指定 Agent ID（可選，不指定則自動選擇）
        """
        task = {
            "id": f"task-{len(self.completed_tasks) + len(self.task_queue) + 1:04d}",
            "description": task_description,
            "created_at": datetime.now().isoformat(),
            "status": "pending"
        }

        if target_agent_id:
            agent = self.agents.get(target_agent_id)
            if not agent:
                return {"error": f"Agent {target_agent_id} not found"}
        else:
            agent = self._select_best_agent(task_description)

        if agent:
            result = agent.assign_task(task)
            task["status"] = "assigned"
            task["assigned_to"] = agent.id
            print(f"[Orchestrator] 任務 '{task_description}' 已分派給 {agent.name}")
            return result
        else:
            self.task_queue.append(task)
            print(f"[Orchestrator] 任務 '{task_description}' 已加入等待佇列")
            return {"task": task, "status": "queued"}

    def _select_best_agent(self, description: str) -> Optional[Agent]:
        """根據任務描述自動選擇最適合的 Agent"""
        keyword_map = {
            "bd-001": ["客戶", "業務", "需求", "提案", "接洽"],
            "cs-001": ["客服", "溝通", "問題", "回覆", "對接"],
            "prop-001": ["簡報", "企劃", "方案", "提案書"],
            "fe-001": ["前端", "UI", "介面", "頁面", "Dashboard"],
            "be-001": ["後端", "API", "資料庫", "伺服器", "邏輯"],
            "qa-001": ["測試", "品質", "QA", "審查", "bug"],
            "fin-001": ["財務", "成本", "預算", "Token", "報表"],
            "legal-001": ["法務", "合規", "合約", "法律", "隱私"],
            "doc-001": ["文件", "文檔", "手冊", "說明", "紀錄"],
        }

        best_agent_id = None
        best_score = 0

        for agent_id, keywords in keyword_map.items():
            score = sum(1 for kw in keywords if kw in description)
            if score > best_score:
                best_score = score
                best_agent_id = agent_id

        if best_agent_id and self.agents[best_agent_id].status == "active":
            return self.agents[best_agent_id]

        # Fallback: 選擇最閒的 Agent
        available = [a for a in self.agents.values() if a.status == "active"]
        if available:
            return min(available, key=lambda a: a.tasks_completed)
        return None

    def get_status(self) -> Dict:
        """取得系統全局狀態"""
        agents_status = {a.id: a.to_dict() for a in self.agents.values()}
        active_count = sum(1 for a in self.agents.values() if a.status == "active")
        busy_count = sum(1 for a in self.agents.values() if a.status == "busy")
        total_tasks = sum(a.tasks_completed for a in self.agents.values())

        return {
            "orchestrator": {
                "uptime_seconds": (datetime.now() - self.started_at).total_seconds(),
                "total_agents": len(self.agents),
                "active_agents": active_count,
                "busy_agents": busy_count,
                "total_tasks_completed": total_tasks,
                "queued_tasks": len(self.task_queue),
            },
            "agents": agents_status,
            "timestamp": datetime.now().isoformat(),
        }

    def get_department_report(self) -> Dict:
        """取得各部門報告"""
        departments = {}
        for agent in self.agents.values():
            if agent.department not in departments:
                departments[agent.department] = {
                    "agents": [],
                    "total_tasks": 0,
                    "active": 0,
                    "busy": 0,
                }
            dept = departments[agent.department]
            dept["agents"].append(agent.name)
            dept["total_tasks"] += agent.tasks_completed
            if agent.status == "active":
                dept["active"] += 1
            elif agent.status == "busy":
                dept["busy"] += 1
        return departments


# ── Main Entry ──
if __name__ == "__main__":
    print("=" * 60)
    print("  凌策公司 — Orchestrator Agent 啟動")
    print("  Palantir AIP 協同模式")
    print("=" * 60)

    orch = Orchestrator()

    # 示範任務分派
    print("\n--- 任務分派示範 ---")
    orch.dispatch("分析 addwii 客戶需求並準備提案書")
    orch.dispatch("開發前端 Dashboard UI 介面")
    orch.dispatch("建立後端 API 服務與資料庫")
    orch.dispatch("執行程式碼品質測試與審查")
    orch.dispatch("追蹤 Token 使用成本與預算")
    orch.dispatch("審查合約合規性")

    # 輸出狀態
    print("\n--- 系統狀態 ---")
    status = orch.get_status()
    print(json.dumps(status["orchestrator"], indent=2, ensure_ascii=False))

    print("\n--- 部門報告 ---")
    report = orch.get_department_report()
    for dept, info in report.items():
        print(f"  {dept}: {', '.join(info['agents'])} | 已完成任務: {info['total_tasks']}")

    print("\n[Orchestrator] 系統就緒，等待人類指令...")
