# RAG-MedQA

面向医疗咨询场景的检索增强生成（RAG）智能问答系统。构建含 79 万条中文医疗对话及临床诊疗指南 PDF 的向量知识库，支持科室分诊、症状查询、用药咨询等场景，提供自然语言检索与来源溯源能力。

## 系统架构

```
用户查询
    │
    ▼
查询预处理（分词 + 词权重计算 + 医疗同义词扩展）
    │
    ▼
混合检索（Elasticsearch 全文检索 × 向量检索加权融合）
    │
    ▼
精排序（BGE-reranker-v2-m3 + Token 相似度 + PageRank 复合评分）
    │
    ▼
Top-K 上下文选取
    │
    ▼
生成（DeepSeek 主力 / Qwen 降级备选 多模型路由）
    │
    ▼
回复 + 来源溯源展示 + 医疗免责声明
```

## 核心功能

### 知识入库

- **PDF 解析**：使用 MinerU 提取临床诊疗指南文本，按标题层级（H1→H6）递归切块，保留层级语义
- **对话数据**：79 万条中文医疗对话按「问题-回答」对作为原子切块单元，支持 JSON / JSONL / CSV / Excel 格式
- **向量表示**：使用 BGE-m3 生成稠密向量，存入 Elasticsearch

### 查询优化与混合检索

- 查询分词、TF-IDF 词权重计算
- **医疗同义词扩展**：专用医疗词典（心梗=心肌梗死=AMI 等），扩展候选关键词覆盖专业术语
- 构建加权布尔查询，提升医疗专有名词的全文检索命中率
- Elasticsearch 全文检索与向量检索加权融合（混合召回），解决纯向量检索对专有名词的漏召回问题

### 精排序

- 召回后接入 **BGE-reranker-v2-m3** 对候选结果精排
- **复合评分**：`0.5 × 语义相似度 + 0.3 × Token Jaccard 相似度 + 0.2 × PageRank`
- 筛选 Top-K 文档作为生成上下文

### 生成与溯源

- **多模型路由层**：DeepSeek 为主力模型，Qwen 为降级备选，服务不可用时自动切换，保障可用性
- 支持多轮追问，维护对话历史
- **来源溯源**：回复中标注引用来源（文档名 + 页码），支持追溯
- **医疗免责声明**：每条回复自动注入声明，明确本系统为参考信息，非正式诊疗建议

## 技术栈

| 组件 | 选型 |
|---|---|
| PDF 解析 | MinerU |
| Embedding | BAAI/bge-m3 |
| Reranker | BAAI/bge-reranker-v2-m3 |
| 向量存储 + 全文检索 | Elasticsearch |
| 主力 LLM | DeepSeek |
| 备选 LLM | Qwen |
| 后端框架 | Python / Flask |
| 前端框架 | React / TypeScript / UmiJS |
| 容器化 | Docker Compose |

## 快速开始

### 环境要求

- Python 3.10–3.12
- Node.js ≥ 18.20.4
- Docker & Docker Compose
- 16 GB+ RAM，50 GB+ 磁盘

### 部署

```bash
# 1. 配置环境变量
cp docker/.env.example docker/.env
# 编辑 docker/.env，填写 DeepSeek / Qwen API Key

# 2. 启动所有服务
cd docker
docker compose up -d

# 3. 访问系统
# Web UI：http://localhost
# API：http://localhost/api/v1
```

### 知识库配置

1. 登录 Web UI，创建知识库
2. **PDF 临床指南**：解析方式选 `MinerU`，切块策略选 `Hierarchical`
3. **医疗对话数据**：解析方式选 `Q&A`，上传 JSON / JSONL / CSV 文件
4. Embedding 模型选 `BAAI/bge-m3`，Reranker 选 `BAAI/bge-reranker-v2-m3`

### 开发模式

```bash
# 后端
uv sync --python 3.12 --all-extras
docker compose -f docker/docker-compose-base.yml up -d
source .venv/bin/activate && export PYTHONPATH=$(pwd)
bash docker/launch_backend_service.sh

# 前端
cd web && npm install && npm run dev
```

## 医疗同义词词典

词典位于 `rag/res/medical_synonym.json`，格式：

```json
{
  "心肌梗死": ["心梗", "AMI", "急性心梗", "心肌梗塞"],
  "高血压": ["血压高", "原发性高血压", "HTN"],
  "糖尿病": ["血糖升高", "DM", "消渴症"]
}
```

如需扩充，可从 [CBLUE](https://github.com/CBLUEbenchmark/CBLUE) 或 CMeKG 导入标准医疗术语。

## 模型路由配置

在 `docker/.env` 中配置主力与备选模型：

```env
# 主力模型（DeepSeek）
CHAT_FACTORY=DeepSeek
CHAT_MODEL_NAME=deepseek-chat
DEEPSEEK_API_KEY=your_key_here

# 降级备选（Qwen）
FALLBACK_LLM_FACTORY=Tongyi-Qianwen
FALLBACK_LLM_NAME=qwen-max
QWEN_API_KEY=your_key_here
```

## 免责声明

本系统基于知识库提供医疗参考信息，不构成正式医疗建议。具体诊疗请以执业医师的专业判断为准。
