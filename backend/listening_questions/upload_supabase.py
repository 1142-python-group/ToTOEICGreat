"""
python upload_supabase.py --part 2 
python upload_supabase.py --part 3
把 CSV 題目 + 對應 mp3 上傳到 Supabase

流程：
  1. 讀 toeic_part2_questions.csv
  2. 對每一題：
     a. 把 audio/{question_id}.mp3 上傳到 Supabase Storage (bucket: audio)
     b. INSERT 一筆資料到 questions 表，含 audio_path
  3. 已存在的題目（依 question_id）會跳過

執行前：
    pip install "supabase==2.18.0" python-dotenv

    在 .env 加：
      SUPABASE_URL=https://xhlwsnflkrkfpweoljgj.supabase.co
      SUPABASE_SECRET_KEY=sb_secret_...   (新版,從 Project Settings → API Keys)
      # 或者舊版命名也行：
      # SUPABASE_SERVICE_ROLE_KEY=eyJ...

    在 Supabase Storage 建一個叫 "audio" 的 bucket（Public 即可）

執行：
    python upload_to_supabase.py --limit 1 --dry-run   # 看看會做什麼,不真的上傳
    python upload_to_supabase.py --limit 1             # 真的上傳 1 題測試
    python upload_to_supabase.py                       # 上傳全部(已存在的會跳過)
"""

from __future__ import annotations

import argparse
import csv
from html import parser
import os
import sys
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from supabase import create_client, Client


# ---------------------------------------------------------------------------
# 設定
# ---------------------------------------------------------------------------

CSV_PATH_PART2 = Path("toeic_part2_questions.csv")
CSV_PATH_PART3 = Path("toeic_part3_questions.csv")
AUDIO_DIR_PART2 = Path("audio/L2")
AUDIO_DIR_PART3 = Path("audio/L3")
BUCKET = "audio"
TABLE = "questions"


# ---------------------------------------------------------------------------
# Supabase 連線
# ---------------------------------------------------------------------------

def get_supabase() -> Client:
    url = os.environ.get("SUPABASE_URL", "").strip()
    # 優先讀新版 SUPABASE_SECRET_KEY，找不到再 fallback 到舊版 SUPABASE_SERVICE_ROLE_KEY
    key = (
        os.environ.get("SUPABASE_SECRET_KEY", "").strip()
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    )
    if not url:
        print("❌ 錯誤：.env 缺少 SUPABASE_URL", file=sys.stderr)
        sys.exit(1)
    if not key:
        print("❌ 錯誤：.env 缺少 SUPABASE_SECRET_KEY（或舊版 SUPABASE_SERVICE_ROLE_KEY）", file=sys.stderr)
        print("   到 Supabase Dashboard → Project Settings → API Keys 取得", file=sys.stderr)
        sys.exit(1)
    return create_client(url, key)


# ---------------------------------------------------------------------------
# 讀 CSV
# ---------------------------------------------------------------------------

def load_csv(csv_path: Path) -> list[dict[str, str]]:
    """讀 CSV，自動去除欄位名稱的前後空白（你的 CSV 有 ' question_text' 這種狀況）。"""
    rows: list[dict[str, str]] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        # 修正欄位名稱的空白
        reader.fieldnames = [(n or "").strip() for n in (reader.fieldnames or [])]
        for row in reader:
            # 同時 strip key 與 value
            cleaned = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
            rows.append(cleaned)
    return rows


# ---------------------------------------------------------------------------
# 撈出已存在的 question_id（避免重複插入）
# ---------------------------------------------------------------------------

