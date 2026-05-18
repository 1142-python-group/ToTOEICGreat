"""    
python ListenLLM.py --part 2 --count 5
python ListenLLM.py --part 3 --count 5
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

# 自動載入專案根目錄的 .env 檔
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ---------------------------------------------------------------------------
# 設定
# ---------------------------------------------------------------------------

# 免費層可用模型；Flash 速度快、成本低（免費層也夠用），最適合這種批次出題
MODEL = "gemini-2.5-flash"

CSV_PATH_PART2 = Path("toeic_part2_questions.csv")
CSV_PATH_PART3 = Path("toeic_part3_questions.csv")

# Part 2 真正的考點
GRAMMAR_FOCUS_PART2: list[str] = [
    "WH問句-What", "WH問句-Where", "WH問句-When", "WH問句-Who", "WH問句-Why", "WH問句-How", "WH問句-How much/many/long/often",
    "Yes/No疑問句-Be動詞", "Yes/No疑問句-助動詞Do/Does/Did", "Yes/No疑問句-情態動詞Can/Will/Would/Could",
    "附加問句(Tag Question)", "選擇疑問句(Or Question)", "間接疑問句(Indirect Question)", "否定疑問句(Negative Question)",
    "陳述句回應(Statement)", "建議/邀請句回應(Suggestion/Offer)", "請求句回應(Request)",
]

GRAMMAR_FOCUS_PART3: list[str] = [
    "對話主旨(Main Idea)", "說話目的(Purpose)", "問題/需求辨識(Problem/Need)", "說話者身分/關係(Speaker Identity/Relationship)",
    "對話地點(Location)", "細節理解(Detail)", "時間/地點/數字資訊(Time/Place/Number)",
    "原因理解(Reason)", "下一步行動(Next Action)", "建議/請求/安排(Suggestion/Request/Schedule)",
    "同意/拒絕/變更(Agreement/Refusal/Change)", "語意推論(Inference)", "說話者意圖(Intention)", 
    "態度/語氣(Attitude/Tone)", "常見商務情境(Business Context)",
]

VOICES: list[str] = [
    "US_male", "US_female",
    "UK_male", "UK_female",
    "AU_male", "AU_female",
    "CA_male", "CA_female",
]

CSV_FIELDS = [
    "question_id",
    "group_id",
    "question_text",
    "option_a", "option_b", "option_c", "option_d",
    "correct_answer",
    "explanation",
    "translation",
    "vocabulary",
    "skill_tag",
    "scripts",        # JSON string
    "prompt_line",    # 提問句（去重用）
]


# ---------------------------------------------------------------------------
# CSV 讀寫
# ---------------------------------------------------------------------------

def load_existing_prompt_lines(csv_path: Path) -> set[str]:
    if not csv_path.exists():
        return set()
    prompts: set[str] = set()
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            line = (row.get("prompt_line") or "").strip()
            if line:
                prompts.add(line.lower())
    return prompts


def append_rows(csv_path: Path, rows: list[dict[str, Any]]) -> None:
    write_header = not csv_path.exists()
    with csv_path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if write_header:
            writer.writeheader()
        for row in rows:
            writer.writerow(row)


# ---------------------------------------------------------------------------
# Prompt 組裝
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_2 = """你是一位專業的多益(TOEIC)出題老師，專門負責出 Part 2 (Question-Response) 應答問題。

TOEIC Part 2 的真實格式：
- 一個人說出一句提問或陳述
- 三個說話者分別說出回應選項 A、B、C（注意：只有 A/B/C，沒有 D）
- 考生憑聽力選出最適合的回應
- 題目和選項都不會以文字呈現，全部用聽的

你的任務是依照指定考點，生成符合多益實際難度與語感的題目。
要點：
1. 提問句要自然、職場情境常見（會議、出差、報告、客戶、行銷、人資、辦公室日常等）。
2. 三個選項要有迷惑性：通常一個是正確答案，兩個是相關詞彙陷阱或音近陷阱。
3. 正確答案要符合自然對話邏輯，不要太牽強。
4. 對話者使用不同口音（美/英/澳/加）增加真實感。
5. 解析、翻譯、單字都必須使用「繁體中文」。
6. 嚴格按照指定 JSON 格式輸出，不要加 markdown 程式碼框。"""

SYSTEM_PROMPT_3 = """你是一位專業的多益(TOEIC)出題老師，專門負責出 Part 3 (Conversations) 對話題。

