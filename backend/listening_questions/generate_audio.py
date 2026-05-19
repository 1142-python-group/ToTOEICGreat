"""
進階版 TTS - 使用 Microsoft Edge TTS (免費、音質佳、支援多口音)
適合：多益 Part 2 應答問題（從 CSV 批次生成）

CSV 欄位需求：
  - scripts: JSON 字串，格式 {"rate": "-5%", "dialog": [[speaker, line], ...]}
             第 1 句為題目（prompt），後 3 句為 (A)(B)(C) 三個選項
  - prompt_line: （選用）顯示用的題目文字，僅用於 log

特色：
  - 支援多個說話者（不同口音輪流對話）
  - 模擬真實 Part 2 節奏：題目唸完後較長停頓，再依序唸 A/B/C 選項
  - 每個選項前會由同一個答題者報讀 "A."、"B."、"C."
"""
import asyncio
import csv
import json
from pathlib import Path
import edge_tts
import os
import glob

_base = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages")
_ffmpeg_list = glob.glob(f"{_base}\\Gyan.FFmpeg*\\**\\bin\\ffmpeg.exe", recursive=True)

if _ffmpeg_list:
    _bin_dir = os.path.dirname(_ffmpeg_list[0])
    # 把 bin 目錄加到當前 process 的 PATH 最前面
    os.environ["PATH"] = _bin_dir + os.pathsep + os.environ.get("PATH", "")
    print(f"已加入 PATH：{_bin_dir}")

from pydub import AudioSegment

# 多益常見的四種口音對應的語音
VOICES = {
    "US_male":   "en-US-GuyNeural",       # 美國男性
    "US_female": "en-US-JennyNeural",     # 美國女性
    "UK_male":   "en-GB-RyanNeural",      # 英國男性
    "UK_female": "en-GB-SoniaNeural",     # 英國女性
    "AU_male":   "en-AU-WilliamNeural",   # 澳洲男性
    "AU_female": "en-AU-NatashaNeural",   # 澳洲女性
    "CA_male":   "en-CA-LiamNeural",      # 加拿大男性
    "CA_female": "en-CA-ClaraNeural",     # 加拿大女性
}

# Part 2 節奏設定（毫秒）
PROMPT_PAUSE_MS = 350    # 題目唸完之後的停頓
LABEL_PAUSE_MS  = 150    # 選項跟內容之間的停頓
OPTION_PAUSE_MS = 350    # 選項之間的停頓
OPTION_LABELS = ["A.", "B.", "C."]


async def synthesize_line(text: str, voice: str, output: str, rate: str = "-5%", max_retries: int = 3):
    """產生單句音檔。rate 範例：'-10%' 較慢、'+0%' 正常、'+10%' 較快"""
    for attempt in range(1, max_retries + 1):
        try:        # 避免因網路波動導致生成失敗
            communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate)
            await communicate.save(output)
            return
        except Exception as e:
            if attempt == max_retries:
                raise
            wait = 2 ** attempt  # 2s、4s、8s
            print(f"  ⚠️  第 {attempt} 次失敗（{type(e).__name__}），{wait} 秒後重試...")
            await asyncio.sleep(wait)


