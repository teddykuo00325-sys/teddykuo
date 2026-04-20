# 凌策公司 — AI Agent 協作平台 API 文檔

> 版本：v1.0 | 更新日期：2026-04-16

---

## 概述

凌策公司 AI Agent 協作平台提供 RESTful API，支援 Agent 管理、任務分派、客戶追蹤、Token 監控等功能。

**Base URL:** `http://localhost:3001/api`

---

## 認證方式

所有 API 請求需在 Header 帶入 API Key：

```
Authorization: Bearer <API_KEY>
```

API Key 採分層管理，每個 Agent 擁有獨立的 Key。

---

## API 端點

### 1. 系統健康檢查

```
GET /api/health
```

**回應範例：**
```json
{
  "status": "healthy",
  "company": "凌策公司",
  "version": "1.0.0",
  "uptime": 86400,
  "timestamp": "2026-04-16T10:00:00.000Z"
}
```

---

### 2. Dashboard 總覽

```
GET /api/dashboard
```

回傳完整的系統狀態，包含 Agent 列表、客戶進度、時程、Token 用量。

**回應結構：**
| 欄位 | 類型 | 說明 |
|------|------|------|
| overview | Object | 系統概覽數據 |
| overview.activeAgents | Number | 活躍 Agent 數量 |
| overview.totalTasksCompleted | Number | 已完成任務總數 |
| overview.avgCertificationProgress | Number | 平均認證進度 (%) |
| overview.tokenUsage | Object | Token 使用統計 |
| agents | Array | Agent 列表 |
| clients | Array | 客戶列表 |
| timeline | Array | 七日作戰時程 |

---

### 3. Agent 管理

#### 取得所有 Agent
```
GET /api/agents
```

#### 取得單一 Agent
```
GET /api/agents/:id
```

**Agent 物件結構：**
| 欄位 | 類型 | 說明 |
|------|------|------|
| id | String | Agent 唯一識別碼 |
| name | String | Agent 名稱 |
| department | String | 所屬部門 |
| status | String | 狀態 (active/idle/error) |
| tasksCompleted | Number | 已完成任務數 |
| model | String | 使用的 AI 模型 |

---

### 4. 客戶管理

#### 取得所有客戶
```
GET /api/clients
```

#### 取得單一客戶
```
GET /api/clients/:id
```

#### 更新客戶資訊
```
PATCH /api/clients/:id
```

**Request Body（部分更新）：**
```json
{
  "certificationProgress": 75,
  "status": "in_progress"
}
```

**Client 物件結構：**
| 欄位 | 類型 | 說明 |
|------|------|------|
| id | String | 客戶唯一識別碼 |
| name | String | 客戶名稱 |
| status | String | 狀態 (in_progress/certified) |
| certificationProgress | Number | 認證進度 (0-100) |
| proposalSent | Boolean | 提案是否已送出 |

---

### 5. 任務管理

#### 建立任務
```
POST /api/tasks
```

**Request Body：**
```json
{
  "title": "開發 addwii Demo",
  "assignedTo": "fe-001",
  "priority": "high",
  "description": "完成 addwii 客戶的 MVP Demo 開發"
}
```

#### 取得所有任務
```
GET /api/tasks
```

---

### 6. Agent 協調指揮

```
POST /api/orchestrate
```

分派任務給指定 Agent。

**Request Body：**
```json
{
  "agentId": "be-001",
  "action": "develop_api",
  "payload": {
    "target": "client-addwii",
    "feature": "智慧客服模組"
  }
}
```

**回應：**
```json
{
  "taskId": "uuid-here",
  "agentId": "be-001",
  "action": "develop_api",
  "status": "completed",
  "timestamp": "2026-04-16T10:00:00.000Z",
  "result": "Task \"develop_api\" dispatched to 後端 Agent successfully"
}
```

---

### 7. Token 使用監控

```
GET /api/tokens
```

**回應：**
```json
{
  "total": 2847500,
  "budget": 10000000,
  "byModel": {
    "opus": 312000,
    "sonnet": 1580000,
    "haiku": 643500,
    "local": 312000
  }
}
```

---

### 8. 時程查詢

```
GET /api/timeline
```

回傳七日作戰計劃的完整時程與狀態。

---

## 錯誤處理

所有錯誤回應格式：
```json
{
  "error": "Agent not found"
}
```

| HTTP 狀態碼 | 說明 |
|-------------|------|
| 200 | 成功 |
| 201 | 建立成功 |
| 400 | 請求格式錯誤 |
| 404 | 資源不存在 |
| 500 | 伺服器錯誤 |

---

## 安全性

- 所有通訊走 HTTPS/TLS 加密
- API Key 分層管理（每個 Agent 獨立 Key）
- 敏感操作需人類審核確認 (Human-in-the-Loop)
- 機密資料僅在離線系統處理，不經過在線 API

---

## 聯絡

- 技術支援：凌策公司技術研發部門
- 文件維護：文件 Agent (doc-001)
