#!/usr/bin/env python3
"""
GPU embedding script — writes output to gzipped NDJSON file on remote disk.
No ES connection needed. After this finishes, run local_import.py to load into ES.

Usage on remote GPU server:
  python embed_to_file.py

Then on local machine:
  scp -P 13615 root@connect.nmb1.seetacloud.com:/root/autodl-tmp/output.ndjson.gz .
  python scripts/local_import.py
"""
import gzip
import json
import os
import sys
import uuid
import time
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────────
MODEL_PATH  = os.getenv("MODEL_PATH",  "/root/autodl-tmp/bge-m3")
DATA_FILE   = os.getenv("DATA_FILE",   "/root/autodl-tmp/train_zh_0.json")
OUTPUT_FILE = os.getenv("OUTPUT_FILE", "/root/autodl-tmp/output.ndjson.gz")
CKPT_FILE   = os.getenv("CKPT_FILE",  "/root/autodl-tmp/embed_file_ckpt.json")
GPU_BATCH   = int(os.getenv("GPU_BATCH", "1024"))   # items per GPU call

# Fixed knowledge base metadata
TENANT_ID  = "1bec4a0a431311f194bf790f7f50c844"
KB_ID      = "c277d0072a2a476795de09b797164c0e"


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


def make_doc(q: str, a: str, vec) -> dict:
    return {
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
        # Convert to float32 for smaller output
        "q_1024_vec": [round(float(x), 6) for x in vec],
    }


def main():
    import numpy as np
    print("Loading FlagEmbedding …")
    from FlagEmbedding import BGEM3FlagModel

    print(f"Loading model {MODEL_PATH} on GPU …")
    model = BGEM3FlagModel(MODEL_PATH, use_fp16=True)
    print("Model loaded.")

    print(f"Counting lines in {DATA_FILE} …")
    total = count_lines(DATA_FILE)
    print(f"Total raw lines: {total:,}")

    start_offset = load_checkpoint()
    if start_offset > 0:
        print(f"Resuming from offset {start_offset:,}")

    # Open output file in append mode (for resume)
    mode = "ab" if start_offset > 0 else "wb"
    offset = start_offset
    t0 = time.time()
    docs_written = 0

    batch_q, batch_a = [], []

    def flush(qs, as_):
        nonlocal docs_written
        result = model.encode(
            qs, batch_size=256, max_length=512,
            return_dense=True, return_sparse=False, return_colbert_vecs=False,
        )
        vecs = result["dense_vecs"]
        for q, a, v in zip(qs, as_, vecs):
            doc = make_doc(q, a, v)
            line = json.dumps(doc, ensure_ascii=False) + "\n"
            gz_out.write(line.encode("utf-8"))
            docs_written += 1

    with gzip.open(OUTPUT_FILE, mode) as gz_out:
        for q, a in iter_qa(DATA_FILE, skip=start_offset):
            batch_q.append(q)
            batch_a.append(a)

            if len(batch_q) >= GPU_BATCH:
                flush(batch_q, batch_a)
                offset += len(batch_q)
                save_checkpoint(offset)
                elapsed = time.time() - t0
                speed = (offset - start_offset) / elapsed if elapsed > 0 else 0
                pct = offset / total * 100
                eta_min = (total - offset) / speed / 60 if speed > 0 else 0
                print(
                    f"  offset={offset:,}/{total:,} ({pct:.1f}%)  "
                    f"speed={speed:.0f} pairs/s  ETA={eta_min:.1f}min"
                )
                batch_q, batch_a = [], []

        # flush remaining
        if batch_q:
            flush(batch_q, batch_a)
            offset += len(batch_q)
            save_checkpoint(offset)
            print(f"  offset={offset:,}/{total:,} (100%)  DONE")

    elapsed = time.time() - t0
    out_size = Path(OUTPUT_FILE).stat().st_size / 1024 / 1024
    print(f"\nFinished! {docs_written:,} docs in {elapsed:.1f}s  ({docs_written/elapsed:.0f} pairs/s)")
    print(f"Output: {OUTPUT_FILE}  ({out_size:.1f} MB)")
    Path(CKPT_FILE).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
