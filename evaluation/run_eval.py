"""
运行离线检索评测：复现生产 pipeline（ES 混合检索 + 规则重排序），直连 ES 和
Embedding HTTP 服务，无需启动后端。

生产 pipeline（search.py:Dealer.retrieval / rerank）：
  1. ES 混合检索：knn_weight×KNN(BGE-m3) + (1-knn_weight)×BM25，候选 top_k=1024
  2. 规则重排序：vt_weight×cosine(chunk_vec, query_vec) + tk_weight×token_overlap
  3. 过滤 similarity ≥ similarity_threshold，取 top_n 传给 LLM

输出：evaluation/results/run_YYYYMMDD_HHMMSS.json
"""

import argparse
import json
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
    TOKEN_OVERLAP_THRESHOLD,
)

from elasticsearch import Elasticsearch

try:
    import jieba
    _has_jieba = True
except ImportError:
    _has_jieba = False

# ── 默认参数（对齐 dialog 表实际配置） ───────────────────────────────────────
DEFAULT_KB_ID = "c277d0072a2a476795de09b797164c0e"
DEFAULT_TOP_RETRIEVAL = 1024    # ES 粗召回候选数
DEFAULT_KNN_WEIGHT = 0.95       # KNN 权重（BM25 = 1 - knn_weight）
DEFAULT_RERANK_VT = 0.3         # 向量相似度权重
DEFAULT_RERANK_TK = 0.7         # token overlap 权重
DEFAULT_THRESHOLD = 0.2         # 重排后过滤阈值
DEFAULT_TOP_N = 6               # 传给 LLM 的 chunk 数
RECALL_AT_KS = [1, 3, 5, 10]   # 始终计算这些 K，与 top_n 无关

EMB_URL = os.environ.get("EVAL_EMB_URL", "http://localhost:6380/v1/embeddings")
EMB_MODEL = os.environ.get("EVAL_EMB_MODEL", "bge-m3")


# ── 分词 ──────────────────────────────────────────────────────────────────────
def tokenize(text: str) -> set[str]:
    tokens = jieba.lcut(text) if _has_jieba else list(text)
    result = set()
    for t in tokens:
        t = t.strip()
        if t and not all(c in "，。！？、；：""''（）【】《》…—·,.;:!?()[]{}" for c in t):
            result.add(t)
    return result


def tokenize_list(text: str) -> list[str]:
    return [t for t in (jieba.lcut(text) if _has_jieba else list(text)) if t.strip()]


# ── Token Overlap F1（判定命中） ──────────────────────────────────────────────
def token_f1(chunk_tokens: set[str], answer_tokens: set[str]) -> float:
    if not chunk_tokens or not answer_tokens:
        return 0.0
    inter = chunk_tokens & answer_tokens
    p = len(inter) / len(chunk_tokens)
    r = len(inter) / len(answer_tokens)
    return 2 * p * r / (p + r) if (p + r) > 0 else 0.0


# ── Token Overlap（重排序用） ─────────────────────────────────────────────────
def token_overlap(query_tks: list[str], chunk_tks: list[str]) -> float:
    if not query_tks or not chunk_tks:
        return 0.0
    q, c = set(query_tks), set(chunk_tks)
    union = q | c
    return len(q & c) / len(union) if union else 0.0


# ── 余弦相似度 ────────────────────────────────────────────────────────────────
def cosine_sim(a: list[float], b: list[float]) -> float:
    a, b = np.array(a, dtype=np.float32), np.array(b, dtype=np.float32)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom > 1e-9 else 0.0


# ── Embedding API ─────────────────────────────────────────────────────────────
def get_embedding(text: str) -> list[float]:
    resp = requests.post(EMB_URL, json={"model": EMB_MODEL, "input": [text]}, timeout=30)
    resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]


# ── ES 客户端 ─────────────────────────────────────────────────────────────────
def build_es_client() -> Elasticsearch:
    hosts = [h.strip() for h in ES_HOSTS.split(",")]
    if ES_USERNAME and ES_PASSWORD:
        return Elasticsearch(hosts, basic_auth=(ES_USERNAME, ES_PASSWORD),
                             verify_certs=False, request_timeout=60)
    return Elasticsearch(hosts, verify_certs=False, request_timeout=60)


