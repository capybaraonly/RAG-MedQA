"""
运行离线检索评测：复现生产 pipeline（ES 混合检索 + 规则重排序），直连 ES 和
Embedding HTTP 服务，无需启动后端。

生产 pipeline（search.py:Dealer.retrieval / rerank）：
  1. ES 混合检索：0.95×KNN(BGE-m3) + 0.05×BM25，候选 top_k=1024
  2. 规则重排序：0.3×cosine_sim(chunk_vec, query_vec) + 0.7×token_overlap
  3. 过滤 similarity ≥ 0.2，取 top_n=6 传给 LLM

输出：evaluation/results/run_YYYYMMDD_HHMMSS.json
"""

import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (
    ES_HOSTS,
    ES_USERNAME,
    ES_PASSWORD,
    ES_INDEX,
    DATASET_FILE,
    RESULTS_DIR,
    TOP_K,
    TOKEN_OVERLAP_THRESHOLD,
)

from elasticsearch import Elasticsearch

try:
    import jieba
    _has_jieba = True
except ImportError:
    _has_jieba = False

# ── 生产参数（对齐 dialog 表实际配置） ───────────────────────────────────────
KB_ID = "c277d0072a2a476795de09b797164c0e"
TOP_RETRIEVAL = 1024        # ES 粗召回候选数
RERANK_TK_WEIGHT = 0.7     # token overlap 权重
RERANK_VT_WEIGHT = 0.3     # 向量相似度权重
SIMILARITY_THRESHOLD = 0.2  # 重排后过滤阈值
TOP_N = 6                   # 传给 LLM 的 chunk 数（最终评测 K）

# ── Embedding 服务 ───────────────────────────────────────────────────────────
EMB_URL = os.environ.get("EVAL_EMB_URL", "http://localhost:6380/v1/embeddings")
EMB_MODEL = os.environ.get("EVAL_EMB_MODEL", "bge-m3")


# ── 分词（用于 token overlap） ───────────────────────────────────────────────
def tokenize(text: str) -> set[str]:
    if _has_jieba:
        tokens = jieba.lcut(text)
    else:
        tokens = list(text)
    result = set()
    for t in tokens:
        t = t.strip()
        if t and not all(c in "，。！？、；：""''（）【】《》…—·,.;:!?()[]{}" for c in t):
            result.add(t)
    return result


def tokenize_list(text: str) -> list[str]:
    """返回列表，用于 token overlap 计算（保留重复）"""
    if _has_jieba:
        return [t for t in jieba.lcut(text) if t.strip()]
    return list(text)


# ── Token Overlap F1（判定命中用） ───────────────────────────────────────────
def token_f1(chunk_tokens: set[str], answer_tokens: set[str]) -> float:
    if not chunk_tokens or not answer_tokens:
        return 0.0
    intersection = chunk_tokens & answer_tokens
    precision = len(intersection) / len(chunk_tokens)
    recall = len(intersection) / len(answer_tokens)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


# ── Token Overlap（重排序用，对齐 qryr.token_similarity） ────────────────────
def token_overlap(query_tks: list[str], chunk_tks: list[str]) -> float:
    """Jaccard-style token overlap，对齐 search.py 规则重排中的 tksim 计算。"""
    if not query_tks or not chunk_tks:
        return 0.0
    q_set = set(query_tks)
    c_set = set(chunk_tks)
    inter = q_set & c_set
    union = q_set | c_set
    return len(inter) / len(union) if union else 0.0


# ── 余弦相似度 ───────────────────────────────────────────────────────────────
def cosine_sim(a: list[float], b: list[float]) -> float:
    a, b = np.array(a), np.array(b)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom > 1e-9 else 0.0


# ── Embedding API ─────────────────────────────────────────────────────────────
def get_embedding(text: str) -> list[float]:
    resp = requests.post(
        EMB_URL,
        json={"model": EMB_MODEL, "input": [text]},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]


# ── ES 客户端 ─────────────────────────────────────────────────────────────────
def build_es_client() -> Elasticsearch:
    hosts = [h.strip() for h in ES_HOSTS.split(",")]
    if ES_USERNAME and ES_PASSWORD:
        return Elasticsearch(hosts, basic_auth=(ES_USERNAME, ES_PASSWORD), verify_certs=False, timeout=60)
    return Elasticsearch(hosts, verify_certs=False, timeout=60)


