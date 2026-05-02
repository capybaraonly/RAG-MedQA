#!/usr/bin/env python3
"""
Standalone GPU embedding script for RAG-MedQA knowledge base ingestion.

Run on remote GPU server with SSH reverse tunnel to local ES:
  ssh -p 13615 -R 1200:localhost:1200 root@connect.nmb1.seetacloud.com
  python embed_to_es.py

Configuration via environment variables or defaults below.
"""
import json
import os
import sys
import uuid
import time
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────────
ES_URL      = os.getenv("ES_URL",      "http://localhost:1200")
ES_USER     = os.getenv("ES_USER",     "elastic")
ES_PASS     = os.getenv("ES_PASS",     "infini_rag_flow")
TENANT_ID   = os.getenv("TENANT_ID",  "1bec4a0a431311f194bf790f7f50c844")
KB_ID       = os.getenv("KB_ID",      "c277d0072a2a476795de09b797164c0e")
INDEX_NAME  = f"rag-medqa_{TENANT_ID}"
MODEL_NAME  = os.getenv("MODEL_NAME", "/root/autodl-tmp/bge-m3")
DATA_FILE   = os.getenv("DATA_FILE",  "/root/autodl-tmp/train_zh_0.json")
CKPT_FILE   = os.getenv("CKPT_FILE",  "/root/autodl-tmp/embed_ckpt.json")
BATCH_SIZE  = int(os.getenv("BATCH_SIZE", "512"))
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "1"))

# ── Index mapping (created once if absent) ──────────────────────────────────
INDEX_MAPPING = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "dynamic_templates": [
            {
                "vec_1024": {
                    "match": "*_1024_vec",
                    "mapping": {
                        "type": "dense_vector",
                        "dims": 1024,
                        "index": True,
                        "similarity": "cosine",
                    },
                }
            }
        ],
        "properties": {
            "id":                  {"type": "keyword"},
            "doc_id":              {"type": "keyword"},
            "kb_id":               {"type": "keyword"},
            "tenant_id":           {"type": "keyword"},
            "docnm_kwd":           {"type": "keyword"},
            "content_with_weight": {"type": "text", "analyzer": "standard"},
            "content_ltks":        {"type": "text", "analyzer": "standard"},
            "content_sm_ltks":     {"type": "text", "analyzer": "standard"},
            "important_kwd":       {"type": "keyword"},
            "image_id":            {"type": "keyword"},
            "create_time":         {"type": "long"},
        },
    },
}


def ensure_index(es):
    if not es.indices.exists(index=INDEX_NAME):
        es.indices.create(index=INDEX_NAME, body=INDEX_MAPPING)
        print(f"Created index: {INDEX_NAME}")
    else:
        print(f"Index already exists: {INDEX_NAME}")


def load_checkpoint():
    if Path(CKPT_FILE).exists():
        return json.loads(Path(CKPT_FILE).read_text()).get("offset", 0)
    return 0


def save_checkpoint(offset: int):
    Path(CKPT_FILE).write_text(json.dumps({"offset": offset}))


def count_lines(path: str) -> int:
    n = 0
    with open(path, "rb") as f:
        for _ in f:
            n += 1
    return n


def iter_qa(path: str, skip: int = 0):
    """Yield (question, answer) skipping the first `skip` valid pairs."""
    seen = 0
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                item = json.loads(raw)
            except json.JSONDecodeError:
                continue
            q = item.get("instruction", "").strip()
            a = item.get("output", "").strip()
            if not q or not a:
                continue
            if seen < skip:
                seen += 1
                continue
            yield q, a
            seen += 1


def make_doc(q: str, a: str, vec: list) -> dict:
    return {
        "_index": INDEX_NAME,
        "_id": uuid.uuid4().hex,
        "id": uuid.uuid4().hex,
        "doc_id": "medical_qa_corpus",
        "kb_id": KB_ID,
        "tenant_id": TENANT_ID,
        "docnm_kwd": "医疗问答",
        "content_with_weight": f"问题：{q}\t回答：{a}",
        "content_ltks": q,
        "content_sm_ltks": q,
        "important_kwd": [],
        "image_id": "",
        "create_time": int(time.time() * 1000),
        "q_1024_vec": vec,
    }


def main():
    # ── Imports ──
    print("Loading FlagEmbedding …")
    from FlagEmbedding import BGEM3FlagModel
    print("Loading elasticsearch …")
    from elasticsearch import Elasticsearch
    from elasticsearch.helpers import bulk

    # ── Connect ES ──
    es = Elasticsearch(ES_URL, basic_auth=(ES_USER, ES_PASS), verify_certs=False,
                       request_timeout=120)
    info = es.info()
    print(f"ES connected: {info['version']['number']}")
    ensure_index(es)

    # ── Load model ──
    print(f"Loading model {MODEL_NAME} on GPU …")
    model = BGEM3FlagModel(MODEL_NAME, use_fp16=True)
    print("Model loaded.")

    # ── Count total lines ──
    print(f"Counting lines in {DATA_FILE} …")
    total = count_lines(DATA_FILE)
    print(f"Total raw lines: {total:,}")

    # ── Checkpoint ──
    start_offset = load_checkpoint()
    if start_offset > 0:
        print(f"Resuming from offset {start_offset:,}")

    offset = start_offset
    batch_q, batch_a = [], []
    t0 = time.time()
    docs_written = 0

    def flush(qs, as_):
        nonlocal docs_written
        # Use fixed GPU batch_size=256 for optimal 4090 throughput
        result = model.encode(qs, batch_size=256, max_length=512,
                              return_dense=True, return_sparse=False, return_colbert_vecs=False)
        vecs = result["dense_vecs"]
        actions = [make_doc(q, a, v.tolist()) for q, a, v in zip(qs, as_, vecs)]
        # Bulk insert with reasonable chunk size to avoid large payloads over tunnel
        ok, _ = bulk(es, actions, raise_on_error=False, chunk_size=256, request_timeout=120)
        docs_written += ok

    for q, a in iter_qa(DATA_FILE, skip=start_offset):
        batch_q.append(q)
        batch_a.append(a)

        if len(batch_q) >= BATCH_SIZE:
            flush(batch_q, batch_a)
            offset += len(batch_q)
            save_checkpoint(offset)
            elapsed = time.time() - t0
            speed = (offset - start_offset) / elapsed if elapsed > 0 else 0
            print(f"  offset={offset:,}  written={docs_written:,}  speed={speed:.0f} pairs/s")
            batch_q, batch_a = [], []

    # remaining
    if batch_q:
        flush(batch_q, batch_a)
        offset += len(batch_q)
        save_checkpoint(offset)
        print(f"  offset={offset:,}  written={docs_written:,}  (final batch)")

    print(f"\nDone! Total written: {docs_written:,} docs in {time.time()-t0:.1f}s")
    # Remove checkpoint on success
    Path(CKPT_FILE).unlink(missing_ok=True)

    # Update KB stats in ES? (optional — the UI will show counts on next search)
    print(f"Index: {INDEX_NAME}, KB_ID: {KB_ID}")


if __name__ == "__main__":
    main()
