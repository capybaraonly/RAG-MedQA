#!/usr/bin/env python3
"""
构建医疗知识库脚本

用法示例:
  # 仅 QA 数据，限制 100 条（本地验证）
  python scripts/build_medical_kb.py --tenant-id <id> --qa-limit 100

  # 全量 QA + PDF（GPU 机器建议 --batch-size 256）
  python scripts/build_medical_kb.py --tenant-id <id> --pdf-dir data/guidelines --batch-size 256

  # 中断后续传（重跑同一命令即可，断点会自动接续）
  python scripts/build_medical_kb.py --tenant-id <id> --qa-limit 100
"""

import json
import os
import sys
from pathlib import Path

# Bug fix: scripts/ 的上一级才是项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from common import settings
from common.settings import init_settings
from rag.nlp.search import index_name as search_index_name
from common.constants import LLMType

CHECKPOINT_DIR = PROJECT_ROOT / "data" / ".checkpoints"


# ---------------------------------------------------------------------------
# 断点续传：checkpoint 读写
# ---------------------------------------------------------------------------

def _ckpt_path(key: str) -> Path:
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    return CHECKPOINT_DIR / f"{key}.json"


def _load_ckpt(key: str) -> dict:
    p = _ckpt_path(key)
    return json.loads(p.read_text()) if p.exists() else {}


def _save_ckpt(key: str, data: dict):
    _ckpt_path(key).write_text(json.dumps(data, ensure_ascii=False, indent=2))


def _del_ckpt(key: str):
    _ckpt_path(key).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# 数据加载
# ---------------------------------------------------------------------------

def load_medical_qa_from_jsonl(jsonl_path: str) -> list[dict]:
    qa_pairs = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            q = item.get("instruction", "")
            a = item.get("output", "")
            if q and a:
                qa_pairs.append({"question": q, "answer": a})
    return qa_pairs


def load_medical_qa_from_dialogue_csv(csv_dir: str) -> list[dict]:
    import pandas as pd

    qa_pairs = []
    for csv_file in Path(csv_dir).glob("*.csv"):
        df = pd.read_csv(csv_file)
        for _, row in df.iterrows():
            qa_pairs.append({
                "question": str(row.get("question", "")),
                "answer": str(row.get("answer", "")),
            })
    return qa_pairs


# ---------------------------------------------------------------------------
# Chunk 构建
# ---------------------------------------------------------------------------

def _make_chunk(text: str, content_with_weight: str, doc_id: str,
                kb_id: str, tenant_id: str, docnm: str) -> dict:
    """生成一个 ES chunk，含全文检索字段和 tokenized 字段。"""
    from common.misc_utils import get_uuid
    from rag.nlp import rag_tokenizer

    content_ltks = rag_tokenizer.tokenize(text)
    return {
        "id": get_uuid(),
        "doc_id": doc_id,
        "kb_id": kb_id,
        "tenant_id": tenant_id,
        "content_ltks": content_ltks,
        "content_sm_ltks": rag_tokenizer.fine_grained_tokenize(content_ltks),
        "content_with_weight": content_with_weight,
        "docnm_kwd": docnm,
        "kb_name": "医疗知识库",
        "important_kwd": [],
        "image_id": "",
    }


def chunk_qa_pairs(qa_pairs: list[dict], tenant_id: str, kb_id: str) -> list[dict]:
    chunks = []
    for pair in qa_pairs:
        q, a = pair["question"], pair["answer"]
        chunk = _make_chunk(
            text=q,
            content_with_weight=f"问题：{q}\t回答：{a}",
            doc_id="medical_qa_corpus",
            kb_id=kb_id,
            tenant_id=tenant_id,
            docnm="医疗问答",
        )
        chunks.append(chunk)
    return chunks


def chunk_pdf_sections(sections, tables, pdf_path: str,
                       tenant_id: str, kb_id: str) -> list[dict]:
    docnm = Path(pdf_path).stem
    doc_id = f"pdf_{docnm}"
    chunks = []

    for text, _ in sections:
        text = text.strip()
        if len(text) < 10:
            continue
        chunks.append(_make_chunk(text, text, doc_id, kb_id, tenant_id, docnm))

    for (_, html_table), _ in tables:
        if not html_table:
            continue
        chunks.append(_make_chunk(html_table, html_table, doc_id, kb_id, tenant_id, docnm))

    return chunks


# ---------------------------------------------------------------------------
# 嵌入 + 写入 ES（断点续传）
# ---------------------------------------------------------------------------