# ── ES 混合检索（复现 Dealer.search 的 KNN + BM25 fusion） ───────────────────
def search_hybrid(es: Elasticsearch, question: str, query_vec: list[float]) -> list[dict]:
    """
    对齐 search.py:ESConnection.search() 的混合检索逻辑：
      - KNN: q_1024_vec, boost 0.95
      - BM25: multi_match, boost 0.05
    返回原始 ES hits，每个 hit 含 _source（包括 q_1024_vec、content_ltks）
    """
    kb_filter = [
        {"terms": {"kb_id": [KB_ID]}},
        {"bool": {"must_not": {"range": {"available_int": {"lt": 1}}}}},
    ]

    body = {
        "knn": {
            "field": "q_1024_vec",
            "query_vector": query_vec,
            "k": TOP_RETRIEVAL,
            "num_candidates": TOP_RETRIEVAL * 2,
            "filter": {"bool": {"filter": kb_filter}},
            "boost": 0.95,
        },
        "query": {
            "bool": {
                "must": [{
                    "multi_match": {
                        "query": question,
                        "fields": [
                            "title_tks^10",
                            "important_kwd^30",
                            "question_tks^20",
                            "content_ltks^2",
                            "content_with_weight",
                        ],
                        "type": "best_fields",
                        "minimum_should_match": "30%",
                    }
                }],
                "filter": kb_filter,
                "boost": 0.05,
            }
        },
        "_source": ["content_with_weight", "content_ltks", "q_1024_vec"],
        "fields": ["q_1024_vec"],
        "size": TOP_RETRIEVAL,
    }

    try:
        resp = es.search(index=ES_INDEX, body=body, request_timeout=30)
    except Exception as e:
        print(f"  ES search error: {e}", file=sys.stderr)
        return []

    hits = []
    for h in resp.get("hits", {}).get("hits", []):
        src = h.get("_source", {})
        # ES 9.x 可能把 dense_vector 放在 fields 而非 _source
        vec = src.get("q_1024_vec") or (h.get("fields") or {}).get("q_1024_vec")
        if isinstance(vec, str):
            vec = [float(x) for x in vec.split("\t")]
        hits.append({
            "chunk_id": h["_id"],
            "content": src.get("content_with_weight", ""),
            "content_ltks": src.get("content_ltks", ""),
            "vec": vec or [],
        })
    return hits


# ── 规则重排序（复现 Dealer.rerank，无 reranker 模型时的路径） ────────────────
def rerank_hits(hits: list[dict], query_vec: list[float], question: str) -> list[dict]:
    """
    对齐 search.py:Dealer.rerank()：
      sim = RERANK_VT_WEIGHT * cosine(query_vec, chunk_vec)
            + RERANK_TK_WEIGHT * token_overlap(query_tks, chunk_tks)
    """
    query_tks = tokenize_list(question)
    scored = []
    for h in hits:
        vt = cosine_sim(query_vec, h["vec"]) if h["vec"] else 0.0
        tk = token_overlap(query_tks, h["content_ltks"].split())
        sim = RERANK_VT_WEIGHT * vt + RERANK_TK_WEIGHT * tk
        scored.append({**h, "similarity": sim})
    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return [s for s in scored if s["similarity"] >= SIMILARITY_THRESHOLD]


# ── 单条评测 ──────────────────────────────────────────────────────────────────
def evaluate_single(
    es: Elasticsearch,
    case: dict,
    answer_tokens: set[str],
) -> dict:
    question = case["question"]

    # 1. 获取查询向量
    try:
        query_vec = get_embedding(question)
    except Exception as e:
        print(f"  Embedding error for qa_{case['id']}: {e}", file=sys.stderr)
        return {"id": case["id"], "question": question[:200], "hit": False,
                "first_hit_rank": None, "top_chunks": [], "error": str(e)}

    # 2. ES 混合检索
    hits = search_hybrid(es, question, query_vec)
    if not hits:
        return {"id": case["id"], "question": question[:200], "hit": False,
                "first_hit_rank": None, "top_chunks": []}

    # 3. 规则重排序，取 top TOP_N
    reranked = rerank_hits(hits, query_vec, question)[:TOP_N]

    # 4. 判定命中
    hit = False
    first_hit_rank = None
    for rank, chunk in enumerate(reranked, 1):
        chunk_tokens = tokenize(chunk["content"])
        if token_f1(chunk_tokens, answer_tokens) >= TOKEN_OVERLAP_THRESHOLD:
            hit = True
            first_hit_rank = rank
            break

    return {
        "id": case["id"],
        "question": question[:200],
        "hit": hit,
        "first_hit_rank": first_hit_rank,
        "top_chunks": [c["chunk_id"] for c in reranked],
    }


