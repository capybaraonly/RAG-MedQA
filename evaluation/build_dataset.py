"""
构建离线评测集：从 data/medical/finetune/train_zh_0.json 采样 200 条 QA 对。

输出：evaluation/dataset/eval_dataset.jsonl
"""

import json
import os
import random
import re
import sys
from collections import defaultdict

random.seed(42)

# 确保能 import config
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (
    RAW_DATA_PATH,
    DATASET_DIR,
    DATASET_FILE,
    SAMPLE_SIZE,
    MIN_OUTPUT_LEN,
    MAX_OUTPUT_LEN,
)


# ── 医学关键词分桶 ──────────────────────────────────────────────────────
MEDICAL_KEYWORDS = [
    # 科室
    "内科", "外科", "儿科", "妇产科", "皮肤科", "眼科", "耳鼻喉", "口腔",
    "神经", "精神", "肿瘤", "心血管", "呼吸", "消化", "泌尿", "内分泌",
    "血液", "骨科", "麻醉", "急诊", "重症", "康复", "影像", "超声",
    "病理", "检验", "药学", "护理", "中医", "针灸", "推拿",
    # 症状
    "发热", "咳嗽", "头痛", "腹痛", "胸痛", "腹泻", "呕吐", "皮疹",
    "水肿", "黄疸", "出血", "昏迷", "抽搐", "瘫痪", "呼吸困难",
    # 药品
    "抗生素", "激素", "疫苗", "中药", "西药",
]


def _extract_bucket(instruction: str) -> str:
    """按 instruction 中的医学关键词分桶，无匹配时归入 '其他'"""
    for kw in MEDICAL_KEYWORDS:
        if kw in instruction:
            return kw
    return "其他"


def _clean_text(text: str) -> str:
    """去除多余空白"""
    return re.sub(r"\s+", " ", text).strip()


def build_dataset():
    """主入口：构建评测集"""
    os.makedirs(DATASET_DIR, exist_ok=True)

    # ── 读取全部数据 ────────────────────────────────────────────────────
    candidates = []
    with open(RAW_DATA_PATH, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            instruction = _clean_text(record.get("instruction", ""))
            output = _clean_text(record.get("output", ""))

            if not instruction or not output:
                continue
            if len(output) < MIN_OUTPUT_LEN or len(output) > MAX_OUTPUT_LEN:
                continue

            bucket = _extract_bucket(instruction)
            candidates.append({
                "raw_idx": idx,
                "question": instruction,
                "reference_answer": output,
                "bucket": bucket,
            })

    print(f"候选 QA 对（过滤后）: {len(candidates)}")

    # ── 分桶均匀采样 ────────────────────────────────────────────────────
    buckets = defaultdict(list)
    for c in candidates:
        buckets[c.pop("bucket")].append(c)

    print(f"分桶数: {len(buckets)}")
    for bucket, items in sorted(buckets.items(), key=lambda x: -len(x[1])):
        print(f"  {bucket}: {len(items)}")

    per_bucket = max(1, SAMPLE_SIZE // len(buckets))
    sampled = []
    for bucket, items in buckets.items():
        random.shuffle(items)
        take = min(per_bucket, len(items))
        sampled.extend(items[:take])

    # 如果不足 SAMPLE_SIZE，从剩余中补充
    if len(sampled) < SAMPLE_SIZE:
        sampled_ids = {s["raw_idx"] for s in sampled}
        remaining = [c for c in candidates if c["raw_idx"] not in sampled_ids]
        random.shuffle(remaining)
        needed = SAMPLE_SIZE - len(sampled)
        sampled.extend(remaining[:needed])

    sampled = sampled[:SAMPLE_SIZE]
    sampled.sort(key=lambda x: x["raw_idx"])

    # ── 写入 JSONL ──────────────────────────────────────────────────────
    with open(DATASET_FILE, "w", encoding="utf-8") as f:
        for i, item in enumerate(sampled):
            record = {
                "id": f"qa_{i + 1:04d}",
                "question": item["question"],
                "reference_answer": item["reference_answer"],
                "source": "qa_pair",
                "metadata": {
                    "source_file": os.path.basename(RAW_DATA_PATH),
                    "raw_idx": item["raw_idx"],
                },
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"✓ 评测集已生成: {DATASET_FILE} ({len(sampled)} 条)")


if __name__ == "__main__":
    build_dataset()