# ── ES 混合检索 ───────────────────────────────────────────────────────────────
def search_hybrid(es: Elasticsearch, question: str, query_vec: list[float],
                  kb_id: str, knn_weight: float, top_retrieval: int) -> list[dict]:
    bm25_weight = round(1.0 - knn_weight, 4)
    kb_filter = [
        {"terms": {"kb_id": [kb_id]}},
        {"bool": {"must_not": {"range": {"available_int": {"lt": 1}}}}},
    ]
    body = {
        "knn": {
            "field": "q_1024_vec",
            "query_vector": query_vec,
            "k": top_retrieval,
            "num_candidates": top_retrieval * 2,
            "filter": {"bool": {"filter": kb_filter}},
            "boost": knn_weight,
        },
        "query": {
            "bool": {
                "must": [{
                    "multi_match": {
                        "query": question,
                        "fields": ["title_tks^10", "important_kwd^30",
                                   "question_tks^20", "content_ltks^2",
                                   "content_with_weight"],
                        "type": "best_fields",
                        "minimum_should_match": "30%",
                    }
                }],
                "filter": kb_filter,
                "boost": bm25_weight,
            }
        },
        "_source": ["content_with_weight", "content_ltks", "q_1024_vec"],
        "fields": ["q_1024_vec"],
        "size": top_retrieval,
    }
    try:
        resp = es.search(index=ES_INDEX, body=body, request_timeout=30)
    except Exception as e:
        print(f"  ES search error: {e}", file=sys.stderr)
        return []

    hits = []
    for h in resp.get("hits", {}).get("hits", []):
        src = h.get("_source", {})
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


# ── 规则重排序 ────────────────────────────────────────────────────────────────
def rerank_hits(hits: list[dict], query_vec: list[float], query_tks: list[str],
                vt_weight: float, tk_weight: float, threshold: float) -> list[dict]:
    scored = []
    for h in hits:
        vt = cosine_sim(query_vec, h["vec"]) if h["vec"] else 0.0
        tk = token_overlap(query_tks, h["content_ltks"].split())
        sim = vt_weight * vt + tk_weight * tk
        scored.append({**h, "similarity": sim})
    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return [s for s in scored if s["similarity"] >= threshold]


# ── 单条评测 ──────────────────────────────────────────────────────────────────
def evaluate_single(es: Elasticsearch, case: dict, answer_tokens: set[str],
                    kb_id: str, knn_weight: float, top_retrieval: int,
                    vt_weight: float, tk_weight: float, threshold: float,
                    top_n: int) -> dict:
    question = case["question"]

    try:
        query_vec = get_embedding(question)
    except Exception as e:
        print(f"  Embedding error: {e}", file=sys.stderr)
        return {"id": case["id"], "question": question[:200], "hit": False,
                "first_hit_rank": None, "top_chunks": [], "error": str(e)}

    hits = search_hybrid(es, question, query_vec, kb_id, knn_weight, top_retrieval)
    if not hits:
        return {"id": case["id"], "question": question[:200], "hit": False,
                "first_hit_rank": None, "top_chunks": []}

    query_tks = tokenize_list(question)
    # 重排后取足够多的候选（max(top_n, max RECALL_AT_KS)），以便计算所有 R@K
    max_k = max(top_n, max(RECALL_AT_KS))
    reranked = rerank_hits(hits, query_vec, query_tks, vt_weight, tk_weight, threshold)[:max_k]

    hit = False
    first_hit_rank: Optional[int] = None
    for rank, chunk in enumerate(reranked, 1):
        if token_f1(tokenize(chunk["content"]), answer_tokens) >= TOKEN_OVERLAP_THRESHOLD:
            hit = True
            first_hit_rank = rank
            break

    return {
        "id": case["id"],
        "question": question[:200],
        "hit": hit,
        "first_hit_rank": first_hit_rank,
        "top_chunks": [c["chunk_id"] for c in reranked[:top_n]],
    }