# ── 指标汇总 ──────────────────────────────────────────────────────────────────
def compute_summary(results: list[dict], top_n: int) -> dict:
    total = len(results)
    if total == 0:
        return {}

    hit_count = sum(1 for r in results if r["hit"])
    mrr_sum = 0.0
    recall_at = {1: 0, 3: 0, 5: 0, top_n: 0}

    for r in results:
        if r["hit"] and r["first_hit_rank"] is not None:
            mrr_sum += 1.0 / r["first_hit_rank"]
            for k in recall_at:
                if r["first_hit_rank"] <= k:
                    recall_at[k] += 1

    summary = {
        "total": total,
        "top_n": top_n,
        "hit_rate": hit_count / total,
        "mrr": mrr_sum / total,
    }
    for k in sorted(recall_at):
        summary[f"recall_at_{k}"] = recall_at[k] / total
    return summary


# ── 主入口 ────────────────────────────────────────────────────────────────────
def main():
    if not os.path.exists(DATASET_FILE):
        print(f"错误: 评测集文件不存在: {DATASET_FILE}", file=sys.stderr)
        print("请先运行: python evaluation/build_dataset.py", file=sys.stderr)
        sys.exit(1)

    test_cases = []
    with open(DATASET_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                test_cases.append(json.loads(line))
    print(f"加载评测集: {len(test_cases)} 条")

    # 验证 Embedding 服务
    print(f"验证 Embedding 服务: {EMB_URL}")
    try:
        test_vec = get_embedding("test")
        print(f"Embedding 服务正常，向量维度: {len(test_vec)}")
    except Exception as e:
        print(f"错误: Embedding 服务不可用 ({e})", file=sys.stderr)
        sys.exit(1)

    # 连接 ES
    print(f"连接 ES: {ES_HOSTS}, index={ES_INDEX}")
    es = build_es_client()
    if not es.ping():
        print("错误: 无法连接到 Elasticsearch", file=sys.stderr)
        sys.exit(1)
    print("ES 连接成功")

    print(f"\nPipeline 参数:")
    print(f"  ES 粗召回 top_k={TOP_RETRIEVAL}, KNN:BM25=0.95:0.05")
    print(f"  重排序 vtweight={RERANK_VT_WEIGHT}, tkweight={RERANK_TK_WEIGHT}")
    print(f"  similarity_threshold={SIMILARITY_THRESHOLD}, top_n={TOP_N}\n")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    results_file = os.path.join(RESULTS_DIR, f"run_{ts}.json")

    per_case = []
    t0 = time.time()
    for i, case in enumerate(test_cases):
        if (i + 1) % 20 == 0:
            elapsed = time.time() - t0
            eta = elapsed / (i + 1) * (len(test_cases) - i - 1)
            print(f"  进度: {i + 1}/{len(test_cases)}  用时 {elapsed:.0f}s  预计剩余 {eta:.0f}s")
        answer_tokens = tokenize(case["reference_answer"])
        result = evaluate_single(es, case, answer_tokens)
        per_case.append(result)

    summary = compute_summary(per_case, TOP_N)

    output = {
        "run_at": ts,
        "config": {
            "pipeline": "hybrid_knn_bm25 + rule_rerank",
            "top_k_retrieval": TOP_RETRIEVAL,
            "knn_weight": 0.95,
            "bm25_weight": 0.05,
            "rerank_vt_weight": RERANK_VT_WEIGHT,
            "rerank_tk_weight": RERANK_TK_WEIGHT,
            "similarity_threshold": SIMILARITY_THRESHOLD,
            "top_n": TOP_N,
            "hit_threshold": TOKEN_OVERLAP_THRESHOLD,
            "es_index": ES_INDEX,
            "kb_id": KB_ID,
        },
        "summary": summary,
        "per_case": per_case,
    }

    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✓ 结果已保存: {results_file}")
    print(f"\n─── 指标汇总 ───")
    for k, v in summary.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.4f}")
        else:
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
