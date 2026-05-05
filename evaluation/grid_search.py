"""
网格搜索：扫描混合检索比例、重排序权重、top_n、相似度阈值对检索指标的影响。

效率设计：
  - 外层：每个 knn_weight 跑一次 ES 查询（200 条 × N 组 knn_weight）
  - 内层：rerank_vt、top_n、threshold 全部离线枚举（numpy，毫秒级）
  - 中间结果缓存到 evaluation/cache/，避免重复 ES 调用

用法：
  python evaluation/grid_search.py                  # 使用默认网格
  python evaluation/grid_search.py --knn 0.8 0.95  # 只扫这两个 knn 值
  python evaluation/grid_search.py --top-n 5 6 8   # 只扫这几个 top_n

输出：
  evaluation/results/grid_YYYYMMDD_HHMMSS.json      # 完整结果
  控制台打印热图式汇总表
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from itertools import product

import numpy as np
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (
    ES_HOSTS, ES_USERNAME, ES_PASSWORD, ES_INDEX,
    DATASET_FILE, RESULTS_DIR, TOKEN_OVERLAP_THRESHOLD,
)
from run_eval import (
    build_es_client, get_embedding, search_hybrid,
    tokenize, tokenize_list, token_f1, token_overlap, cosine_sim,
)

from elasticsearch import Elasticsearch

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")

# ── 默认网格 ──────────────────────────────────────────────────────────────────
DEFAULT_KNN_WEIGHTS   = [0.0, 0.5, 0.7, 0.9, 0.95, 1.0]
DEFAULT_RERANK_VT     = [0.0, 0.3, 0.5, 0.7, 1.0]   # vt_weight; tk = 1 - vt
DEFAULT_TOP_NS        = [3, 5, 6, 10]
DEFAULT_THRESHOLDS    = [0.0, 0.1, 0.2]
RECALL_AT_KS          = [1, 3, 5, 10]
DEFAULT_KB_ID         = "c277d0072a2a476795de09b797164c0e"
DEFAULT_TOP_RETRIEVAL = 1024
EMB_URL = os.environ.get("EVAL_EMB_URL", "http://localhost:6380/v1/embeddings")
EMB_MODEL = os.environ.get("EVAL_EMB_MODEL", "bge-m3")


# ── 缓存 key（基于 knn_weight + 数据集） ──────────────────────────────────────
def cache_path(knn_weight: float) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"hits_knn{knn_weight:.2f}.json")


def load_cache(knn_weight: float) -> list[dict] | None:
    p = cache_path(knn_weight)
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return None


def save_cache(knn_weight: float, data: list[dict]):
    with open(cache_path(knn_weight), "w") as f:
        json.dump(data, f, ensure_ascii=False)


# ── ES 检索并缓存每条 case 的原始 hits ────────────────────────────────────────
def fetch_all_hits(es: Elasticsearch, test_cases: list[dict],
                   knn_weight: float, kb_id: str,
                   top_retrieval: int) -> list[dict]:
    cached = load_cache(knn_weight)
    if cached is not None:
        print(f"  [cache hit] knn_weight={knn_weight}")
        return cached

    print(f"  [ES query ] knn_weight={knn_weight}  ({len(test_cases)} cases)", flush=True)
    results = []
    t0 = time.time()
    for i, case in enumerate(test_cases):
        if (i + 1) % 40 == 0:
            print(f"    {i+1}/{len(test_cases)}  {time.time()-t0:.0f}s", flush=True)
        try:
            query_vec = get_embedding(case["question"])
        except Exception as e:
            print(f"    embedding error: {e}", file=sys.stderr)
            query_vec = []

        hits = search_hybrid(es, case["question"], query_vec, kb_id,
                             knn_weight, top_retrieval) if query_vec else []
        query_tks = tokenize_list(case["question"])
        results.append({
            "id": case["id"],
            "question": case["question"][:200],
            "reference_answer": case["reference_answer"],
            "query_vec": query_vec,
            "query_tks": query_tks,
            "hits": hits,
        })

    save_cache(knn_weight, results)
    print(f"  [cached   ] knn_weight={knn_weight}  total {time.time()-t0:.0f}s")
    return results


# ── 离线重排序 + 指标计算（纯 numpy，无网络） ──────────────────────────────────
def eval_offline(cases_with_hits: list[dict],
                 vt_weight: float, tk_weight: float,
                 threshold: float, top_n: int) -> dict:
    mrr_sum = 0.0
    recall_at = {k: 0 for k in RECALL_AT_KS}
    hit_at_top_n = 0
    max_k = max(top_n, max(RECALL_AT_KS))

    for c in cases_with_hits:
        hits = c["hits"]
        if not hits:
            continue
        query_vec = c["query_vec"]
        query_tks = c["query_tks"]
        answer_tokens = tokenize(c["reference_answer"])

        # 重排序
        scored = []
        for h in hits:
            vt = cosine_sim(query_vec, h["vec"]) if h["vec"] else 0.0
            tk = token_overlap(query_tks, h["content_ltks"].split())
            sim = vt_weight * vt + tk_weight * tk
            scored.append((sim, h))
        scored.sort(key=lambda x: x[0], reverse=True)
        reranked = [(sim, h) for sim, h in scored if sim >= threshold][:max_k]

        # 命中判定
        first_hit_rank = None
        for rank, (sim, chunk) in enumerate(reranked, 1):
            if token_f1(tokenize(chunk["content"]), answer_tokens) >= TOKEN_OVERLAP_THRESHOLD:
                first_hit_rank = rank
                break

        if first_hit_rank is not None:
            mrr_sum += 1.0 / first_hit_rank
            for k in recall_at:
                if first_hit_rank <= k:
                    recall_at[k] += 1
            if first_hit_rank <= top_n:
                hit_at_top_n += 1

    total = len(cases_with_hits)
    result = {
        f"hit_rate@{top_n}": round(hit_at_top_n / total, 4),
        "mrr": round(mrr_sum / total, 4),
    }
    for k in sorted(recall_at):
        result[f"R@{k}"] = round(recall_at[k] / total, 4)
    return result


# ── 打印汇总表 ────────────────────────────────────────────────────────────────
def print_table(rows: list[dict], top_n: int):
    header = f"{'knn_w':>6} {'vt_w':>5} {'tk_w':>5} {'thr':>5} {'top_n':>6} │ "
    header += "  ".join(f"R@{k:<2}" for k in RECALL_AT_KS)
    header += f"  {'MRR':>6}  hit_rate"
    print("\n" + header)
    print("─" * len(header))
    for r in rows:
        cfg = r["config"]
        m = r["metrics"]
        line = (f"{cfg['knn_weight']:>6.2f} {cfg['vt_weight']:>5.2f} {cfg['tk_weight']:>5.2f} "
                f"{cfg['threshold']:>5.2f} {cfg['top_n']:>6} │ ")
        line += "  ".join(f"{m.get(f'R@{k}', 0):.3f}" for k in RECALL_AT_KS)
        line += f"  {m['mrr']:>6.4f}  {m.get(f'hit_rate@{cfg[\"top_n\"]}', 0):.4f}"
        print(line)


# ── 主入口 ────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="RAG-MedQA 网格搜索")
    parser.add_argument("--knn", type=float, nargs="+", default=DEFAULT_KNN_WEIGHTS,
                        metavar="W", help="KNN 权重列表")
    parser.add_argument("--vt", type=float, nargs="+", default=DEFAULT_RERANK_VT,
                        metavar="W", help="重排向量权重列表（tk=1-vt）")
    parser.add_argument("--top-n", type=int, nargs="+", default=DEFAULT_TOP_NS,
                        metavar="N", help="top-N 列表")
    parser.add_argument("--threshold", type=float, nargs="+", default=DEFAULT_THRESHOLDS,
                        metavar="T", help="similarity_threshold 列表")
    parser.add_argument("--top-retrieval", type=int, default=DEFAULT_TOP_RETRIEVAL)
    parser.add_argument("--kb-id", type=str, default=DEFAULT_KB_ID)
    parser.add_argument("--no-cache", action="store_true", help="忽略缓存，强制重新查询")
    args = parser.parse_args()

    if args.no_cache:
        import shutil
        if os.path.exists(CACHE_DIR):
            shutil.rmtree(CACHE_DIR)
        print("已清除缓存")

    if not os.path.exists(DATASET_FILE):
        print(f"错误: 评测集不存在: {DATASET_FILE}", file=sys.stderr)
        sys.exit(1)
    test_cases = []
    with open(DATASET_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                test_cases.append(json.loads(line))
    print(f"评测集: {len(test_cases)} 条")

    try:
        get_embedding("test")
        print(f"Embedding 服务: {EMB_URL} ✓")
    except Exception as e:
        print(f"Embedding 服务不可用: {e}", file=sys.stderr)
        sys.exit(1)

    es = build_es_client()
    if not es.ping():
        print("Elasticsearch 不可用", file=sys.stderr)
        sys.exit(1)
    print(f"ES: {ES_HOSTS} ✓")

    grid = list(product(args.knn, args.vt, args.top_n, args.threshold))
    knn_unique = sorted(set(args.knn))
    print(f"\n网格规模: knn×{len(args.knn)} × vt×{len(args.vt)} × top_n×{len(args.top_n)} "
          f"× thr×{len(args.threshold)} = {len(grid)} 组")
    print(f"ES 查询批次: {len(knn_unique)}（每批 {len(test_cases)} 条，其余离线）\n")

    # 外层：按 knn_weight 批次做 ES 查询（带缓存）
    hits_by_knn: dict[float, list[dict]] = {}
    for knn_w in knn_unique:
        hits_by_knn[knn_w] = fetch_all_hits(es, test_cases, knn_w, args.kb_id, args.top_retrieval)

    # 内层：离线枚举所有参数组合
    print(f"\n开始离线网格枚举 ({len(grid)} 组)...", flush=True)
    all_rows = []
    for knn_w, vt_w, top_n, thr in grid:
        tk_w = round(1.0 - vt_w, 4)
        metrics = eval_offline(hits_by_knn[knn_w], vt_w, tk_w, thr, top_n)
        all_rows.append({
            "config": {
                "knn_weight": knn_w,
                "bm25_weight": round(1 - knn_w, 4),
                "vt_weight": vt_w,
                "tk_weight": tk_w,
                "threshold": thr,
                "top_n": top_n,
            },
            "metrics": metrics,
        })

    # 按 MRR 排序
    all_rows.sort(key=lambda x: (x["metrics"]["mrr"], x["metrics"].get(f"R@{max(RECALL_AT_KS)}", 0)),
                  reverse=True)

    # 打印 top-20
    print(f"\n─── Top-20 参数组合（按 MRR 降序）───")
    print_table(all_rows[:20], args.top_n[0])

    # 保存完整结果
    os.makedirs(RESULTS_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_file = os.path.join(RESULTS_DIR, f"grid_{ts}.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({
            "run_at": ts,
            "grid_axes": {
                "knn_weights": args.knn,
                "vt_weights": args.vt,
                "top_ns": args.top_n,
                "thresholds": args.threshold,
            },
            "results": all_rows,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n✓ 完整结果: {out_file}")

    # 找最优（对每个 top_n 单独显示）
    print("\n─── 各 top_n 最优参数 ───")
    for tn in sorted(set(args.top_n)):
        best = max(
            (r for r in all_rows if r["config"]["top_n"] == tn),
            key=lambda x: x["metrics"]["mrr"],
        )
        c, m = best["config"], best["metrics"]
        r_at = ", ".join(f"R@{k}={m.get(f'R@{k}',0):.3f}" for k in RECALL_AT_KS)
        print(f"  top_n={tn}: knn={c['knn_weight']}, vt={c['vt_weight']}, "
              f"thr={c['threshold']} → MRR={m['mrr']:.4f}, {r_at}")


if __name__ == "__main__":
    main()