def embed_and_index_chunks(
    chunks: list[dict],
    emb_model,
    tenant_id: str,
    kb_id: str,
    ckpt_key: str,
    batch_size: int = 32,
):
    idx_name = search_index_name(tenant_id)
    ckpt = _load_ckpt(ckpt_key)
    start = ckpt.get("offset", 0)
    total = len(chunks)

    if start >= total:
        print(f"  [{ckpt_key}] 已全部完成，跳过")
        return

    if start > 0:
        print(f"  [{ckpt_key}] 断点续传：从第 {start} 个 chunk 继续（共 {total}）")

    for i in range(start, total, batch_size):
        batch = chunks[i: i + batch_size]

        # Bug fix: encode() 返回 (embeddings, token_count) 元组，需要解包
        vectors, _ = emb_model.encode([c["content_ltks"] for c in batch])

        for j, chunk in enumerate(batch):
            chunk["q_1024_vec"] = vectors[j].tolist()

        settings.docStoreConn.insert(batch, idx_name, kb_id)

        new_offset = i + len(batch)
        _save_ckpt(ckpt_key, {"offset": new_offset})
        print(f"  [{ckpt_key}] {new_offset} / {total}")

    _del_ckpt(ckpt_key)
    print(f"  [{ckpt_key}] 完成，共 {total} chunks")


# ---------------------------------------------------------------------------
# QA 入库
# ---------------------------------------------------------------------------

def build_qa_knowledge_base(
    tenant_id: str,
    kb_id: str,
    qa_source: str,
    qa_data_path: str,
    qa_limit: int | None,
    batch_size: int,
):
    from api.db.services.llm_service import LLMBundle
    from api.db.joint_services.tenant_model_service import get_tenant_default_model_by_type

    print(f"[QA] 加载数据: {qa_data_path}")
    if qa_source == "shibing624/medical":
        qa_pairs = load_medical_qa_from_jsonl(qa_data_path)
    elif qa_source == "toyhom":
        qa_pairs = load_medical_qa_from_dialogue_csv(qa_data_path)
    else:
        raise ValueError(f"不支持的 qa_source: {qa_source}")

    if qa_limit:
        qa_pairs = qa_pairs[:qa_limit]
    print(f"[QA] 已加载 {len(qa_pairs)} 条 QA 对，开始生成 chunks...")

    chunks = chunk_qa_pairs(qa_pairs, tenant_id, kb_id)
    print(f"[QA] 已生成 {len(chunks)} 个 chunks，开始嵌入...")

    emb_cfg = get_tenant_default_model_by_type(LLMType.EMBEDDING)
    emb_model = LLMBundle(emb_cfg)
    embed_and_index_chunks(
        chunks, emb_model, tenant_id, kb_id,
        ckpt_key=f"{kb_id}_qa",
        batch_size=batch_size,
    )


# ---------------------------------------------------------------------------
# PDF 入库
# ---------------------------------------------------------------------------