# ── 指标汇总 ──────────────────────────────────────────────────────────────────
def compute_summary(results: list[dict], top_n: int) -> dict:
    total = len(results)
    if total == 0:
        return {}

    mrr_sum = 0.0
    recall_at = {k: 0 for k in RECALL_AT_KS}
    hit_at_top_n = 0

    for r in results:
        rank = r.get("first_hit_rank")
        if rank is not None:
            mrr_sum += 1.0 / rank
            for k in recall_at:
                if rank <= k:
                    recall_at[k] += 1
            if rank <= top_n:
                hit_at_top_n += 1

    summary = {
        "total": total,
        "top_n": top_n,
        f"hit_rate_at_{top_n}": hit_at_top_n / total,
        "mrr": mrr_sum / total,
    }
    for k in sorted(recall_at):
        summary[f"recall_at_{k}"] = recall_at[k] / total
    return summary


# ── 主入口 ────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="RAG-MedQA 离线检索评测")
    parser.add_argument("--knn-weight", type=float, default=DEFAULT_KNN_WEIGHT)
    parser.add_argument("--rerank-vt", type=float, default=DEFAULT_RERANK_VT)
    parser.add_argument("--rerank-tk", type=float, default=DEFAULT_RERANK_TK)
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N)
    parser.add_argument("--top-retrieval", type=int, default=DEFAULT_TOP_RETRIEVAL)
    parser.add_argument("--kb-id", type=str, default=DEFAULT_KB_ID)
    args = parser.parse_args()

    if not os.path.exists(DATASET_FILE):
        print(f"错误: 评测集不存在: {DATASET_FILE}", file=sys.stderr)
        print("请先运行: python evaluation/build_dataset.py", file=sys.stderr)
        sys.exit(1)

    test_cases = []
    with open(DATASET_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                test_cases.append(json.loads(line))
    print(f"加载评测集: {len(test_cases)} 条")

    print(f"验证 Embedding 服务: {EMB_URL}")
    try:
        test_vec = get_embedding("test")
        print(f"Embedding 正常，维度: {len(test_vec)}")
    except Exception as e:
        print(f"错误: Embedding 服务不可用 ({e})", file=sys.stderr)
        sys.exit(1)

    es = build_es_client()
    if not es.ping():
        print("错误: 无法连接到 Elasticsearch", file=sys.stderr)
        sys.exit(1)
    print(f"ES 连接成功: {ES_HOSTS}")

    print(f"\nPipeline 参数:")
    print(f"  KNN:BM25 = {args.knn_weight:.2f}:{round(1-args.knn_weight,2):.2f}")
    print(f"  rerank vt={args.rerank_vt}, tk={args.rerank_tk}, threshold={args.threshold}")
    print(f"  top_n={args.top_n}, recall_at_Ks={RECALL_AT_KS}\n")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    results_file = os.path.join(RESULTS_DIR, f"run_{ts}.json")

    per_case = []
    t0 = time.time()
    for i, case in enumerate(test_cases):
        if (i + 1) % 20 == 0:
            elapsed = time.time() - t0
            eta = elapsed / (i + 1) * (len(test_cases) - i - 1)
            print(f"  进度: {i+1}/{len(test_cases)}  用时 {elapsed:.0f}s  预计剩余 {eta:.0f}s",
                  flush=True)
        answer_tokens = tokenize(case["reference_answer"])
        result = evaluate_single(
            es, case, answer_tokens, args.kb_id,
            args.knn_weight, args.top_retrieval,
            args.rerank_vt, args.rerank_tk, args.threshold, args.top_n,
        )
        per_case.append(result)

    summary = compute_summary(per_case, args.top_n)

    output = {
        "run_at": ts,
        "config": {
            "knn_weight": args.knn_weight,
            "bm25_weight": round(1 - args.knn_weight, 4),
            "rerank_vt_weight": args.rerank_vt,
            "rerank_tk_weight": args.rerank_tk,
            "similarity_threshold": args.threshold,
            "top_n": args.top_n,
            "top_k_retrieval": args.top_retrieval,
            "hit_threshold": TOKEN_OVERLAP_THRESHOLD,
            "es_index": ES_INDEX,
            "kb_id": args.kb_id,
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
