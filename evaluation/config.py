"""
离线评测模块配置。

从项目 service_conf.yaml 读取 ES 连接信息，同时定义采样参数和路径常量。
"""

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from common.config_utils import get_base_config

# ── Elasticsearch ───────────────────────────────────────────────────────
_es_config = get_base_config("es", {})
ES_HOSTS = os.environ.get("EVAL_ES_HOSTS", _es_config.get("hosts", "http://localhost:1200"))
ES_USERNAME = os.environ.get("EVAL_ES_USERNAME", _es_config.get("username", "elastic"))
ES_PASSWORD = os.environ.get("EVAL_ES_PASSWORD", _es_config.get("password", "infini_rag_flow"))
ES_INDEX = os.environ.get("EVAL_ES_INDEX", "ragmedqa")  # 对齐 SYSTEM_INDEX_NAME

# ── 数据来源 ────────────────────────────────────────────────────────────
RAW_DATA_PATH = os.path.join(REPO_ROOT, "data", "medical", "finetune", "train_zh_0.json")

# ── 采样参数 ────────────────────────────────────────────────────────────
SAMPLE_SIZE = 200
MIN_OUTPUT_LEN = 50
MAX_OUTPUT_LEN = 800

# ── 输出路径 ────────────────────────────────────────────────────────────
EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(EVAL_DIR, "dataset")
RESULTS_DIR = os.path.join(EVAL_DIR, "results")
DATASET_FILE = os.path.join(DATASET_DIR, "eval_dataset.jsonl")

# ── 检索参数 ────────────────────────────────────────────────────────────
TOP_K = 10  # 检索返回 top-K chunks
TOKEN_OVERLAP_THRESHOLD = 0.3  # token overlap F1 阈值，≥此值视为命中
