#!/usr/bin/env python3
"""
Import gzipped NDJSON (produced by embed_to_file.py) into local Elasticsearch.

Usage:
  python scripts/local_import.py [--file /path/to/output.ndjson.gz]
"""
import argparse
import gzip
import json
import time
from pathlib import Path

ES_URL   = "http://localhost:1200"
ES_USER  = "elastic"
ES_PASS  = "infini_rag_flow"
TENANT_ID = "1bec4a0a431311f194bf790f7f50c844"
INDEX_NAME = f"rag-medqa_{TENANT_ID}"
CHUNK_SIZE = 500   # docs per HTTP bulk call
CKPT_FILE  = "/tmp/local_import_ckpt.json"

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


def load_checkpoint():
    p = Path(CKPT_FILE)
    return json.loads(p.read_text()).get("offset", 0) if p.exists() else 0


def save_checkpoint(offset: int):
    Path(CKPT_FILE).write_text(json.dumps({"offset": offset}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default="output.ndjson.gz")
    args = parser.parse_args()

    from elasticsearch import Elasticsearch
    from elasticsearch.helpers import bulk

    es = Elasticsearch(ES_URL, basic_auth=(ES_USER, ES_PASS),
                       verify_certs=False, request_timeout=120)
    print(f"ES connected: {es.info()['version']['number']}")

    if not es.indices.exists(index=INDEX_NAME):
        es.indices.create(index=INDEX_NAME, body=INDEX_MAPPING)
        print(f"Created index: {INDEX_NAME}")
    else:
        print(f"Index exists: {INDEX_NAME}")

    start_offset = load_checkpoint()
    if start_offset > 0:
        print(f"Resuming from line {start_offset:,}")

    batch = []
    offset = 0
    docs_written = 0
    t0 = time.time()

    with gzip.open(args.file, "rt", encoding="utf-8") as f:
        for line in f:
            offset += 1
            if offset <= start_offset:
                continue
            line = line.strip()
            if not line:
                continue
            doc = json.loads(line)
            action = {"_index": INDEX_NAME, "_id": doc["id"]}
            batch.append({**action, **doc})

            if len(batch) >= CHUNK_SIZE:
                ok, _ = bulk(es, batch, raise_on_error=False, chunk_size=CHUNK_SIZE)
                docs_written += ok
                save_checkpoint(offset)
                elapsed = time.time() - t0
                speed = docs_written / elapsed if elapsed > 0 else 0
                print(f"  line={offset:,}  written={docs_written:,}  {speed:.0f} docs/s")
                batch = []

    if batch:
        ok, _ = bulk(es, batch, raise_on_error=False, chunk_size=CHUNK_SIZE)
        docs_written += ok
        save_checkpoint(offset)
        print(f"  line={offset:,}  written={docs_written:,}  (final)")

    elapsed = time.time() - t0
    print(f"\nDone! {docs_written:,} docs in {elapsed:.1f}s")
    Path(CKPT_FILE).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