def fetch_existing_ids(sb: Client) -> set[str]:
    """分頁撈 questions 表所有已存在的 question_id。"""
    existing: set[str] = set()
    page_size = 1000
    offset = 0
    while True:
        resp = (
            sb.table(TABLE)
            .select("question_id")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        data = resp.data or []
        if not data:
            break
        for row in data:
            qid = row.get("question_id")
            if qid:
                existing.add(qid)
        if len(data) < page_size:
            break
        offset += page_size
    return existing


# ---------------------------------------------------------------------------
# 上傳 mp3 到 Storage
# ---------------------------------------------------------------------------

def upload_mp3(sb: Client, mp3_path: Path, storage_path: str) -> bool:
    """上傳 mp3 到 Storage。已存在會 upsert 覆蓋。回傳是否成功。"""
    try:
        with mp3_path.open("rb") as f:
            sb.storage.from_(BUCKET).upload(
                path=storage_path,
                file=f,
                file_options={
                    "content-type": "audio/mpeg",
                    "upsert": "true",
                },
            )
        return True
    except Exception as e:
        print(f"  ⚠️ Storage 上傳失敗：{e}")
        return False


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="把 CSV + mp3 上傳到 Supabase")
    parser.add_argument(
        "--part",
        type=int,
        choices=[2, 3],
        default=2,
        help="要上傳 TOEIC Listening 哪一大題：2 或 3",
    )
    parser.add_argument("--csv", type=Path, default=None, help="CSV 路徑，不填則依 part 自動選擇")
    parser.add_argument("--audio-dir", type=Path, default=None, help="mp3 資料夾，不填則依 part 自動選擇")
    parser.add_argument("--limit", type=int, default=None, help="只處理前 N 題（測試用）")
    parser.add_argument("--dry-run", action="store_true", help="只列印不上傳")
    parser.add_argument("--skip-audio", action="store_true", help="只寫 DB，不上傳 mp3")
    args = parser.parse_args()

    if args.csv is None:
        args.csv = CSV_PATH_PART2 if args.part == 2 else CSV_PATH_PART3

    if args.audio_dir is None:
        args.audio_dir = AUDIO_DIR_PART2 if args.part == 2 else AUDIO_DIR_PART3

    rows = load_csv(args.csv)
    print(f"📄 從 {args.csv} 讀到 {len(rows)} 題")

    # 限制只處理前 N 題
    if args.limit is not None and args.limit > 0:
        rows = rows[: args.limit]
        print(f"🎯 --limit={args.limit}：只處理前 {len(rows)} 題")

    if args.dry_run:
        print("🔍 Dry run 模式：不會真的連 Supabase\n")
        sb = None
        existing_ids: set[str] = set()
    else:
        sb = get_supabase()
        print("🔌 已連線到 Supabase")
        existing_ids = fetch_existing_ids(sb)
        print(f"📚 questions 表已有 {len(existing_ids)} 題")

    stats = {"inserted": 0, "skipped_dup": 0, "skipped_no_mp3": 0, "failed": 0}

    for i, row in enumerate(rows, 1):
        qid = row.get("question_id", "")
        group_id = row.get("group_id", "").strip()
        if not qid:
            print(f"[{i}/{len(rows)}] ⚠️ 沒有 question_id,跳過")
            stats["failed"] += 1
            continue

        # 重複檢查
        if qid in existing_ids:
            print(f"[{i}/{len(rows)}] ⏭️  {qid} 已在 DB,跳過")
            stats["skipped_dup"] += 1
            continue

        # 找對應 mp3
        if args.part == 3:
            audio_id = group_id
            storage_path = f"{audio_id}.mp3"
        else:
            audio_id = qid
            storage_path = f"{audio_id}.mp3"

        mp3_path = args.audio_dir / f"{audio_id}.mp3"

        if not args.skip_audio:
            if not mp3_path.exists():
                print(f"[{i}/{len(rows)}] ⚠️ {qid} 沒有 mp3 ({mp3_path}),跳過")
                stats["skipped_no_mp3"] += 1
                continue

        # 1. 上傳 mp3
        if not args.skip_audio and not args.dry_run:
            ok = upload_mp3(sb, mp3_path, storage_path)
            if not ok:
                stats["failed"] += 1
                continue

        # 2. 組 DB 資料
        record: dict[str, Any] = {
            "question_id":    qid,
            "group_id":       group_id,
            "question_text":  row.get("question_text", ""),
            "option_a":       row.get("option_a", ""),
            "option_b":       row.get("option_b", ""),
            "option_c":       row.get("option_c", ""),
            "option_d":       row.get("option_d", ""),
            "correct_answer": row.get("correct_answer", ""),
            "explanation":    row.get("explanation", ""),
            "skill_tag":      row.get("skill_tag", ""),
            "translation":    row.get("translation", ""),
            "vocabulary":     row.get("vocabulary", ""),
            "part":           args.part,
            "audio_path":     storage_path,
            # created_at 不填,讓 DB 預設值 now() 自動帶
        }

        if args.dry_run:
            print(f"[{i}/{len(rows)}] 🔍 (dry) 會 INSERT {qid}  audio={storage_path}")
            stats["inserted"] += 1
            continue

        # 3. INSERT DB
        try:
            sb.table(TABLE).insert(record).execute()
            existing_ids.add(qid)
            stats["inserted"] += 1
            print(f"[{i}/{len(rows)}] ✅ {qid}  已上傳 + 寫入")
        except Exception as e:
            print(f"[{i}/{len(rows)}] ❌ {qid} DB 寫入失敗:{e}")
            stats["failed"] += 1

    # 統計
    print("\n" + "=" * 50)
    print(f"✅ 成功新增:   {stats['inserted']}")
    print(f"⏭️  已存在跳過: {stats['skipped_dup']}")
    print(f"⚠️ 缺 mp3 跳過: {stats['skipped_no_mp3']}")
    print(f"❌ 失敗:       {stats['failed']}")


if __name__ == "__main__":
    main()