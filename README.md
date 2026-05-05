# 岐黄问诊（RAG-MedQA）

面向医疗咨询场景的检索增强生成（RAG）智能问答系统。构建含 79 万条中文医疗对话及临床诊疗指南 PDF 的向量知识库，支持科室分诊、症状查询、用药咨询等场景，提供自然语言检索与来源溯源能力。

## 目录

- [系统架构](#系统架构)
- [核心流程原理](#核心流程原理)
- [项目结构](#项目结构)
- [前端架构](#前端架构)
- [后端架构](#后端架构)
- [技术栈](#技术栈)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [开发指南](#开发指南)
- [API 接口](#api-接口)
- [离线评估](#离线评估)
- [免责声明](#免责声明)

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        用户界面（React SPA）                  │
│              登录 / 注册 → 会话管理 → SSE 流式问答              │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP / SSE
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                      API 网关（Nginx）                        │
│              /api/* → 后端    / → 前端静态文件                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Quart 异步 Web 服务                        │
│              路由发现 → 会话管理 → 对话流程编排                    │
└──────────┬────────────┬────────────┬────────────┬───────────┘
           │            │            │            │
           ▼            ▼            ▼            ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│    MySQL    │ │Elasticsearch│ │    Redis    │ │    MinIO    │
│  用户&会话   │ │ 向量+全文索引 │  │  锁/队列    │ │  文件存储     │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
```

**请求链路**（一次问答的完整路径）：

```
用户输入问题
    │
    ▼
查询预处理 ─── 分词 + TF-IDF 词权重 + 医疗同义词扩展
    │
    ▼
混合检索 ─── Elasticsearch BM25 全文检索 × BGE-m3 稠密向量检索
    │          加权融合（0.05 文本 + 0.95 向量）
    ▼
精排序 ─── BGE-reranker-v2-m3 语义评分 + Token Jaccard 复合评分
    │
    ▼
上下文装配 ─── Top-K 知识块 + 引用提示注入 system prompt
    │
    ▼
LLM 生成 ─── 主力模型 / 可配置备选模型，SSE 流式输出
    │
    ▼
引用插入 ─── 答案文本中插入 [ID:N] 标记，附带来源文档信息
    │
    ▼
前端渲染 ─── 流式逐字展示 + 可点击引用角标 + 悬停查看原文片段
```

---

## 核心流程原理

### 1. 文档解析与知识入库

#### PDF 临床指南（MinerU 解析器）

临床诊疗指南 PDF 经由 MinerU 提取结构化文本。解析后按文档标题层级（H1 → H6）递归切分为语义块：

```
H1 心血管疾病诊疗指南
  H2 高血压
    H3 药物治疗
      → chunk: "H1 心血管疾病诊疗指南 > H2 高血压 > H3 药物治疗\n钙通道阻滞剂（CCB）是..."
```

层级路径作为 chunk 元数据保留，检索时可依据标题层级提升相关性权重。

#### 医疗对话数据（Q&A 解析器）

79 万条中文医疗对话按「问题-回答」对切分：

```json
{
  "question": "高血压患者平时饮食要注意什么？",
  "answer": "高血压患者应遵循低盐低脂饮食原则..."
}
```

每个 Q&A 对作为一个原子 chunk，保留 `content_ltks`（问题分词）和 `content_sm_ltks`（细粒度分词）用于检索匹配。

#### 向量化

所有 chunk 使用 **BAAI/bge-m3** 生成 1024 维稠密向量，存入 Elasticsearch 的 `dense_vector` 字段。索引 mapping 同时保留：
- `content_with_weight`：带 TF-IDF 权重的文本，用于 BM25 全文检索
- `important_kwd`：TF-IDF 提取的关键词，权重提升 30 倍
- `q_*.term_vec`：每 token 的 BM25 词频/文档频率统计，用于复合评分

### 2. 查询预处理

用户问题进入检索管道前，经过三级预处理：

**第一级 — 分词与词权重**（`rag/nlp/term_weight.py`）

分词后，计算每个 token 的 TF-IDF 权重。高于阈值的 token 进入 `important_kwd` 字段，在检索时获得 30 倍权重提升。

**第二级 — 医疗同义词扩展**（`rag/nlp/synonym.py`）

加载双词典：
- `synonym.json`（通用中文同义词）
- `medical_synonym.json`（医疗专用，112 组疾病术语映射）

```
"心肌梗死" → ["心梗", "AMI", "急性心梗", "心肌梗塞"]
"高血压"   → ["血压高", "原发性高血压", "HTN"]
"糖尿病"   → ["血糖升高", "DM", "消渴症"]
```

每个用户查询词如果命中同义词表，其所有同义词作为 `OR` 条件加入检索，扩大召回范围。

**第三级 — 查询构建**（`rag/nlp/query.py`）

构建 Elasticsearch `bool` 查询：
```json
{
  "bool": {
    "should": [
      {"match": {"title_tks^10":      "高血压 饮食"}},
      {"match": {"important_kwd^30":  "高血压 饮食 注意"}},
      {"match": {"question_tks^20":   "高血压 饮食 注意 什么"}},
      {"match": {"content_ltks^2":    "高血压 饮食 注意 什么"}}
    ],
    "minimum_should_match": 1
  }
}
```

### 3. 混合检索

检索采用 **全文检索 + 向量检索加权融合** 策略（`rag/nlp/search.py`）：

```
融合分数 = 0.05 × BM25 文本分数 + 0.95 × 余弦相似度分数
```

| 组件 | 实现 | 作用 |
|---|---|---|
| BM25 全文检索 | Elasticsearch `match` + 字段加权 | 精确匹配医学术语、药名、数字范围 |
| 向量检索 | BGE-m3 embedding + `knn` query | 语义近似匹配，覆盖同义不同表述 |
| 加权融合 | Elasticsearch 加权求和 | 综合两种检索的优势 |

**降级策略**：若加权融合无结果，降为纯全文检索（`similarity_threshold=0.17`，`minimum_should_match=0.1`），保证至少召回部分相关文档。

### 4. 精排序

粗召回后，候选文档经过两级精排（`rag/nlp/search.py:Dealer.retrieval()`）：

**第一级 — BGE-reranker-v2-m3 重排序**

使用 Cross-Encoder 架构的 BGE-reranker-v2-m3 模型，对每个 (query, chunk) 对计算深度语义相关度分数。

**第二级 — Token Jaccard 相似度**

计算查询 token 集合与 chunk token 集合的交并比，补偿向量模型对精确术语匹配的不足。

### 5. 生成与溯源

#### Prompt 装配（`rag/prompts/generator.py`）

Top-K chunk 被格式化为上下文注入 system prompt：

```
你是一个专业的医疗助手。请根据以下知识库内容回答用户问题。

------
[文档名: 高血压诊疗指南.pdf | 页码: 23]
钙通道阻滞剂（CCB）是高血压一线治疗药物之一...
------
[文档名: 心血管内科对话.json | Q&A #1042]
高血压患者应遵循低盐低脂饮食原则，每日食盐摄入量...
------

### Query:
高血压患者平时饮食要注意什么？

在回答中引用具体来源时，使用 [ID:0]、[ID:1] 标记。
```

#### 流式生成（`api/db/services/dialog_service.py`）

LLM 以 SSE（Server-Sent Events）流式输出，每个事件携带增量 token。前端逐字渲染，实现打字机效果。

#### 引用插入（`retriever.insert_citations()`）

答案生成完毕后，在文本中插入 `[ID:N]` 标记：

```
高血压患者应注意 [ID:0] 低盐饮食，每日食盐摄入不超过 6g [ID:1]。
```

前端渲染时将 `[ID:0]` 替换为蓝色可点击角标 `[1]`，鼠标悬停显示来源文档名和原文片段。

### 6. 多模型路由与容错

系统实现了 **主备模型自动切换**（`api/db/services/llm_service.py`）：

- **主力模型**：由 `conf/service_conf.yaml` 中 `user_default_llm` 配置决定（默认 DeepSeek）
- **备选模型**：通过环境变量 `FALLBACK_LLM_FACTORY` / `FALLBACK_LLM_NAME` 指定，主力不可用时自动接管
- **切换逻辑**：`LLMBundle.async_chat()` 捕获主力异常后，实例化备选 `LLMBundle` 重试

---

## 项目结构

```
RAG-MedQA/
├── api/                          # 后端服务
│   ├── apps/                     # Quart 应用 + API 路由模块
│   │   ├── __init__.py           # 应用工厂：Quart 实例化、蓝图自动发现、SPA 静态托管
│   │   ├── sdk/chat.py           # 对话 / 会话 / 问答 接口（/api/v1/chats/...）
│   │   ├── kb_app.py             # 知识库管理（/v1/kb/...）
│   │   ├── llm_app.py            # LLM 模型配置（/v1/llm/...）
│   │   ├── user_app.py           # 用户注册 / 登录 / 设置（/v1/user/...）
│   │   └── system_app.py         # 系统状态与配置（/v1/system/...）
│   ├── db/
│   │   ├── db_models.py          # Peewee ORM 模型定义
│   │   ├── services/             # 业务逻辑层
│   │   │   ├── dialog_service.py     # 对话核心：检索 + 生成编排
│   │   │   ├── conversation_service.py # 会话 CRUD + SSE 流构造
│   │   │   ├── document_service.py    # 文档解析进度管理
│   │   │   └── llm_service.py         # LLM 调用 + 主备路由
│   │   └── runtime_config.py     # 运行时配置
│   └── ragflow_server.py         # 服务入口
│
├── rag/                          # RAG 核心引擎
│   ├── nlp/
│   │   ├── search.py             # Dealer 检索器：混合搜索 + 精排 + 引用插入
│   │   ├── query.py              # 查询构造：分词 + 权重 + 同义词扩展
│   │   ├── term_weight.py        # TF-IDF 词权重计算
│   │   ├── synonym.py            # 医疗同义词加载与扩展
│   │   └── rag_tokenizer.py      # 分词器封装
│   ├── llm/
│   │   ├── chat_model.py         # 聊天模型抽象层（多供应商后端）
│   │   ├── embedding_model.py    # Embedding 模型抽象层
│   │   └── rerank_model.py       # Reranker 模型抽象层
│   ├── prompts/
│   │   ├── generator.py          # Prompt 模板：知识格式化 + 引用指令
│   │   └── citation_prompt.md    # 引用格式提示模板（及其他 prompt 模板）
│   ├── app/
│   │   ├── qa.py                 # Q&A 对话分块器
│   │   ├── naive.py              # 通用文本分块器
│   │   └── tag.py                # 问题标签/分诊分类
│   └── res/
│       ├── synonym.json           # 通用同义词词典
│       ├── medical_synonym.json  # 医疗同义词词典（112 组）
│       └── ner.json              # 命名实体识别词典
│
├── parser/                       # 文档解析器
│   ├── mineru_parser.py          # MinerU PDF → Markdown 解析（临床指南）
│   ├── json_parser.py            # JSON / JSONL 医疗对话数据解析（79 万条）
│   ├── markdown_parser.py        # Markdown 结构化切块（MinerU 输出后处理）
│   └── utils.py                  # 文本读取、PDF 页数统计
│
├── evaluation/                   # 离线检索评估工具（独立脚本，不依赖后端服务）
│   ├── run_eval.py               # 评估入口：读取数据集 → 直连 ES 检索 → 输出指标
│   ├── build_dataset.py          # 构建评估数据集
│   ├── config.py                 # 评估配置（ES 连接、数据集路径、指标阈值）
│   ├── dataset/                  # 评估数据集（JSONL 格式）
│   └── results/                  # 评估结果输出目录
│
├── web/                          # 前端 SPA
│   ├── src/
│   │   ├── pages/
│   │   │   ├── chat/index.tsx        # 聊天主界面（Sidebar + keyed SessionView）
│   │   │   ├── landing/index.tsx     # 落地页（游客免费体验，最多 3 次）
│   │   │   ├── login/index.tsx       # 登录页
│   │   │   ├── register/index.tsx    # 注册页
│   │   │   └── profile/index.tsx     # 个人信息 / 修改密码
│   │   ├── components/ui/        # Radix UI 组件库（Tooltip、Dialog 等）
│   │   ├── services/api.ts       # API 客户端（SSE 流、会话管理、类型定义）
│   │   ├── utils/citations.tsx   # 引用角标渲染（正则匹配 → Tooltip）
│   │   └── routes.tsx            # 前端路由配置
│   ├── tailwind.config.js        # Tailwind 蓝白医疗主题
│   └── vite.config.ts            # Vite 构建配置
│
├── common/                       # 共享模块
│   ├── settings.py               # 全局配置初始化
│   ├── config_utils.py           # YAML 配置读取 + 解密
│   ├── constants.py              # 常量定义
│   └── file_utils.py             # 文件路径工具
│
├── conf/
│   ├── service_conf.yaml         # 主配置文件（数据库、ES、模型）
│   ├── llm_factories.json        # LLM 供应商注册表
│   └── *.json                    # ES mapping 模板
│
├── docker/
│   ├── docker-compose.yml        # 生产环境（6 服务：MySQL + Redis + ES + MinIO + Backend + Nginx）
│   ├── docker-compose-base.yml   # 开发环境（仅基础设施，后端本地启动）
│   ├── nginx.conf                # Nginx 反向代理配置
│   └── .env                      # 环境变量模板
│
├── Dockerfile                    # 多阶段构建（前端 npm build + 后端 Python）
├── pyproject.toml                # Python 项目配置
└── README.md
```

---

## 前端架构

### 组件层级

```
App
└── RouterProvider
    ├── LandingPage          # 未登录：游客体验（最多 3 次问答），超限显示注册引导
    ├── LoginPage / RegisterPage
    └── ChatPage             # 已登录
        ├── Sidebar（会话列表、新建按钮、重命名、用户信息）
        └── SessionView key={activeId}  ← 会话切换时 React 完全重新挂载
            ├── Welcome 区（Logo + 4 个示例问题）
            ├── MessageBubble[]（消息列表，含 SSE 流式光标）
            │   └── renderWithCitations()（[ID:N] → 可点击角标）
            └── InputBar（多行输入框 + 发送按钮，Enter 发送 / Shift+Enter 换行）
```

### 会话隔离机制

`SessionView` 使用 `key={activeId}` 挂载。当用户点击侧边栏切换会话时：

1. `activeId` 变更 → `key` 变更
2. React **彻底卸载**旧 `SessionView` 实例——丢弃其全部 state、ref、pending setState、in-flight fetch
3. React **全新挂载**新 `SessionView` 实例——`useState` 初始值从 session prop 读取历史消息

这从根本上杜绝了跨会话的状态泄露。

### SSE 流式问答

```typescript
// api.ts — AsyncGenerator 模式
export async function* askStream(question, sessionId, ...) {
  const res = await fetch('/api/v1/chats/ask', { method: 'POST', ... });
  const reader = res.body.getReader();
  while (true) {
    const { done, value } = await reader.read();
    // 解析 SSE "data:" 行，逐 chunk yield
    yield { answer: chunk.answer, done: chunk.final, reference: chunk.reference };
  }
}

// chat/index.tsx — for await 消费
for await (const chunk of askStream(...)) {
  if (chunk.done) break;
  fullAnswer += chunk.answer;
  setMessages(prev => prev.map(m =>
    m.id === streamId ? { ...m, content: fullAnswer } : m
  ));
}
```

### 引用溯源渲染

```typescript
// utils/citations.tsx
export function renderWithCitations(content: string, refs?: Reference) {
  // 正则拆分 "[ID:0]"、"[ID:1]"
  // → 替换为 Radix Tooltip 包裹的蓝色角标
  // → 悬停显示：文档名 + 原文片段
}
```

---

## 后端架构

### 应用启动流程

```
ragflow_server.py
  → init_root_logger()                # 日志初始化
  → settings.init_settings()          # 全局配置加载（DB、ES、LLM）
  → init_web_db()                     # Peewee 建表 / 迁移
  → init_web_data()                   # 初始数据填充
  → RuntimeConfig.init_env()          # 运行时配置
  → 启动 update_progress 后台线程      # 文档解析进度轮询（Redis 分布式锁保护）
  → app.run(host, port)               # Quart/Hypercorn 服务启动
```

### 路由自动发现

`api/apps/__init__.py` 扫描 `api/apps/` 和 `api/apps/sdk/` 目录下的 `*_app.py` / `*.py` 文件，自动注册为 Quart Blueprint：

- `api/apps/*_app.py` → 前缀 `/{version}/{page_name}`（如 `/v1/kb`、`/v1/user`）
- `api/apps/sdk/*.py` → 前缀 `/api/{version}`（如 `/api/v1/chats`）

### 数据模型（Peewee ORM）

核心表关系：

```
User（用户账户）
  ├── Knowledgebase（知识库）
  │     └── Document（文档）
  │           └── File2Document ← File（文件树）
  ├── Dialog（对话应用配置，绑定知识库）
  │     └── Conversation（会话）
  │           ├── message（JSON 消息数组）
  │           └── reference（JSON 引用数组，与消息并行）
  ├── LLMFactory / TenantLLM（LLM 供应商与模型配置）
  └── Task（文档解析任务，含进度追踪）
```

---

## 技术栈

| 层次 | 组件 | 说明 |
|---|---|---|
| **文档解析** | MinerU（CLI / API） | 临床指南 PDF → Markdown |
| | parser（JSON + Markdown） | JSON 对话数据解析 + Markdown 结构化切块 |
| **Embedding** | BAAI/bge-m3 | 1024 维稠密向量，中英双语 |
| **Reranker** | BAAI/bge-reranker-v2-m3 | Cross-Encoder 精排 |
| **向量 + 全文** | Elasticsearch 8.x | 混合索引 + 加权融合检索 |
| **LLM** | 可配置（默认 DeepSeek） | 支持所有兼容 OpenAI 接口的供应商，配置备选模型实现自动降级 |
| **关系数据库** | MySQL 8.0 | 用户、会话、知识库元数据 |
| **缓存 / 队列** | Redis（Valkey 8） | 分布式锁、任务队列 |
| **对象存储** | MinIO | 上传文件存储 |
| **后端框架** | Python / Quart | 异步 Web 服务（Flask 兼容 API） |
| **ORM** | Peewee | 轻量级 ORM，连接池 + 自动重连 |
| **前端框架** | React 18 / TypeScript | SPA 应用 |
| **UI 组件** | Radix UI + Tailwind CSS | 无障碍组件 + 原子化样式 |
| **构建工具** | Vite 7 | 前端打包 |
| **容器化** | Docker Compose | 一键部署（MySQL + ES + Redis + MinIO + Backend + Nginx） |

---

## 快速开始

### 环境要求

- Python 3.10–3.12
- Node.js ≥ 18.20.4
- Docker & Docker Compose
- 16 GB+ RAM，50 GB+ 磁盘

### 生产部署

```bash
# 1. 配置 API Key
cp docker/.env.example docker/.env
# 编辑 docker/.env，至少填写主力 LLM 的 API Key

# 2. 启动所有服务
cd docker
docker compose up -d

# 3. 访问
# Web UI：http://localhost
# API：http://localhost/api/v1
```

服务启动顺序：MySQL → Redis → Elasticsearch → MinIO → Backend → Nginx。Docker Compose 通过 `depends_on` + `healthcheck` 保证依赖就绪。

### 开发环境

```bash
# 1. 启动基础设施（MySQL, Redis, ES, MinIO）
docker compose -f docker/docker-compose-base.yml up -d

# 2. 后端
uv sync --python 3.12
source .venv/bin/activate
export PYTHONPATH=$(pwd)
python api/ragflow_server.py

# 3. 前端（新终端）
cd web
npm install
npm run dev          # 开发服务器，默认 http://localhost:9222
```

### 知识库配置

1. 访问 Web UI，注册 / 登录
2. 通过 `/v1/kb/` 接口或前端页面创建知识库，配置：
   - **PDF 临床指南**：解析方式 `MinerU`，切块策略 `Hierarchical`
   - **医疗对话数据**：解析方式 `Q&A`，上传 JSON / JSONL / CSV
3. Embedding 模型选择 `BAAI/bge-m3`
4. Reranker 选择 `BAAI/bge-reranker-v2-m3`

---

## 配置说明

### 主配置（`conf/service_conf.yaml`）

```yaml
RAG-MedQA:
  host: 0.0.0.0
  http_port: 9380
mysql:
  name: 'rag_flow'
  user: 'root'
  password: 'infini_rag_flow'
  host: 'localhost'
  port: 3306

es:
  hosts: 'http://localhost:1200'
  username: 'elastic'
  password: 'infini_rag_flow'

redis:
  host: 'localhost:6379'
  password: 'infini_rag_flow'

user_default_llm:
  factory: 'DeepSeek'
  api_key: 'sk-xxxxxxxx'
  base_url: 'https://api.deepseek.com/v1'
  default_models:
    chat_model: 'deepseek-chat'
    embedding_model: 'BAAI/bge-m3'
    rerank_model: 'BAAI/bge-reranker-v2-m3'
```

### 环境变量（`docker/.env`）

| 变量 | 必需 | 默认值 | 说明 |
|---|---|---|---|
| `MYSQL_ROOT_PASSWORD` | 否 | `infini_rag_flow` | MySQL root 密码 |
| `REDIS_PASSWORD` | 否 | `infini_rag_flow` | Redis 密码 |
| `QUART_RESPONSE_TIMEOUT` | 否 | `600` | 后端响应超时（秒），本地 CPU 推理时建议调大 |
| `REGISTER_ENABLED` | 否 | `1` | `0` = 关闭新用户注册 |
| `FALLBACK_LLM_FACTORY` | 否 | — | 备选 LLM 供应商（如 `Qwen`），主力不可用时自动切换 |
| `FALLBACK_LLM_NAME` | 否 | — | 备选 LLM 模型名（如 `qwen-max`） |

### LLM 供应商注册

`conf/llm_factories.json` 定义了所有可用的 LLM 供应商（DeepSeek、OpenAI、Qwen、Zhipu 等），包括各供应商的模型列表和 API 端点模板。

---

## 开发指南

### 后端

```bash
# 安装依赖
uv sync --python 3.12

# 启动（开发模式，支持热重载）
python api/ragflow_server.py --debug

# 初始化超级用户（首次部署）
python api/ragflow_server.py --init-superuser
```

### 前端

```bash
cd web
npm install
npm run dev       # 开发服务器，HMR 热更新
npm run build     # 生产构建，输出到 web/dist/
```

### 添加新的 API 路由

在 `api/apps/sdk/` 下新建 `xxx_app.py`，定义 `manager`（Blueprint）和路由处理函数，系统启动时自动发现并注册到 `/api/v1/` 前缀下。

### 添加新的文档解析器

1. 在 `rag/app/` 下实现分块逻辑（参考 `qa.py`）
2. 解析器列表由 `common/settings.py` 中的 `PARSERS` 变量控制

---

## API 接口

### 用户认证

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/v1/user/login` | 登录（RSA 加密密码） |
| `POST` | `/v1/user/register` | 注册 |
| `GET` | `/v1/user/logout` | 退出登录 |
| `GET` | `/v1/user/info` | 当前用户信息 |
| `POST` | `/v1/user/setting` | 修改昵称 / 头像 |
| `POST` | `/v1/user/forget/otp` | 发送密码重置验证码 |
| `POST` | `/v1/user/forget/verify-otp` | 验证 OTP |
| `POST` | `/v1/user/forget/reset-password` | 重置密码 |

### 对话与会话

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/v1/chats` | 获取对话应用列表 |
| `POST` | `/api/v1/chats` | 创建对话应用 |
| `GET` | `/api/v1/chats/{chat_id}` | 获取对话应用详情 |
| `PUT` | `/api/v1/chats/{chat_id}` | 更新对话应用配置 |
| `DELETE` | `/api/v1/chats/{chat_id}` | 删除对话应用 |
| `GET` | `/api/v1/chats/{chat_id}/sessions` | 获取会话列表 |
| `POST` | `/api/v1/chats/{chat_id}/sessions` | 创建新会话 |
| `GET` | `/api/v1/chats/{chat_id}/sessions/{id}` | 获取单个会话详情（含历史消息） |
| `PUT` | `/api/v1/chats/{chat_id}/sessions/{id}` | 重命名会话 |
| `POST` | `/api/v1/chats/ask` | **核心接口**：提交问题，SSE 流式返回答案 + 引用 |

### 知识库

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/v1/kb/detail` | 知识库详情 |
| `POST` | `/v1/kb/list` | 知识库列表（支持分页 / 过滤） |
| `POST` | `/v1/kb/create` | 创建知识库 |
| `POST` | `/v1/kb/update` | 更新知识库配置 |

### SSE 响应格式

```
# 流式帧（incremental token）
data:{"code":0,"data":{"answer":"高血压","reference":{},"final":false}}

# 最终帧（含完整答案和引用）
data:{"code":0,"data":{"answer":"高血压患者应注意[ID:0]低盐饮食...","reference":{"chunks":[...]},"final":true}}

# 结束信号
data:{"code":0,"data":true}
```

- **流式帧**：`final: false`，`answer` 为增量 token
- **最终帧**：`final: true`，`answer` 含完整答案 + `[ID:N]` 引用，`reference` 含来源 chunks
- **结束信号**：`data: true`

---

## 离线评估

系统提供独立的离线检索评估工具（`evaluation/`），直接连接 ES 运行，无需启动后端服务。

### 数据集格式（JSONL）

```jsonl
{"id": "qa_0001", "question": "高血压患者饮食注意事项？", "reference_answer": "低盐低脂，每日食盐<6g..."}
{"id": "qa_0002", "question": "降压药什么时候服用效果最好？", "reference_answer": "清晨空腹服用长效降压药..."}
```

### 运行评估

```bash
# 1. 构建评估数据集（从训练集采样 200 条）
python evaluation/build_dataset.py

# 2. 运行评估（直连 ES，无需启动后端）
python evaluation/run_eval.py

# 结果输出到 evaluation/results/run_YYYYMMDD_HHMMSS.json
```

### 评估指标

| 指标 | 说明 |
|---|---|
| `hit_rate` | 至少命中一个相关 chunk 的问题占比（= Recall@K） |
| `recall@1/3/5/10` | 首个相关 chunk 排在前 N 名内的问题占比 |
| `mrr` | 首个相关 chunk 排名倒数的均值（Mean Reciprocal Rank） |

命中判定标准：检索到的 chunk 与标准答案之间的 Token Overlap F1 ≥ 0.3。

### 当前评估结果

> 数据集：从 79 万条医疗对话中按科室均匀采样 200 条，固定随机种子 42。  
> 检索方式：ES `multi_match`（纯 BM25，不含向量检索），K=10。

| 指标 | 值 |
|---|---|
| **Recall@10 (hit_rate)** | **96.50%** |
| Recall@1 | 88.00% |
| Recall@3 | 93.00% |
| Recall@5 | 93.50% |
| **MRR** | **0.9095** |

R@1 = 88% 说明约 88% 的问题答案出现在检索结果第一位；MRR ≈ 0.91 说明平均首个命中排名极靠前，纯 BM25 在本数据集上已有强劲基准。

---

## 免责声明

本系统基于知识库提供医疗参考信息，不构成正式医疗建议。具体诊疗请以执业医师的专业判断为准。