TOEIC Part 3 的真實格式：
- 會播放一段 2 人的英文對話
- 對話通常發生在職場、商務、服務、旅遊、購物、會議、電話、辦公室等情境
- 每段對話後會有 3 題選擇題
- 每題有 A/B/C/D 四個選項
- 考生根據整段對話內容作答
- 有些題目會考主旨、目的、細節、推論、下一步行動

你的任務是依照指定考點，生成符合多益實際難度與語感的 Part 3 對話題。

出題要點：
1. 對話要自然、真實，符合 TOEIC 商務與日常職場情境。
2. 對話長度約 4~6 句，適合生成 3 題。
3. 每段對話需有清楚情境，例如：會議安排、訂單問題、客戶服務、出差、報告、維修、活動規劃、辦公室行政等。
4. 三題必須考不同層次：至少包含「主旨/目的」、「細節理解」、「推論或下一步行動」。
5. 選項要有迷惑性，但正確答案必須能從對話中合理判斷。
6. 對話者使用不同口音（美/英/澳/加），增加聽力真實感。
7. 解析、翻譯、單字都必須使用「繁體中文」。
8. 嚴格按照指定 JSON 格式輸出，不要加 markdown 程式碼框。
"""

def get_short_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:6]}"

def build_user_prompt_2(
    current_grammar: str,
    asker_voice: str,
    responder_voice: str,
    avoid_prompts: list[str],
) -> str:
    avoid_block = ""
    if avoid_prompts:
        sample = avoid_prompts[-30:]
        avoid_block = (
            "\n\n【避免重複】以下提問句已經出過了，請務必生成完全不同主題與句型的新題：\n"
            + "\n".join(f"- {p}" for p in sample)
        )

    return f"""請生成一題多益 Part 2 題目。

【考點 skill_tag】：{current_grammar}
【說話者設定】：
- 提問者語音：{asker_voice}
- 回應者語音：{responder_voice}（三個選項 A/B/C 都由這同一個回應者說出）

請嚴格按照以下 JSON 格式輸出（不要加 ```json 框，不要加任何說明文字）：

{{
  "question_text": "",
  "option_a": "A",
  "option_b": "B",
  "option_c": "C",
  "option_d": "D",
  "correct_answer": "A 或 B 或 C（Part 2 不會是 D）",
  "explanation": "繁體中文簡短解析（1-2 句，約 30-60 字）：點出本題的關鍵聽力陷阱或答題技巧即可，不需要逐題說明每個選項，因為翻譯已能幫助使用者理解。",
  "translation": "整句繁體中文翻譯：包含提問句以及三個選項的翻譯，格式為「問：xxx／A：xxx／B：xxx／C：xxx」。",
  "vocabulary": "請嚴格統一使用此格式：【英文單字 (詞性) - 繁體中文解釋】，多個單字用頓號分隔。範例：revenue (n.) - 營收、implement (v.) - 實施。列出 2-3 個重點單字。",
  "skill_tag": "{current_grammar}",
  "scripts": {{
    "rate": "-5%",
    "dialog": [
      ["{asker_voice}", "提問者說的英文句子"],
      ["{responder_voice}", "選項A的英文句子"],
      ["{responder_voice}", "選項B的英文句子"],
      ["{responder_voice}", "選項C的英文句子"]
    ]
  }}
}}

注意事項：
- question_text 一律留空字串 ""（這是資料庫設計，不要填內容）
- option_a / option_b / option_c / option_d 一律固定為 "A" / "B" / "C" / "D"（不要把實際句子填進去；實際句子在 scripts.dialog 裡）
- correct_answer 只能是 "A" / "B" / "C" 其中一個，生成答案為 C 的題目。
- scripts.dialog 必須剛好 4 個元素：第 1 個是提問句，後 3 個依序對應 A/B/C
- 語音代號必須完全照上面寫的（提問者 = {asker_voice}，回應者三句都是 {responder_voice}），請勿更動
- 提問句要自然、真實，符合多益職場情境{avoid_block}"""

def build_user_prompt_3(
    current_focus: str,
    speaker_1_voice: str,
    speaker_2_voice: str,
    avoid_prompts: list[str],
) -> str:
    avoid_block = ""
    if avoid_prompts:
        sample = avoid_prompts[-20:]
        avoid_block = (
            "\n\n【避免重複】以下對話開頭或主題已經出過了，請務必生成完全不同情境的新題：\n"
            + "\n".join(f"- {p}" for p in sample)
        )

    speaker_setting = f"""
- Speaker 1 語音：{speaker_1_voice}
- Speaker 2 語音：{speaker_2_voice}
"""

    return f"""請生成一組多益 TOEIC Listening Part 3 對話題。

【考點 skill_tag】：{current_focus}

【說話者設定】：
{speaker_setting}

請嚴格按照以下 JSON 格式輸出（不要加 ```json 框，不要加任何說明文字）：

