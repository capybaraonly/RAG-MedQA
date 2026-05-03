"""
运行离线检索评测：读取 eval_dataset.jsonl，直连 ES 检索，用 token overlap 判定命中，输出指标。

输出：evaluation/results/run_YYYYMMDD_HHMMSS.json
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Optional

# 确保能 import config
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

# 尽可能加载 jieba 分词
try:
    import jieba
    _has_jieba = True
except ImportError:
    _has_jieba = False


# ── 分词 ────────────────────────────────────────────────────────────────
def tokenize(text: str) -> set[str]:
    """中文用 jieba 分词 + 字粒度回退，英文按空白分词"""
    if _has_jieba:
        tokens = jieba.lcut(text)
    else:
        tokens = list(text)
    # 过滤空白和单字（保留中文字单字也可能是有效的，这里只减空白标点）
    result = set()
    for t in tokens:
        t = t.strip()
        if t and not all(c in "，。！？、；：""''（）【】《》…—·,.;:!?()[]{}" for c in t):
            result.add(t)
    return result


# ── Token Overlap F1 ────────────────────────────────────────────────────
def token_f1(chunk_tokens: set[str], answer_tokens: set[str]) -> float:
    if not chunk_tokens or not answer_tokens:
        return 0.0
    intersection = chunk_tokens & answer_tokens
    precision = len(intersection) / len(chunk_tokens)
    recall = len(intersection) / len(answer_tokens)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


# ── ES 连接 ─────────────────────────────────────────────────────────────
def build_es_client() -> Elasticsearch:
    hosts = [h.strip() for h in ES_HOSTS.split(",")]
    if ES_USERNAME and ES_PASSWORD:
        return Elasticsearch(hosts, basic_auth=(ES_USERNAME, ES_PASSWORD), verify_certs=False, timeout=60)
    return Elasticsearch(hosts, verify_certs=False, timeout=60)


# ── ES 检索 ─────────────────────────────────────────────────────────────
def search_es(es: Elasticsearch, question: str, top_k: int = TOP_K) -> list[dict]:
    """
    用 multi_match 检索 ES，返回 top_k chunks 列表。
    每个元素包含 chunk_id 和 content。
    """
    query_body = {
        "query": {
            "multi_match": {
                "query": question,
                "fields": ["content_with_weight", "question_kwd"],
            }
        },
        "size": top_k,
    }

    try:
        response = es.search(index=ES_INDEX, body=query_body, request_timeout=30)
    except Exception as e:
        print(f"  ES search error: {e}", file=sys.stderr)
        return []

    hits = response.get("hits", {}).get("hits", [])
    results = []
    for hit in hits:
        source = hit.get("_source", {})
        results.append({
            "chunk_id": hit.get("_id", ""),
            "content": source.get("content_with_weight", ""),
        })
    return results


# ── 单条评测 ────────────────────────────────────────────────────────────
def evaluate_single(
    es: Elasticsearch,
    case: dict,
    answer_tokens: set[str],
    top_k: int = TOP_K,
) -> dict:
    question = case["question"]
    chunks = search_es(es, question, top_k=top_k)

    hit = False
    first_hit_rank: Optional[int] = None

    for rank, chunk in enumerate(chunks, 1):
        chunk_content = chunk.get("content", "")
        if not chunk_content:
            continue
        chunk_tokens = tokenize(chunk_content)
        f1 = token_f1(chunk_tokens, answer_tokens)
        if f1 >= TOKEN_OVERLAP_THRESHOLD:
            hit = True
            if first_hit_rank is None:
                first_hit_rank = rank
            break

    return {
        "id": case["id"],
        "question": question[:200],
        "hit": hit,
        "first_hit_rank": first_hit_rank,
        "top_chunks": [c["chunk_id"] for c in chunks],
    }


# ── 指标汇总 ────────────────────────────────────────────────────────────
def compute_summary(results: list[dict]) -> dict:
    total = len(results)
    if total == 0:
        return {}

    hit_count = sum(1 for r in results if r["hit"])
    mrr_sum = 0.0
    recall_at = {1: 0, 3: 0, 5: 0, 10: 0}

    for r in results:
        if r["hit"] and r["first_hit_rank"] is not None:
            mrr_sum += 1.0 / r["first_hit_rank"]
            for k in recall_at:
                if r["first_hit_rank"] <= k:
                    recall_at[k] += 1

    return {
        "total": total,
        "hit_rate": hit_count / total,
        "recall_at_1": recall_at[1] / total,
        "recall_at_3": recall_at[3] / total,
        "recall_at_5": recall_at[5] / total,
        "recall_at_10": recall_at[10] / total,
        "mrr": mrr_sum / total,
    }


# ── 主入口 ──────────────────────────────────────────────────────────────
def main():
    # 检查评测集是否存在
    if not os.path.exists(DATASET_FILE):
        print(f"错误: 评测集文件不存在: {DATASET_FILE}", file=sys.stderr)
        print("请先运行: python evaluation/build_dataset.py", file=sys.stderr)
        sys.exit(1)

    # 加载评测集
    test_cases = []
    with open(DATASET_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                test_cases.append(json.loads(line))

    print(f"加载评测集: {len(test_cases)} 条")

    # 连接 ES
    print(f"连接 ES: {ES_HOSTS}, index={ES_INDEX}")
    es = build_es_client()
    if not es.ping():
        print("错误: 无法连接到 Elasticsearch", file=sys.stderr)
        sys.exit(1)
    print("ES 连接成功")

    # 逐条评测
    os.makedirs(RESULTS_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    results_file = os.path.join(RESULTS_DIR, f"run_{ts}.json")

    per_case = []
    for i, case in enumerate(test_cases):
        if (i + 1) % 20 == 0:
            print(f"  进度: {i + 1}/{len(test_cases)}")
        answer_tokens = tokenize(case["reference_answer"])
        result = evaluate_single(es, case, answer_tokens)
        per_case.append(result)

    summary = compute_summary(per_case)

    # 输出
    output = {
        "run_at": ts,
        "config": {
            "K": TOP_K,
            "threshold": TOKEN_OVERLAP_THRESHOLD,
            "es_index": ES_INDEX,
            "es_hosts": ES_HOSTS,
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
