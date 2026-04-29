#!/usr/bin/env python3
"""
本地 BGE-M3 嵌入服务（开发/测试用），暴露 OpenAI-compatible /v1/embeddings 接口。
默认监听 0.0.0.0:6380。
用法: python scripts/mini_emb_server.py
"""

import logging
import sys
from pathlib import Path

import numpy as np
from flask import Flask, jsonify, request

app = Flask(__name__)
_model = None


def _get_model():
    global _model
    if _model is None:
        logging.info("Loading BAAI/bge-m3 …")
        try:
            from FlagEmbedding import FlagModel
            _model = FlagModel("BAAI/bge-m3", use_fp16=True)
            logging.info("FlagModel loaded")
        except Exception as e:
            logging.warning("FlagModel failed (%s), falling back to sentence-transformers", e)
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer("BAAI/bge-m3")
    return _model


@app.route("/v1/embeddings", methods=["POST"])
def embeddings():
    data = request.get_json(force=True)
    texts = data.get("input", [])
    if isinstance(texts, str):
        texts = [texts]

    model = _get_model()
    try:
        vecs = model.encode(texts)
    except AttributeError:
        # sentence-transformers API
        vecs = model.encode(texts, normalize_embeddings=True)

    vecs = np.array(vecs)
    token_count = sum(len(t.split()) for t in texts)

    return jsonify({
        "object": "list",
        "data": [
            {"object": "embedding", "embedding": vecs[i].tolist(), "index": i}
            for i in range(len(texts))
        ],
        "model": "bge-m3",
        "usage": {"prompt_tokens": token_count, "total_tokens": token_count},
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=6380)
    ap.add_argument("--host", default="0.0.0.0")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    print(f"Starting mini embedding server on {args.host}:{args.port}")
    _get_model()  # preload
    app.run(host=args.host, port=args.port, threaded=True)
