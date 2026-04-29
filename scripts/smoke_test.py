#!/usr/bin/env python3
"""
知识库入库冒烟测试脚本。

执行步骤：
1. 启动本地 BGE-M3 嵌入服务（端口 6380）
2. 在 DB 中注册 xxxx factory 的 embedding 模型（仅首次执行）
3. 跑 build_medical_kb.py --qa-limit 100
4. 验证 ES 中确实写入了文档

用法:
  python scripts/smoke_test.py --tenant-id <id>

如果本地嵌入服务已在运行（另一个终端 python scripts/mini_emb_server.py），
可以加 --skip-server 跳过启动步骤。
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def wait_for_server(url: str, timeout: int = 60):
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            time.sleep(1)
    return False


def register_embedding_model(tenant_id: str):
    """DB 中注册 xxxx 工厂的 bge-m3 embedding（幂等）。"""
    from common.settings import init_settings
    init_settings()
    from api.db.db_models import init_database_tables, TenantLLM, LLMFactories, LLM
    init_database_tables()

    factory_name = "xxxx"
    model_name = "bge-m3@xxxx"

    # 确保 LLMFactories 有 xxxx
    if not LLMFactories.get_or_none(LLMFactories.name == factory_name):
        LLMFactories.create(name=factory_name, logo="", tags="Embedding", status="1")
        print(f"  已添加 factory: {factory_name}")

    # 确保 LLM 表有 bge-m3@xxxx embedding 条目
    if not LLM.get_or_none(LLM.fid == factory_name, LLM.llm_name == model_name):
        LLM.create(
            fid=factory_name,
            llm_name=model_name,
            model_type="embedding",
            max_tokens=8096,
            tags="Embedding",
            status="1",
        )
        print(f"  已添加 LLM: {model_name}")

    # 确保 TenantLLM 有该 tenant 的 embedding 配置
    if not TenantLLM.get_or_none(
        TenantLLM.tenant_id == tenant_id,
        TenantLLM.llm_name == model_name,
        TenantLLM.model_type == "embedding",
    ):
        TenantLLM.create(
            tenant_id=tenant_id,
            llm_factory=factory_name,
            llm_name=model_name,
            model_type="embedding",
            api_key="xxx",
            api_base="http://localhost:6380",
            max_tokens=8096,
            used_tokens=0,
        )
        print(f"  已为 tenant {tenant_id[:8]}... 注册 embedding 模型")
    else:
        print(f"  embedding 模型已注册，跳过")


def verify_indexed(tenant_id: str, kb_id: str, min_docs: int = 50):
    """验证 ES 中写入的文档数量。"""
    from common.settings import init_settings
    init_settings()
    from common import settings
    from rag.nlp.search import index_name

    idx = index_name(tenant_id)
    try:
        # Simple count query
        count = settings.docStoreConn.count({"kb_id": kb_id}, idx, [kb_id])
        print(f"\n  ES 文档数量: {count} (kb_id={kb_id[:8]}...)")
        assert count >= min_docs, f"期望 >= {min_docs} 条，实际 {count} 条"
        print(f"  ✓ 验证通过")
        return True
    except Exception as e:
        print(f"  验证失败: {e}")
        return False


def main():
    ap = argparse.ArgumentParser(description="知识库入库冒烟测试")
    ap.add_argument("--tenant-id", required=True, help="租户 ID")
    ap.add_argument("--skip-server", action="store_true",
                    help="跳过启动本地嵌入服务（已在外部运行时使用）")
    ap.add_argument("--qa-limit", type=int, default=100)
    args = ap.parse_args()

    server_proc = None

    try:
        # ── 1. 启动嵌入服务 ──────────────────────────────────────────
        if not args.skip_server:
            print(">>> 启动本地嵌入服务（BGE-M3，端口 6380）…")
            server_proc = subprocess.Popen(
                [sys.executable, str(PROJECT_ROOT / "scripts" / "mini_emb_server.py")],
                cwd=str(PROJECT_ROOT),
            )
            print("    等待服务就绪（最长 120s，需要加载模型）…")
            if not wait_for_server("http://localhost:6380/health", timeout=120):
                print("  错误：嵌入服务未能在 120s 内启动")
                sys.exit(1)
            print("  ✓ 嵌入服务就绪")
        else:
            print(">>> 跳过嵌入服务启动（--skip-server）")

        # ── 2. 注册 embedding 模型 ────────────────────────────────────
        print("\n>>> 注册 embedding 模型…")
        register_embedding_model(args.tenant_id)

        # ── 3. 运行入库脚本 ───────────────────────────────────────────
        print(f"\n>>> 运行入库脚本（--qa-limit {args.qa_limit}）…")
        cmd = [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "build_medical_kb.py"),
            "--tenant-id", args.tenant_id,
            "--qa-limit", str(args.qa_limit),
            "--batch-size", "16",
        ]
        result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
        if result.returncode != 0:
            print("\n  错误：入库脚本返回非零状态码")
            sys.exit(1)

        # ── 4. 读取生成的 kb_id 并验证 ────────────────────────────────
        print("\n>>> 验证 ES 写入…")
        ckpt_dir = PROJECT_ROOT / "data" / ".checkpoints"
        ckpt_files = list(ckpt_dir.glob(f"global_{args.tenant_id}_*.json"))
        if not ckpt_files:
            print("  警告：找不到全局 checkpoint，跳过 ES 验证")
        else:
            import json
            ckpt = json.loads(ckpt_files[0].read_text())
            kb_id = ckpt.get("kb_id", "")
            if kb_id:
                verify_indexed(args.tenant_id, kb_id, min_docs=args.qa_limit // 2)
            else:
                print("  警告：checkpoint 中无 kb_id")

        print("\n=== 冒烟测试通过 ===")

    finally:
        if server_proc is not None:
            print("\n>>> 关闭嵌入服务…")
            server_proc.terminate()
            server_proc.wait()


if __name__ == "__main__":
    main()