{{
  "question_text": "Part 3 Conversation",
  "option_a": "",
  "option_b": "",
  "option_c": "",
  "option_d": "",
  "correct_answer": "",
  "explanation": "繁體中文簡短解析（1-2 句，約 30-60 字）：點出本題的關鍵聽力陷阱或答題技巧即可，不需要逐題說明每個選項，因為翻譯已能幫助使用者理解。",
  "translation": "整句繁體中文翻譯：包含對話內容的翻譯，格式為「Speaker 1：xxx／Speaker 2：xxx／...」。",
  "vocabulary": "請嚴格統一使用此格式：【英文單字 (詞性) - 繁體中文解釋】，多個單字用頓號分隔。範例：revenue (n.) - 營收、implement (v.) - 實施。列出 2-3 個重點單字。",
  "skill_tag": "{current_focus}",
  "scripts": {{
    "title": "Part 3 - 簡短英文標題",
    "rate": "-5%",
    "dialog": [
      ["{speaker_1_voice}", "第一句英文對話"],
      ["{speaker_2_voice}", "第二句英文對話"]
    ]
  }},
  "questions": [
    {{
      "question_text": "Question 1 的英文題目",
      "option_a": "A. 英文選項",
      "option_b": "B. 英文選項",
      "option_c": "C. 英文選項",
      "option_d": "D. 英文選項",
      "correct_answer": "A/B/C/D",
      "explanation": "繁體中文解析，說明為什麼此選項正確。",
      "translation": "題目與四個選項。",
      "skill_tag": "{current_focus}"
    }},
    {{
      "question_text": "Question 2 的英文題目",
      "option_a": "A. 英文選項",
      "option_b": "B. 英文選項",
      "option_c": "C. 英文選項",
      "option_d": "D. 英文選項",
      "correct_answer": "A/B/C/D",
      "explanation": "繁體中文解析，說明為什麼此選項正確。",
      "translation": "題目與四個選項。",
      "skill_tag": "{current_focus}"
    }},
    {{
      "question_text": "Question 3 的英文題目",
      "option_a": "A. 英文選項",
      "option_b": "B. 英文選項",
      "option_c": "C. 英文選項",
      "option_d": "D. 英文選項",
      "correct_answer": "A/B/C/D",
      "explanation": "繁體中文解析，說明為什麼此選項正確。",
      "translation": "題目與四個選項。",
      "skill_tag": "{current_focus}"
    }}
  ]
}}