async def generate_part2_question(
    dialog: list[tuple[str, str]],
    output: str,
    rate: str = "-5%",
    prompt_pause_ms: int = PROMPT_PAUSE_MS,
    label_pause_ms: int = LABEL_PAUSE_MS,
    option_pause_ms: int = OPTION_PAUSE_MS,
):
    """
    產生一道 Part 2 題目音檔。
 
    dialog 結構（共 4 句）：
      [0] 題目         (speaker_q, prompt)
      [1] 選項 A       (speaker_a, option A)
      [2] 選項 B       (speaker_a, option B)
      [3] 選項 C       (speaker_a, option C)
 
    順序：
      題目 →（prompt_pause）→
      "A." →（label_pause）→ 選項A →（option_pause）→
      "B." →（label_pause）→ 選項B →（option_pause）→
      "C." →（label_pause）→ 選項C
    """
    if len(dialog) != 4:
        raise ValueError(f"Part 2 題目需要 4 句（1 題目 + 3 選項），實際收到 {len(dialog)} 句")
 
    output_folder = os.path.dirname(output)
    if output_folder:
        os.makedirs(output_folder, exist_ok=True)
 
    tmp_dir = f"tmp_tts_{Path(output).stem}"
    os.makedirs(tmp_dir, exist_ok=True)
 
    # segments 每個元素為 (path, pause_after_ms)
    segments = []
 
    # ----- 第 0 句：題目 -----
    q_speaker, q_text = dialog[0]
    q_voice = VOICES.get(q_speaker)
    if q_voice is None:
        raise ValueError(f"未知的說話者：{q_speaker}，可用：{list(VOICES.keys())}")
    q_path = f"{tmp_dir}/seg_q.mp3"
    await synthesize_line(q_text, q_voice, q_path, rate=rate)
    segments.append((q_path, prompt_pause_ms))
    print(f"  題目 [{q_speaker}]: {q_text[:60]}...")
 
    # ----- 第 1~3 句：A/B/C 選項（label 與內容分開生成）-----
    options = dialog[1:]
    for i, (speaker, line) in enumerate(options):
        voice = VOICES.get(speaker)
        if voice is None:
            raise ValueError(f"未知的說話者：{speaker}，可用：{list(VOICES.keys())}")
        label = OPTION_LABELS[i]
 
        # label 獨立成段（"A.", "B.", "C."）
        label_path = f"{tmp_dir}/seg_{i}_label.mp3"
        await synthesize_line(label, voice, label_path, rate=rate)
        segments.append((label_path, label_pause_ms))  # 唸完 label 後停一下
 
        # 選項內容
        body_path = f"{tmp_dir}/seg_{i}_body.mp3"
        await synthesize_line(line, voice, body_path, rate=rate)
        # 最後一個選項後不需要停頓
        is_last = (i == len(options) - 1)
        segments.append((body_path, 0 if is_last else option_pause_ms))
 
        print(f"  ({label}) [{speaker}]: {line[:60]}...")
 
    # ----- 合併 -----
    combined = AudioSegment.empty()
    for path, pause in segments:
        combined += AudioSegment.from_mp3(path)
        if pause > 0:
            combined += AudioSegment.silent(duration=pause)
 
    combined.export(output, format="mp3")
    print(f"  ✓ {output}（{len(combined)/1000:.1f} 秒）\n")
 
    # 清理暫存
    for path, _ in segments:
        os.remove(path)
    os.rmdir(tmp_dir)

async def generate_part3_conversation(
    dialog: list[tuple[str, str]],
    output: str,
    rate: str = "-5%",
    line_pause_ms: int = 350,
):
    """
    產生一段 Part 3 對話音檔。

    dialog 結構：
      [
        ["UK_male", "Good morning..."],
        ["US_male", "Oh, right..."],
        ...
      ]

    Part 3 不需要唸 A/B/C/D，因為音檔只播放對話。
    題目與選項通常顯示在畫面或試卷上。
    """
    if len(dialog) < 2:
        raise ValueError(f"Part 3 對話至少需要 2 句，實際收到 {len(dialog)} 句")

    output_folder = os.path.dirname(output)
    if output_folder:
        os.makedirs(output_folder, exist_ok=True)

    tmp_dir = f"tmp_tts_{Path(output).stem}"
    os.makedirs(tmp_dir, exist_ok=True)

    segments = []

    for i, (speaker, line) in enumerate(dialog):
        voice = VOICES.get(speaker)

        if voice is None:
            raise ValueError(f"未知的說話者：{speaker}，可用：{list(VOICES.keys())}")

        seg_path = f"{tmp_dir}/seg_{i}.mp3"
        await synthesize_line(line, voice, seg_path, rate=rate)

        is_last = i == len(dialog) - 1
        segments.append((seg_path, 0 if is_last else line_pause_ms))

        print(f"  [{speaker}]: {line[:70]}...")

    combined = AudioSegment.empty()

    for path, pause in segments:
        combined += AudioSegment.from_mp3(path)
        if pause > 0:
            combined += AudioSegment.silent(duration=pause)

    combined.export(output, format="mp3")
    print(f"  ✓ {output}（{len(combined) / 1000:.1f} 秒）\n")

    for path, _ in segments:
        os.remove(path)

    os.rmdir(tmp_dir)