def build_pdf_knowledge_base(
    tenant_id: str,
    kb_id: str,
    pdf_dir: str,
    batch_size: int,
    parse_method: str,
    mineru_api_url: str,
):
    from api.db.services.llm_service import LLMBundle
    from api.db.joint_services.tenant_model_service import get_tenant_default_model_by_type
    from parser.mineru_parser import MinerUPdfParser

    pdf_paths = sorted(Path(pdf_dir).glob("**/*.pdf"))
    if not pdf_paths:
        print(f"[PDF] {pdf_dir} 下未找到 PDF 文件，跳过")
        return

    print(f"[PDF] 发现 {len(pdf_paths)} 个 PDF 文件")

    parser = MinerUPdfParser(api_url=mineru_api_url)
    if not mineru_api_url and not parser.check_installation():
        print("[PDF] 警告: MinerU CLI 未安装，跳过 PDF 解析")
        print("       安装: pip install mineru")
        print("       或用 --mineru-api-url 指向运行中的 MinerU API 服务")
        return

    ckpt_key = f"{kb_id}_pdf"
    ckpt = _load_ckpt(ckpt_key)
    done_files: set[str] = set(ckpt.get("done_files", []))

    emb_cfg = get_tenant_default_model_by_type(LLMType.EMBEDDING)
    emb_model = LLMBundle(emb_cfg)

    for pdf_path in pdf_paths:
        fname = str(pdf_path)
        if fname in done_files:
            print(f"[PDF] 跳过（已完成）: {pdf_path.name}")
            continue

        print(f"[PDF] 解析: {pdf_path.name}")
        try:
            sections, tables = parser.parse_pdf(filepath=fname, parse_method=parse_method)
        except Exception as e:
            print(f"[PDF] 解析失败 {pdf_path.name}: {e}")
            continue

        print(f"[PDF]   → {len(sections)} sections，{len(tables)} tables")
        chunks = chunk_pdf_sections(sections, tables, fname, tenant_id, kb_id)
        if not chunks:
            print(f"[PDF]   → 无有效 chunks，跳过")
        else:
            embed_and_index_chunks(
                chunks, emb_model, tenant_id, kb_id,
                ckpt_key=f"{kb_id}_pdf_{pdf_path.stem}",
                batch_size=batch_size,
            )

        done_files.add(fname)
        _save_ckpt(ckpt_key, {"done_files": list(done_files)})

    _del_ckpt(ckpt_key)
    print("[PDF] 全部 PDF 处理完毕")


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def build_knowledge_base(
    tenant_id: str,
    kb_name: str = "医疗知识库",
    qa_source: str = "shibing624/medical",
    qa_data_path: str = "data/medical/finetune/train_zh_0.json",
    qa_limit: int | None = None,
    pdf_dir: str | None = None,
    batch_size: int = 32,
    mineru_api_url: str = "",
    parse_method: str = "auto",
):
    from api.db.db_models import init_database_tables
    from api.db.services.knowledgebase_service import KnowledgebaseService
    from common.misc_utils import get_uuid

    init_settings()
    init_database_tables()

    print(f"=== 构建知识库: {kb_name} ===")

    # 断点续传：复用同名知识库
    ckpt_key = f"global_{tenant_id}_{kb_name}"
    ckpt = _load_ckpt(ckpt_key)
    if ckpt.get("kb_id"):
        kb_id = ckpt["kb_id"]
        print(f"  续传已有知识库: {kb_id}")
    else:
        kb_id = get_uuid()
        KnowledgebaseService.save(
            id=kb_id,
            tenant_id=tenant_id,
            name=kb_name,
            description="中文医疗知识库 - 包含临床问答和诊疗指南",
            embd_id="BAAI/bge-m3",
            parser_id="qa",
            parser_config={},
            permission="me",
        )
        _save_ckpt(ckpt_key, {"kb_id": kb_id})
        print(f"  知识库已创建: {kb_id}")

    build_qa_knowledge_base(
        tenant_id=tenant_id,
        kb_id=kb_id,
        qa_source=qa_source,
        qa_data_path=qa_data_path,
        qa_limit=qa_limit,
        batch_size=batch_size,
    )

    if pdf_dir:
        build_pdf_knowledge_base(
            tenant_id=tenant_id,
            kb_id=kb_id,
            pdf_dir=pdf_dir,
            batch_size=batch_size,
            parse_method=parse_method,
            mineru_api_url=mineru_api_url,
        )

    print(f"=== 完成! 知识库 ID: {kb_id} ===")
    return kb_id


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="构建医疗知识库")
    ap.add_argument("--tenant-id", required=True, help="租户 ID")
    ap.add_argument("--kb-name", default="医疗知识库")
    ap.add_argument(
        "--qa-source",
        default="shibing624/medical",
        choices=["shibing624/medical", "toyhom"],
    )
    ap.add_argument(
        "--qa-data-path",
        default="data/medical/finetune/train_zh_0.json",
        help="相对于项目根目录的路径",
    )
    ap.add_argument("--qa-limit", type=int, default=None,
                    help="限制 QA 条数（测试用，如 --qa-limit 100）")
    ap.add_argument("--pdf-dir", default=None,
                    help="临床指南 PDF 所在目录")
    ap.add_argument("--parse-method", default="auto",
                    choices=["auto", "ocr", "txt"],
                    help="MinerU 解析模式")
    ap.add_argument("--mineru-api-url", default="",
                    help="MinerU API 服务地址，留空则使用本地 CLI")
    ap.add_argument("--batch-size", type=int, default=32,
                    help="嵌入批大小（CPU 建议 16–32，4090 可用 256）")
    args = ap.parse_args()

    build_knowledge_base(
        tenant_id=args.tenant_id,
        kb_name=args.kb_name,
        qa_source=args.qa_source,
        qa_data_path=args.qa_data_path,
        qa_limit=args.qa_limit,
        pdf_dir=args.pdf_dir,
        batch_size=args.batch_size,
        mineru_api_url=args.mineru_api_url,
        parse_method=args.parse_method,
    )