注意事項：
- 選項之間的換行用／表示，保持在同一行。
- scripts.dialog 必須是完整英文對話，約 4~6 句，並且控制在 50 內能說完的長度。
- 每句格式必須是 ["語音代號", "英文句子"]。
- 語音代號只能使用指定的 speaker voice，不可以自行新增。
- 如果是兩人對話，只能使用 Speaker 1 和 Speaker 2。
- 如果提供 Speaker 3，才可以使用三人對話。
- questions 必須剛好 3 題。
- 每題都必須有 A/B/C/D 四個選項。
- correct_answer 必須是 "A"、"B"、"C"、"D" 其中一個。
- 三題考點要有差異，不要三題都只問細節。
- 建議三題安排：
  1. 主旨/目的題
  2. 細節題
  3. 推論/下一步行動題
- 對話內容必須能明確支持正確答案。
- 不要讓正確答案過於明顯，也不要讓錯誤選項完全無關。
- 題目與選項使用自然 TOEIC 英文。
- 解析、翻譯、vocabulary 一律使用繁體中文。
{avoid_block}
"""

# ---------------------------------------------------------------------------
# 呼叫 Gemini
# ---------------------------------------------------------------------------

def call_gemini(
    client: genai.Client,
    user_prompt: str,
    system_prompt: str,
    *,
    max_retries: int = 4
) -> str:
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            resp = client.models.generate_content(
                model=MODEL,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    temperature=0.9,
                    max_output_tokens=4000,
                ),
            )
            return (resp.text or "").strip()

        except Exception as e:
            last_error = e
            msg = str(e)
            transient = any(s in msg for s in (
                "503", "500", "UNAVAILABLE", "overloaded",
                "RESOURCE_EXHAUSTED", "429"
            ))

            if not transient or attempt == max_retries:
                raise

            wait = 5 * (2 ** (attempt - 1))
            print(f"  ⏳ 第 {attempt} 次失敗（伺服器忙碌），{wait} 秒後重試...")
            time.sleep(wait)

    raise last_error if last_error else RuntimeError("call_gemini 異常結束")


def parse_response(raw: str) -> dict[str, Any]:
    """容錯地把模型回傳解成 dict。"""
    text = raw.strip()
    # 萬一被包了 ```json ... ```
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"找不到 JSON：{raw[:200]}")
    return json.loads(text[start : end + 1])


# ---------------------------------------------------------------------------
# 驗證 & 正規化
# ---------------------------------------------------------------------------

def validate_and_normalize(q: dict[str, Any]) -> dict[str, Any]:
    required = [
        "question_text", "option_a", "option_b", "option_c", "option_d",
        "correct_answer", "explanation", "translation",
        "vocabulary", "skill_tag", "scripts",
    ]
    for k in required:
        if k not in q:
            raise ValueError(f"缺少欄位：{k}")

    # 強制覆寫
    q["question_text"] = ""
    q["option_a"] = "A"
    q["option_b"] = "B"
    q["option_c"] = "C"
    q["option_d"] = "D"

    if q["correct_answer"] not in ("A", "B", "C"):
        raise ValueError(f"correct_answer 必須是 A/B/C：{q['correct_answer']}")

    scripts = q["scripts"]
    if not isinstance(scripts, dict):
        raise ValueError("scripts 必須是 dict")
    if "rate" not in scripts or "dialog" not in scripts:
        raise ValueError("scripts 缺少 rate 或 dialog")

    dialog = scripts["dialog"]
    if not isinstance(dialog, list) or len(dialog) != 4:
        raise ValueError(
            f"scripts.dialog 必須剛好 4 筆，實際 {len(dialog) if isinstance(dialog, list) else 'N/A'}"
        )

    for i, item in enumerate(dialog):
        if not (isinstance(item, list) and len(item) == 2):
            raise ValueError(f"scripts.dialog[{i}] 必須是 [speaker, text] 兩元素陣列")
        speaker, text = item
        if speaker not in VOICES:
            raise ValueError(f"未知語音代號：{speaker}")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"scripts.dialog[{i}] 的文字為空")

    # Part 2 規則：三個選項必須由同一個回應者說，且跟提問者不同人
    asker_voice = dialog[0][0]
    responder_voices = {dialog[1][0], dialog[2][0], dialog[3][0]}
    if len(responder_voices) != 1:
        raise ValueError(f"三個選項必須是同一個回應者，實際：{responder_voices}")
    responder_voice = next(iter(responder_voices))
    if responder_voice == asker_voice:
        raise ValueError(f"提問者與回應者不能同一人：{asker_voice}")

    return q

def validate_and_normalize_part3(q: dict[str, Any]) -> dict[str, Any]:
    required = [
        "question_text", "option_a", "option_b", "option_c", "option_d",
        "correct_answer", "explanation", "translation",
        "vocabulary", "skill_tag", "scripts", "questions",
    ]

    for k in required:
        if k not in q:
            raise ValueError(f"缺少欄位：{k}")

    scripts = q["scripts"]
    if not isinstance(scripts, dict):
        raise ValueError("scripts 必須是 dict")

    if "rate" not in scripts or "dialog" not in scripts:
        raise ValueError("scripts 缺少 rate 或 dialog")

    dialog = scripts["dialog"]
    if not isinstance(dialog, list):
        raise ValueError("scripts.dialog 必須是 list")

    for i, item in enumerate(dialog):
        if not (isinstance(item, list) and len(item) == 2):
            raise ValueError(f"scripts.dialog[{i}] 必須是 [speaker, text]")

        speaker, text = item

        if speaker not in VOICES:
            raise ValueError(f"未知語音代號：{speaker}")

        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"scripts.dialog[{i}] 文字為空")

    questions = q["questions"]
    if not isinstance(questions, list) or len(questions) != 3:
        raise ValueError("Part 3 questions 必須剛好 3 題")

    for idx, item in enumerate(questions):
        for key in [
            "question_text",
            "option_a", "option_b", "option_c", "option_d",
            "correct_answer",
            "explanation",
            "translation",
            "skill_tag",
        ]:
            if key not in item:
                raise ValueError(f"questions[{idx}] 缺少欄位：{key}")

        if item["correct_answer"] not in ("A", "B", "C", "D"):
            raise ValueError(
                f"questions[{idx}].correct_answer 必須是 A/B/C/D：{item['correct_answer']}"
            )

    return q

def to_csv_row_part2(q: dict[str, Any]) -> dict[str, Any]:
    prompt_line = q["scripts"]["dialog"][0][1]
    return {
        "question_id": get_short_id("L2"),
        "group_id": "",
        "question_text": q["question_text"],
        "option_a": q["option_a"],
        "option_b": q["option_b"],
        "option_c": q["option_c"],
        "option_d": q["option_d"],
        "correct_answer": q["correct_answer"],
        "explanation": q["explanation"],
        "translation": q["translation"],
        "vocabulary": q["vocabulary"],
        "skill_tag": q["skill_tag"],
        "scripts": json.dumps(q["scripts"], ensure_ascii=False),
        "prompt_line": prompt_line,
    }

def to_csv_rows_part3(q: dict[str, Any]) -> list[dict[str, Any]]:
    group_id = get_short_id("L3")
    prompt_line = q["scripts"]["dialog"][0][1]
    scripts_json = json.dumps(q["scripts"], ensure_ascii=False)

    rows = []

    for idx, item in enumerate(q["questions"], start=1):
        rows.append({
            "question_id": get_short_id("L3"),
            "group_id": group_id,
            "question_text": item["question_text"],
            "option_a": item["option_a"],
            "option_b": item["option_b"],
            "option_c": item["option_c"],
            "option_d": item["option_d"],
            "correct_answer": item["correct_answer"],
            "explanation": item["explanation"],
            "translation": item["translation"],
            "vocabulary": q["vocabulary"],
            "skill_tag": item.get("skill_tag", q["skill_tag"]),
            "scripts": scripts_json,
            "prompt_line": prompt_line if idx == 1 else "",
        })

    return rows

# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def generate_batch(part: int, count: int, csv_path: Path, max_retry: int = 3) -> None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("錯誤：請先在 .env 設定 GEMINI_API_KEY", file=sys.stderr)
        print("從 https://aistudio.google.com/apikey 取得", file=sys.stderr)
        sys.exit(1)

    client = genai.Client(api_key=api_key)
    existing = load_existing_prompt_lines(csv_path)
    print(f"📚 已有 {len(existing)} 題在 {csv_path}")

    new_rows: list[dict[str, Any]] = []
    generated = 0
    attempts = 0
    max_total_attempts = count * (max_retry + 1)

    while generated < count and attempts < max_total_attempts:
        attempts += 1

        if part == 2:
            current_grammar = random.choice(GRAMMAR_FOCUS_PART2)
            asker_voice, responder_voice = random.sample(VOICES, 2)

            print(f"\n▶ [{generated + 1}/{count}] Part 2 考點：{current_grammar}")
            print(f"   提問者：{asker_voice} / 回應者：{responder_voice}")

            user_prompt = build_user_prompt_2(
                current_grammar=current_grammar,
                asker_voice=asker_voice,
                responder_voice=responder_voice,
                avoid_prompts=sorted(existing),
            )

            system_prompt = SYSTEM_PROMPT_2

        elif part == 3:
            current_focus = random.choice(GRAMMAR_FOCUS_PART3)
            speaker_1_voice, speaker_2_voice = random.sample(VOICES, 2)

            print(f"\n▶ [{generated + 1}/{count}] Part 3 考點：{current_focus}")
            print(f"   Speaker 1：{speaker_1_voice} / Speaker 2：{speaker_2_voice}")

            user_prompt = build_user_prompt_3(
                current_focus=current_focus,
                speaker_1_voice=speaker_1_voice,
                speaker_2_voice=speaker_2_voice,
                avoid_prompts=sorted(existing),
            )

            system_prompt = SYSTEM_PROMPT_3

        else:
            raise ValueError("part 只能是 2 或 3")

        try:
            raw = call_gemini(client, user_prompt, system_prompt)
            parsed = parse_response(raw)

            if part == 2:
                normalized = validate_and_normalize(parsed)
            else:
                normalized = validate_and_normalize_part3(parsed)

        except Exception as e:
            err_msg = str(e)
            if len(err_msg) > 200:
                err_msg = err_msg[:200] + "..."
            print(f"  ⚠️ 生成失敗：{err_msg}")
            continue

        prompt_line = normalized["scripts"]["dialog"][0][1].strip().lower()

        if prompt_line in existing:
            print(f"  ⚠️ 對話/提問句重複，跳過：{prompt_line[:60]}")
            continue

        if part == 2:
            row = to_csv_row_part2(normalized)
            new_rows.append(row)

            print(f"  ✅ 完成：{normalized['scripts']['dialog'][0][1]}")
            print(f"     正解 {normalized['correct_answer']}")

        else:
            rows = to_csv_rows_part3(normalized)
            new_rows.extend(rows)

            print(f"  ✅ 完成 Part 3 對話：{normalized['scripts']['title']}")
            print(f"     已產生 3 題")


        existing.add(prompt_line)
        generated += 1

        time.sleep(4)
        
    if new_rows:
        append_rows(csv_path, new_rows)
        print(f"\n💾 已寫入 {len(new_rows)} 筆資料到 {csv_path}")
    else:
        print("\n⚠️ 沒有任何成功生成的題目")

    if generated < count:
        print(f"⚠️ 目標 {count} 組，實際 {generated} 組（達嘗試上限）")


def main() -> None:
    parser = argparse.ArgumentParser(description="TOEIC Part 2 自動出題 (Gemini)")
    parser.add_argument(
        "--part",
        type=int,
        choices=[2, 3],
        default=3,
        help="要生成 TOEIC Listening 哪一大題：2 或 3",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=5,
        help="要生成的題組數。Part 2 是題數；Part 3 是對話組數，每組會產生 3 題。",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help="CSV 輸出路徑。不填則依照 part 自動選擇。",
    )
    args = parser.parse_args()

    if args.csv is None:
        csv_path = CSV_PATH_PART2 if args.part == 2 else CSV_PATH_PART3
    else:
        csv_path = args.csv
    generate_batch(
        part=args.part,
        count=args.count,
        csv_path=csv_path,
    )


if __name__ == "__main__":
    main()