def load_questions_from_csv(csv_path: str) -> list[dict]:
    """
    從 CSV 讀題目，解析每列的 scripts 欄位。

    回傳：[{"index": 1, "rate": "-5%", "dialog": [...], "prompt_line": "..."}, ...]
    """
    questions = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=1):
            scripts_raw = row.get("scripts", "").strip()
            if not scripts_raw:
                print(f"⚠️  第 {i} 列沒有 scripts 欄位，略過")
                continue
            try:
                script = json.loads(scripts_raw)
            except json.JSONDecodeError as e:
                print(f"❌ 第 {i} 列 scripts 解析失敗：{e}")
                continue
            dialog = [tuple(item) for item in script["dialog"]]
            questions.append({
                "index": i,
                "question_id": row.get("question_id", "").strip(),
                "rate": script.get("rate", "-5%"),
                "dialog": dialog,
                "prompt_line": row.get("prompt_line", "").strip(),
                "skill_tag": row.get("skill_tag", "").strip(),
            })
    return questions

def load_part3_groups_from_csv(csv_path: str) -> list[dict]:
    """
    從 Part 3 CSV 讀取題組。
    同一個 group_id 只產生一個音檔。
    """
    groups = {}

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        for i, row in enumerate(reader, start=1):
            group_id = row.get("group_id", "").strip()
            question_id = row.get("question_id", "").strip()

            if not group_id:
                group_id = question_id

            if group_id in groups:
                continue

            scripts_raw = row.get("scripts", "").strip()

            if not scripts_raw:
                print(f"⚠️ 第 {i} 列沒有 scripts 欄位，略過")
                continue

            try:
                script = json.loads(scripts_raw)
            except json.JSONDecodeError as e:
                print(f"❌ 第 {i} 列 scripts 解析失敗：{e}")
                continue

            dialog = [tuple(item) for item in script["dialog"]]

            groups[group_id] = {
                "group_id": group_id,
                "rate": script.get("rate", "-5%"),
                "title": script.get("title", ""),
                "dialog": dialog,
                "skill_tag": row.get("skill_tag", "").strip(),
            }

    return list(groups.values())

async def main():
    # part 2
    csv_path = Path("toeic_part2_questions.csv")
    output_dir = Path("audio/L2")
    output_dir.mkdir(exist_ok=True)

    if not csv_path.exists():
        print(f"❌ 找不到 {csv_path}")
        return

    questions = load_questions_from_csv(str(csv_path))
    print(f"從 CSV 讀到 {len(questions)} 道 Part 2題目。\n")

    # 跳過已存在的音檔
    pending = []
    for q in questions:
        out_path = output_dir / f"{q['question_id']}.mp3"
        if out_path.exists():
            continue
        pending.append((q, out_path))

    print(f"其中 {len(pending)} 道尚未生成音檔，開始處理...\n")

    failed = []
    for q, out_path in pending:
        print(f"=== {q['question_id']}  [{q['skill_tag']}] ===")
        try:
            await generate_part2_question(
                dialog=q["dialog"],
                output=str(out_path),
                rate=q["rate"],
            )
        except Exception as e:
            print(f"❌ Q{q['index']:03d} 處理失敗：{e}\n")
            failed.append(q["index"])
            continue

    print(f"\n✅ 全部完成！共處理 {len(pending)} 道題目")
    if failed:
        print(f"⚠️  有 {len(failed)} 道題目處理失敗：{failed}")

    # part 3
    csv_path = Path("toeic_part3_questions.csv")
    output_dir = Path("audio/L3")
    output_dir.mkdir(parents=True, exist_ok=True)

    if not csv_path.exists():
        print(f"❌ 找不到 {csv_path}")
        return

    groups = load_part3_groups_from_csv(str(csv_path))
    print(f"從 CSV 讀到 {len(groups)} 組 Part 3 對話。\n")

    pending = []

    for g in groups:
        out_path = output_dir / f"{g['group_id']}.mp3"

        if out_path.exists():
            continue

        pending.append((g, out_path))

    print(f"其中 {len(pending)} 組尚未生成音檔，開始處理...\n")

    failed = []

    for g, out_path in pending:
        print(f"=== {g['group_id']} [{g['skill_tag']}] {g['title']} ===")

        try:
            await generate_part3_conversation(
                dialog=g["dialog"],
                output=str(out_path),
                rate=g["rate"],
            )

        except Exception as e:
            print(f"❌ {g['group_id']} 處理失敗：{e}\n")
            failed.append(g["group_id"])
            continue

    print(f"\n✅ 全部完成！共處理 {len(pending)} 組 Part 3 對話")

    if failed:
        print(f"⚠️ 有 {len(failed)} 組處理失敗：{failed}")


if __name__ == "__main__":
    asyncio.run(main())