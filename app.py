#!/usr/bin/env python3
"""LectureFlow - Extract action items from lecture transcripts with Gemini."""

from __future__ import annotations

import argparse
import cgi
import html
import json
import os
import re
import shlex
import socket
import sys
import webbrowser
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_ENV_FILE = ".env"
DEFAULT_MD_FILENAME = "lectureflow_todo.md"
DEFAULT_DOWNLOADS_DIRNAME = "Downloads"
DEFAULT_WEB_HOST = "127.0.0.1"
DEFAULT_WEB_PORT = 8765

DEFAULT_SYSTEM_PROMPT = """You are a precise task extraction assistant specialized in processing university lecture transcripts and meeting notes.

MISSION: Extract ONLY explicitly stated action items - tasks that someone is clearly expected to complete. Do not infer, assume, or create tasks from general discussion, explanations, or opinions.

OUTPUT FORMAT: Return a valid JSON object with this structure:
{
  "action_items": [
    {
      "task": "Clear one-sentence description of what needs to be done",
      "owner": "Specific person's name, 'Everyone', or 'Unspecified (needs clarification)'",
      "deadline": "Exact date/time if stated, 'Approximate: [timeframe]' if vague, or 'Not specified'",
      "priority": "High / Medium / Low",
      "confidence": "High / Medium / Low",
      "notes": "Any ambiguity, context, or caveats worth flagging"
    }
  ],
  "summary": "One sentence summarizing the overall context",
  "natural_language_summary": "A short natural-language recap (2-4 sentences) for humans",
  "warnings": ["List any ambiguities, unclear references, or items that need human review"]
}

RULES:
1. NEVER fabricate deadlines - if the speaker says "soon" or "whenever", mark deadline as approximate, do not invent a specific date.
2. NEVER assign ownership when the speaker is vague - use "Unspecified (needs clarification)" instead of guessing.
3. NEVER turn lecture content, explanations, or theoretical discussions into action items.
4. If the transcript contains NO actionable items, return an empty action_items array and explain in the summary.
5. Handle multilingual input gracefully - extract tasks regardless of language, and output consistently in English.
6. Add a "confidence" field: High if the task, owner, and deadline are all clear; Medium if one element is ambiguous; Low if multiple elements are unclear.
7. Use the "warnings" array to flag anything a human should double-check.
8. Transcript may be long, noisy, and full of filler words (e.g., um/so/like). Focus on buried explicit assignments, deadlines, and responsibilities.
9. Relative dates like "next week", "week four", and "by Friday" must remain relative unless exact dates are explicitly given.

Respond with valid JSON only. No markdown code fences and no extra text outside JSON.
"""


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="LectureFlow - Extract action items from transcripts using Gemini"
    )

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--input", type=str, help="Path to transcript .txt file")
    mode_group.add_argument("--eval", type=str, help="Path to eval_set.json")

    parser.add_argument(
        "--format",
        type=str,
        default="markdown",
        choices=["markdown", "json"],
        help="Output format for single transcript mode (default: markdown)",
    )
    parser.add_argument(
        "--system-prompt",
        type=str,
        default=None,
        help="Path to custom system prompt file",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output path. Single mode: markdown/json by --format. Eval mode: always JSON",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"Gemini model name (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_WEB_PORT,
        help=f"Web mode port when running without --input/--eval (default: {DEFAULT_WEB_PORT})",
    )
    return parser.parse_args()


def resolve_api_key() -> str | None:
    """Resolve API key from env vars, then .env file."""
    env_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if env_key:
        return env_key.strip()

    script_dir = Path(__file__).resolve().parent
    env_file = script_dir / DEFAULT_ENV_FILE
    if env_file.exists() and env_file.is_file():
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[len("export ") :].strip()
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'\"")
            if key in {"GEMINI_API_KEY", "GOOGLE_API_KEY"} and value:
                return value
    return None


def create_genai_client(api_key: str) -> tuple[Any, Any]:
    """Create Gemini client with lazy import and user-friendly error."""
    try:
        from google import genai as genai_sdk
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "google-genai is not installed. Run: pip install -r requirements.txt"
        ) from exc
    return genai_sdk.Client(api_key=api_key), genai_sdk


def load_system_prompt(prompt_path: str | None) -> str:
    """Load system prompt from custom file, or return default prompt."""
    if not prompt_path:
        return DEFAULT_SYSTEM_PROMPT

    prompt_file = Path(prompt_path).expanduser()
    if not prompt_file.exists() or not prompt_file.is_file():
        raise FileNotFoundError(f"System prompt file not found: {prompt_file}")
    return prompt_file.read_text(encoding="utf-8").strip()


def read_text_file(file_path: str) -> str:
    """Read UTF-8 text from a file path."""
    path = Path(os.path.expandvars(file_path)).expanduser()
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Input file not found: {path}")
    return path.read_text(encoding="utf-8")


def normalize_user_path_input(raw_path: str) -> str:
    """Normalize pasted/dragged path text from terminal input."""
    path = raw_path.strip()
    if not path:
        return path

    # Handle wrapped quotes: "/path/with space/file.txt"
    if len(path) >= 2 and path[0] == path[-1] and path[0] in {"'", '"'}:
        path = path[1:-1].strip()

    # Handle escaped spaces/backslashes from drag-and-drop text, e.g. /A\ B/file.txt
    if "\\" in path or "'" in path or '"' in path:
        try:
            parts = shlex.split(path)
            if len(parts) == 1:
                path = parts[0]
        except ValueError:
            pass

    return path


def normalize_action_item(item: Any) -> dict[str, str]:
    """Normalize one action item dictionary for stable downstream rendering."""
    if not isinstance(item, dict):
        item = {}

    return {
        "task": str(item.get("task") or "Unclear task (needs review)").strip(),
        "owner": str(item.get("owner") or "Unspecified (needs clarification)").strip(),
        "deadline": str(item.get("deadline") or "Not specified").strip(),
        "priority": str(item.get("priority") or "Medium").strip(),
        "confidence": str(item.get("confidence") or "Low").strip(),
        "notes": str(item.get("notes") or "").strip(),
    }


def normalize_output_language(raw_language: str | None) -> str:
    """Normalize output language selector to 'english' or 'chinese'."""
    if not raw_language:
        return "english"
    value = str(raw_language).strip().lower()
    if value in {"chinese", "zh", "zh-cn", "cn", "中文"}:
        return "chinese"
    return "english"


def normalize_result(data: Any, raw_output: str | None = None) -> dict[str, Any]:
    """Normalize model output into a stable JSON shape."""
    obj: dict[str, Any] = data if isinstance(data, dict) else {}

    action_items_raw = obj.get("action_items")
    action_items: list[dict[str, str]] = []
    if isinstance(action_items_raw, list):
        action_items = [normalize_action_item(item) for item in action_items_raw]

    warnings_raw = obj.get("warnings")
    warnings: list[str] = []
    if isinstance(warnings_raw, list):
        warnings = [str(w).strip() for w in warnings_raw if str(w).strip()]

    result: dict[str, Any] = {
        "action_items": action_items,
        "summary": str(obj.get("summary") or "").strip(),
        "natural_language_summary": str(obj.get("natural_language_summary") or "").strip(),
        "warnings": warnings,
    }

    if raw_output is not None:
        result["raw_output"] = raw_output

    return result


def extract_json_candidates(text: str) -> list[str]:
    """Extract possible JSON snippets from mixed model output."""
    candidates: list[str] = []
    stripped = text.strip()
    if stripped:
        candidates.append(stripped)

    fenced_blocks = re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    for block in fenced_blocks:
        block = block.strip()
        if block:
            candidates.append(block)

    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
        candidates.append(text[first_brace : last_brace + 1].strip())

    # Balanced top-level JSON object extraction.
    depth = 0
    start = -1
    in_string = False
    escaped = False
    for idx, ch in enumerate(text):
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            if depth == 0:
                start = idx
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start != -1:
                candidates.append(text[start : idx + 1].strip())
                start = -1

    # Deduplicate while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)

    return unique


def parse_model_output(raw_text: str) -> dict[str, Any]:
    """Parse model output into structured JSON with robust fallbacks."""
    if not raw_text or not raw_text.strip():
        return {
            "action_items": [],
            "summary": "Model returned empty output.",
            "natural_language_summary": "",
            "warnings": ["Empty response from model; manual review required."],
            "raw_output": raw_text,
        }

    for candidate in extract_json_candidates(raw_text):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return normalize_result(parsed, raw_output=raw_text)

    return {
        "action_items": [],
        "summary": "Failed to parse model output as JSON.",
        "natural_language_summary": "",
        "warnings": [
            "Model output was not valid JSON; showing raw output for manual review."
        ],
        "raw_output": raw_text,
    }


def call_gemini(
    client: Any,
    genai_sdk: Any,
    transcript: str,
    system_prompt: str,
    model_name: str,
    output_language: str = "english",
) -> dict[str, Any]:
    """Call Gemini and return normalized extraction output."""
    language = normalize_output_language(output_language)
    if language == "chinese":
        language_instruction = (
            "OUTPUT LANGUAGE REQUIREMENT: Use Simplified Chinese for all natural-language "
            "fields in JSON (task, owner, deadline, priority, confidence, notes, summary, "
            "natural_language_summary, warnings). Keep JSON keys unchanged."
        )
    else:
        language_instruction = (
            "OUTPUT LANGUAGE REQUIREMENT: Use English for all natural-language fields in JSON."
        )

    prompt_text = f"{language_instruction}\n\nTranscript:\n{transcript}"

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt_text,
            config=genai_sdk.types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.2,
            ),
        )
    except Exception as exc:  # pylint: disable=broad-except
        return {
            "action_items": [],
            "summary": "Gemini API call failed.",
            "natural_language_summary": "",
            "warnings": [f"API error: {exc}"],
            "raw_output": "",
        }

    raw_text = (response.text or "").strip()
    return parse_model_output(raw_text)


def render_markdown_todo(
    result: dict[str, Any], source: str, output_language: str = "english"
) -> str:
    """Render extraction result as a markdown todo list."""
    language = normalize_output_language(output_language)
    extracted_on = date.today().isoformat()
    summary = (result.get("natural_language_summary") or result.get("summary") or "").strip()

    if language == "chinese":
        title = "# LectureFlow - 行动事项"
        source_label = "来源"
        extracted_label = "提取日期"
        summary_label = "摘要"
        action_items_label = "## 行动事项"
        no_items_line = "- [ ] **未发现明确行动事项** - 全体 - 未说明"
        priority_label = "优先级"
        confidence_label = "置信度"
        warnings_label = "## 备注与警告"
        none_label = "- 无"
        raw_label = "## 模型原始输出（兜底）"
        if source == "Pasted Text":
            source = "粘贴文本"
        elif source == "File Input":
            source = "文件输入"
    else:
        title = "# LectureFlow - Action Items"
        source_label = "Source"
        extracted_label = "Extracted"
        summary_label = "Summary"
        action_items_label = "## Action Items"
        no_items_line = "- [ ] **No explicit action items found** - Everyone - Not specified"
        priority_label = "Priority"
        confidence_label = "Confidence"
        warnings_label = "## Notes & Warnings"
        none_label = "- None"
        raw_label = "## Raw Model Output (Fallback)"

    lines: list[str] = [title, "", f"> **{source_label}:** {source}", f"> **{extracted_label}:** {extracted_on}"]

    if summary:
        lines.append(f"> **{summary_label}:** {summary}")

    lines.extend(["", "---", "", action_items_label, ""])

    items = result.get("action_items", [])
    if not isinstance(items, list) or not items:
        lines.append(no_items_line)
    else:
        for raw_item in items:
            item = normalize_action_item(raw_item)
            task = item["task"]
            owner = item["owner"]
            deadline = item["deadline"]
            confidence = item["confidence"]
            notes = item["notes"]
            priority = item["priority"]

            lines.append(f"- [ ] **{task}** - {owner} - {deadline}")
            if notes:
                lines.append(f"  - {notes}")
            lines.append(f"  - {priority_label}: {priority}")
            lines.append(f"  - {confidence_label}: {confidence}")
            lines.append("")

    warnings = result.get("warnings", [])
    lines.extend(["---", "", warnings_label, ""])
    if isinstance(warnings, list) and warnings:
        for warning in warnings:
            lines.append(f"- {warning}")
    else:
        lines.append(none_label)

    raw_output = str(result.get("raw_output") or "").strip()
    if raw_output and str(result.get("summary", "")).startswith("Failed to parse"):
        lines.extend(["", raw_label, "", "```text", raw_output, "```"])

    return "\n".join(lines).rstrip() + "\n"


def format_single_output(
    result: dict[str, Any], output_format: str, source: str, output_language: str = "english"
) -> tuple[str, str]:
    """Return (content, file_extension_hint) for single transcript mode."""
    if output_format == "json":
        return json.dumps(result, indent=2, ensure_ascii=False) + "\n", ".json"
    return render_markdown_todo(result, source, output_language=output_language), ".md"


def write_output(path: str, content: str) -> None:
    """Write output text to disk."""
    Path(path).expanduser().write_text(content, encoding="utf-8")


def resolve_default_save_dir() -> Path:
    """Resolve default save directory (prefer ~/Downloads, fallback to cwd)."""
    downloads = Path.home() / DEFAULT_DOWNLOADS_DIRNAME
    try:
        downloads.mkdir(parents=True, exist_ok=True)
        if downloads.is_dir():
            return downloads
    except OSError:
        pass
    return Path.cwd()


def pick_available_port(host: str, preferred_port: int) -> int:
    """Return preferred port if available, otherwise ask OS for a free port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, preferred_port))
            return preferred_port
        except OSError:
            sock.bind((host, 0))
            return int(sock.getsockname()[1])


def render_web_page(
    markdown: str = "",
    saved_path: str = "",
    info_message: str = "",
    error_message: str = "",
) -> str:
    """Render a minimal HTML UI for web-mode interaction."""
    escaped_markdown = html.escape(markdown)
    escaped_saved_path = html.escape(saved_path)
    escaped_info = html.escape(info_message)
    escaped_error = html.escape(error_message)

    info_block = (
        f"<p class='info'>Saved to: <code>{escaped_saved_path}</code></p>"
        if saved_path
        else ""
    )
    if escaped_info:
        info_block += f"<p class='info'>{escaped_info}</p>"

    error_block = f"<p class='error'>{escaped_error}</p>" if escaped_error else ""
    result_block = (
        f"""
        <section class="result">
          <h2>Generated Markdown</h2>
          {info_block}
          {error_block}
          <textarea readonly>{escaped_markdown}</textarea>
        </section>
        """
        if (markdown or saved_path or error_message or info_message)
        else ""
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>LectureFlow Web UI</title>
  <style>
    :root {{
      --bg: #f7f7ef;
      --card: #fffdf6;
      --ink: #13233a;
      --accent: #1f6f5f;
      --border: #d7d1c6;
    }}
    body {{
      margin: 0;
      background: radial-gradient(circle at 15% 10%, #efe8da, var(--bg));
      font-family: 'Avenir Next', 'Segoe UI', sans-serif;
      color: var(--ink);
      line-height: 1.45;
    }}
    .wrap {{
      max-width: 980px;
      margin: 24px auto;
      padding: 0 16px;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 20px;
      box-shadow: 0 12px 30px rgba(19, 35, 58, 0.08);
    }}
    h1 {{
      margin: 0 0 12px;
      font-size: 28px;
      letter-spacing: .3px;
    }}
    p {{
      margin: 0 0 12px;
    }}
    label {{
      display: block;
      font-weight: 600;
      margin: 12px 0 6px;
    }}
    textarea, input[type="text"], input[type="file"] {{
      width: 100%;
      box-sizing: border-box;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 10px;
      font-size: 14px;
      background: #fff;
    }}
    textarea {{
      min-height: 180px;
      resize: vertical;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    }}
    .row {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }}
    @media (max-width: 760px) {{
      .row {{ grid-template-columns: 1fr; }}
    }}
    button {{
      margin-top: 14px;
      border: 0;
      border-radius: 10px;
      background: var(--accent);
      color: white;
      font-size: 15px;
      padding: 10px 16px;
      cursor: pointer;
    }}
    .hint {{
      color: #4a5a70;
      font-size: 13px;
      margin-top: 6px;
    }}
    .result {{
      margin-top: 16px;
      border-top: 1px dashed var(--border);
      padding-top: 14px;
    }}
    .info {{
      background: #e7f5ef;
      border: 1px solid #9fd8c2;
      border-radius: 8px;
      padding: 8px 10px;
      color: #144a3b;
      margin: 8px 0;
    }}
    .error {{
      background: #fce8e8;
      border: 1px solid #ef9a9a;
      border-radius: 8px;
      padding: 8px 10px;
      color: #a32626;
      margin: 8px 0;
    }}
    code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>LectureFlow Web</h1>
      <p>Upload transcript file or paste transcript text, then generate action-item Markdown.</p>
      <form method="post" action="/extract" enctype="multipart/form-data">
        <label for="transcript_file">Upload Transcript File (.txt/.md)</label>
        <input id="transcript_file" name="transcript_file" type="file" />
        <p class="hint">If both file and pasted text are provided, pasted text is used first.</p>

        <label for="transcript_text">Or Paste Transcript Text</label>
        <textarea id="transcript_text" name="transcript_text" placeholder="Paste transcript here..."></textarea>

        <label for="transcript_path">Optional: Local File Path</label>
        <input id="transcript_path" name="transcript_path" type="text" placeholder="/path/to/transcript.txt" />

        <div class="row">
          <div>
            <label for="source_name">Source Name (optional)</label>
            <input id="source_name" name="source_name" type="text" placeholder="Lecture 1 Transcript" />
          </div>
          <div>
            <label for="output_name">Output Markdown Filename</label>
            <input id="output_name" name="output_name" type="text" value="{DEFAULT_MD_FILENAME}" />
          </div>
        </div>

        <button type="submit">Generate & Save Markdown</button>
      </form>
      {result_block}
    </div>
  </div>
</body>
</html>
"""


def render_web_page_modern(
    markdown: str = "",
    saved_path: str = "",
    info_message: str = "",
    error_message: str = "",
    default_save_dir: str = "",
) -> str:
    """Render modern split-layout UI with async markdown preview."""
    initial_md = json.dumps(markdown)
    initial_saved = json.dumps(saved_path)
    initial_info = json.dumps(info_message)
    initial_error = json.dumps(error_message)
    initial_default_save_dir = json.dumps(default_save_dir)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>LectureFlow Web UI</title>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <style>
    :root {{
      --bg: #f5f5f7;
      --card: rgba(255, 255, 255, 0.78);
      --ink: #1d1d1f;
      --accent: #0071e3;
      --accent-hover: #0077ed;
      --border: rgba(0, 0, 0, 0.08);
      --muted: #6e6e73;
    }}
    body {{
      margin: 0;
      background: radial-gradient(1200px 600px at -10% -20%, #ffffff 0%, var(--bg) 55%);
      font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', sans-serif;
      color: var(--ink);
      line-height: 1.45;
    }}
    .wrap {{
      max-width: 1200px;
      margin: 22px auto;
      padding: 0 16px;
    }}
    .layout {{
      display: grid;
      grid-template-columns: 360px 1fr;
      gap: 16px;
      min-height: calc(100vh - 60px);
    }}
    .panel {{
      background: var(--card);
      border: 1px solid var(--border);
      backdrop-filter: saturate(180%) blur(18px);
      -webkit-backdrop-filter: saturate(180%) blur(18px);
      border-radius: 18px;
      padding: 18px;
      box-shadow: 0 10px 28px rgba(0, 0, 0, 0.08);
    }}
    h1 {{
      margin: 0 0 10px;
      font-size: 25px;
      letter-spacing: -0.01em;
    }}
    h2 {{
      margin: 0 0 8px;
      font-size: 19px;
      letter-spacing: -0.01em;
    }}
    p {{ margin: 0 0 12px; }}
    label {{
      display: block;
      font-weight: 600;
      margin: 12px 0 6px;
    }}
    textarea, input[type="text"], input[type="file"] {{
      width: 100%;
      box-sizing: border-box;
      border: 1px solid #d2d2d7;
      border-radius: 12px;
      padding: 10px;
      font-size: 14px;
      background: rgba(255, 255, 255, 0.92);
      transition: border-color .2s ease, box-shadow .2s ease;
    }}
    textarea:focus, input[type="text"]:focus, input[type="file"]:focus {{
      border-color: #86b7fe;
      box-shadow: 0 0 0 3px rgba(0, 113, 227, 0.18);
      outline: none;
    }}
    textarea {{
      min-height: 160px;
      resize: vertical;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    }}
    .row {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }}
    @media (max-width: 760px) {{
      .row {{ grid-template-columns: 1fr; }}
      .layout {{ grid-template-columns: 1fr; }}
    }}
    button {{
      margin-top: 14px;
      border: 0;
      border-radius: 999px;
      background: var(--accent);
      color: white;
      font-size: 15px;
      font-weight: 600;
      padding: 10px 18px;
      cursor: pointer;
      transition: background-color .2s ease, transform .08s ease;
    }}
    button:hover {{ background: var(--accent-hover); }}
    button:active {{ transform: translateY(1px); }}
    .hint {{
      color: var(--muted);
      font-size: 13px;
      margin-top: 6px;
    }}
    .info {{
      background: #e7f5ef;
      border: 1px solid #9fd8c2;
      border-radius: 8px;
      padding: 8px 10px;
      color: #144a3b;
      margin: 8px 0;
    }}
    .error {{
      background: #fce8e8;
      border: 1px solid #ef9a9a;
      border-radius: 8px;
      padding: 8px 10px;
      color: #a32626;
      margin: 8px 0;
    }}
    code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    }}
    .right-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
      margin-bottom: 10px;
    }}
    .status {{
      font-size: 13px;
      padding: 4px 8px;
      border-radius: 999px;
      background: #ececf1;
      color: #3a3a3c;
    }}
    .status.generating {{
      background: #fff2de;
      color: #8f4f00;
      font-weight: 600;
    }}
    #preview {{
      border: 1px solid #d2d2d7;
      border-radius: 12px;
      padding: 14px;
      min-height: 300px;
      overflow: auto;
      background: rgba(255, 255, 255, 0.92);
    }}
    #raw_md {{
      margin-top: 10px;
      width: 100%;
      min-height: 120px;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      border: 1px solid #d2d2d7;
      border-radius: 12px;
      padding: 10px;
      box-sizing: border-box;
    }}
    .save-default {{
      margin-top: 8px;
      color: var(--muted);
      font-size: 12px;
    }}
    .lang-tabs {{
      display: inline-flex;
      border: 1px solid #d2d2d7;
      border-radius: 999px;
      overflow: hidden;
      background: rgba(255, 255, 255, 0.92);
      margin-top: 6px;
    }}
    .lang-tabs input[type="radio"] {{
      display: none;
    }}
    .lang-tabs label {{
      margin: 0;
      padding: 8px 14px;
      font-size: 13px;
      font-weight: 600;
      color: #515154;
      cursor: pointer;
      user-select: none;
    }}
    .lang-tabs input[type="radio"]:checked + label {{
      background: var(--accent);
      color: #fff;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="layout">
      <section class="panel">
        <h1>LectureFlow Web</h1>
        <p>Upload transcript or paste text, then generate Todo Markdown.</p>
        <form id="extract_form" method="post" action="/extract" enctype="multipart/form-data">
          <label for="transcript_file">Upload Transcript File (.txt/.md)</label>
          <input id="transcript_file" name="transcript_file" type="file" />
          <p class="hint">If both file and pasted text are provided, pasted text wins.</p>

          <label for="transcript_text">Or Paste Transcript Text</label>
          <textarea id="transcript_text" name="transcript_text" placeholder="Paste transcript here..."></textarea>

          <label for="transcript_path">Optional: Local File Path</label>
          <input id="transcript_path" name="transcript_path" type="text" placeholder="/path/to/transcript.txt" />

          <label>Output Language</label>
          <div class="lang-tabs" role="tablist" aria-label="Output Language">
            <input id="output_lang_en" type="radio" name="output_language" value="english" checked />
            <label for="output_lang_en">English</label>
            <input id="output_lang_zh" type="radio" name="output_language" value="chinese" />
            <label for="output_lang_zh">中文</label>
          </div>

          <div class="row">
            <div>
              <label for="source_name">Source Name (optional)</label>
              <input id="source_name" name="source_name" type="text" placeholder="Lecture 1 Transcript" />
            </div>
            <div>
              <label for="output_name">Output Markdown Filename</label>
              <input id="output_name" name="output_name" type="text" value="{DEFAULT_MD_FILENAME}" />
            </div>
          </div>
          <p class="save-default">Default save folder: <code id="default_save_dir_label"></code></p>

          <button id="submit_btn" type="submit">Generate & Save Markdown</button>
        </form>
      </section>

      <section class="panel">
        <div class="right-header">
          <h2>Markdown Preview</h2>
          <span id="status" class="status">Ready</span>
        </div>
        <div id="message_info"></div>
        <div id="message_error"></div>
        <article id="preview"><p class="hint">Result will appear here.</p></article>
        <label for="raw_md">Raw Markdown</label>
        <textarea id="raw_md" readonly placeholder="Generated markdown will appear here..."></textarea>
      </section>
    </div>
  </div>

  <script>
    const initialMd = {initial_md};
    const initialSaved = {initial_saved};
    const initialInfo = {initial_info};
    const initialError = {initial_error};
    const defaultSaveDir = {initial_default_save_dir};

    function escapeHtml(text) {{
      return String(text)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;');
    }}

    function renderMarkdown(md) {{
      const preview = document.getElementById('preview');
      const rawMd = document.getElementById('raw_md');
      rawMd.value = md || '';
      if (!md) {{
        preview.innerHTML = '<p class="hint">Result will appear here.</p>';
        return;
      }}
      if (window.marked && typeof window.marked.parse === 'function') {{
        preview.innerHTML = window.marked.parse(md);
      }} else {{
        preview.innerHTML = '<pre>' + escapeHtml(md) + '</pre>';
      }}
    }}

    function setStatus(text, isGenerating=false) {{
      const status = document.getElementById('status');
      status.textContent = text;
      status.className = isGenerating ? 'status generating' : 'status';
    }}

    function setMessage(infoHtml, errorHtml) {{
      const infoEl = document.getElementById('message_info');
      const errEl = document.getElementById('message_error');
      infoEl.innerHTML = infoHtml ? `<p class="info">${{infoHtml}}</p>` : '';
      errEl.innerHTML = errorHtml ? `<p class="error">${{errorHtml}}</p>` : '';
    }}

    if (initialMd || initialSaved || initialInfo || initialError) {{
      const infoHtml = initialSaved
        ? `Saved to: <code>${{escapeHtml(initialSaved)}}</code><br>${{escapeHtml(initialInfo || '')}}`
        : (initialInfo ? escapeHtml(initialInfo) : '');
      setMessage(infoHtml, initialError ? escapeHtml(initialError) : '');
      renderMarkdown(initialMd || '');
    }}

    const defaultDirLabel = document.getElementById('default_save_dir_label');
    defaultDirLabel.textContent = defaultSaveDir || 'Current directory';

    const form = document.getElementById('extract_form');
    const submitBtn = document.getElementById('submit_btn');
    form.addEventListener('submit', async (event) => {{
      event.preventDefault();
      setStatus('GENERATING...', true);
      submitBtn.disabled = true;
      setMessage('', '');
      try {{
        const response = await fetch('/extract', {{
          method: 'POST',
          body: new FormData(form),
        }});
        const data = await response.json();
        if (!response.ok || !data.ok) {{
          setStatus('Failed');
          setMessage('', escapeHtml(data.error || 'Unknown error'));
          renderMarkdown('');
          return;
        }}
        const infoHtml = `Saved to: <code>${{escapeHtml(data.saved_path || '')}}</code><br>${{escapeHtml(data.info || '')}}`;
        setMessage(infoHtml, '');
        renderMarkdown(data.markdown || '');
        setStatus('Done');
      }} catch (error) {{
        setStatus('Failed');
        setMessage('', escapeHtml(String(error)));
        renderMarkdown('');
      }} finally {{
        submitBtn.disabled = false;
      }}
    }});
  </script>
</body>
</html>
"""


def make_web_handler(
    client: Any,
    genai_sdk: Any,
    system_prompt: str,
    model_name: str,
    save_dir: Path,
) -> type[BaseHTTPRequestHandler]:
    """Create a request handler class bound to runtime dependencies."""

    class LectureFlowWebHandler(BaseHTTPRequestHandler):
        """HTTP handler for LectureFlow web mode."""

        def _send_html(self, page: str, status_code: int = 200) -> None:
            encoded = page.encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _send_json(self, payload: dict[str, Any], status_code: int = 200) -> None:
            encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _get_field_text(self, form: cgi.FieldStorage, name: str) -> str:
            field = form[name] if name in form else None
            if field is None:
                return ""
            if isinstance(field, list):
                field = field[0]
            if getattr(field, "filename", ""):
                return ""
            value = getattr(field, "value", "")
            return str(value).strip()

        def _extract_transcript_from_form(self, form: cgi.FieldStorage) -> tuple[str, str]:
            pasted_text = self._get_field_text(form, "transcript_text")
            source_name = self._get_field_text(form, "source_name")
            if pasted_text:
                return pasted_text, source_name or "Pasted Text"

            uploaded = form["transcript_file"] if "transcript_file" in form else None
            if isinstance(uploaded, list):
                uploaded = uploaded[0]
            if uploaded is not None and getattr(uploaded, "filename", "") and uploaded.file:
                raw = uploaded.file.read()
                if isinstance(raw, bytes):
                    text = raw.decode("utf-8", errors="replace")
                else:
                    text = str(raw)
                return text.strip(), source_name or str(uploaded.filename)

            raw_path = self._get_field_text(form, "transcript_path")
            if raw_path:
                path = normalize_user_path_input(raw_path)
                transcript = read_text_file(path)
                source = source_name or Path(path).expanduser().name or "File Input"
                return transcript.strip(), source

            raise ValueError("Please upload a file, paste transcript text, or provide a file path.")

        def do_GET(self) -> None:
            """Render the main form."""
            if self.path not in {"/", ""}:
                self._send_html(
                    render_web_page_modern(
                        error_message="Page not found.",
                        default_save_dir=str(save_dir),
                    ),
                    status_code=404,
                )
                return
            self._send_html(render_web_page_modern(default_save_dir=str(save_dir)))

        def do_POST(self) -> None:
            """Process extraction request and return JSON for async UI update."""
            if self.path != "/extract":
                self._send_json({"ok": False, "error": "Page not found."}, status_code=404)
                return

            try:
                form = cgi.FieldStorage(
                    fp=self.rfile,
                    headers=self.headers,
                    environ={
                        "REQUEST_METHOD": "POST",
                        "CONTENT_TYPE": self.headers.get("Content-Type", ""),
                    },
                )
                transcript, source = self._extract_transcript_from_form(form)
                if not transcript:
                    raise ValueError("Transcript is empty after reading input.")
                output_language = normalize_output_language(
                    self._get_field_text(form, "output_language")
                )

                output_name = self._get_field_text(form, "output_name") or DEFAULT_MD_FILENAME
                output_name = Path(output_name).name or DEFAULT_MD_FILENAME
                output_path = save_dir / output_name

                result = call_gemini(
                    client,
                    genai_sdk,
                    transcript,
                    system_prompt,
                    model_name,
                    output_language=output_language,
                )
                markdown = render_markdown_todo(result, source, output_language=output_language)
                write_output(str(output_path), markdown)

                self._send_json(
                    {
                        "ok": True,
                        "markdown": markdown,
                        "saved_path": str(output_path),
                        "output_language": output_language,
                        "info": "Markdown generated and saved to default Downloads folder.",
                    },
                    status_code=200,
                )
            except Exception as exc:  # pylint: disable=broad-except
                self._send_json({"ok": False, "error": str(exc)}, status_code=400)

        def log_message(self, fmt: str, *args: Any) -> None:
            """Keep server logs concise."""
            print(f"[web] {self.address_string()} - {fmt % args}")

    return LectureFlowWebHandler


def run_web_mode(
    client: Any,
    genai_sdk: Any,
    system_prompt: str,
    model_name: str,
    port: int,
) -> None:
    """Run local web server for transcript interaction."""
    host = DEFAULT_WEB_HOST
    chosen_port = pick_available_port(host, port)
    save_dir = resolve_default_save_dir()
    handler_cls = make_web_handler(client, genai_sdk, system_prompt, model_name, save_dir)
    server = ThreadingHTTPServer((host, chosen_port), handler_cls)
    url = f"http://{host}:{chosen_port}"

    print("\nLectureFlow Web UI is running.")
    print(f"Open in browser: {url}")
    print(f"Generated markdown will be saved to: {save_dir / DEFAULT_MD_FILENAME}")
    print("Press Ctrl+C to stop.\n")

    try:
        webbrowser.open(url)
    except Exception:
        pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nWeb server stopped.")
    finally:
        server.server_close()


def summarize_case(case: dict[str, Any], result: dict[str, Any]) -> None:
    """Print concise eval-case summary to terminal."""
    print("\n" + "=" * 60)
    print(f"Case {case.get('id')} [{case.get('type')}]: {case.get('description')}")
    print("=" * 60)
    count = len(result.get("action_items", []))
    print(f"Extracted {count} action item(s)")
    for warning in result.get("warnings", []):
        print(f"Warning: {warning}")


def run_eval_mode(
    args: argparse.Namespace,
    client: Any,
    genai_sdk: Any,
    system_prompt: str,
) -> list[dict[str, Any]]:
    """Run evaluation over all test cases and return JSON-compatible results."""
    eval_cases_raw = json.loads(read_text_file(args.eval))
    if not isinstance(eval_cases_raw, list):
        raise ValueError("Eval file must contain a JSON array of test cases.")

    results: list[dict[str, Any]] = []
    for case_raw in eval_cases_raw:
        case = case_raw if isinstance(case_raw, dict) else {}
        transcript = str(case.get("input") or "")
        result = call_gemini(client, genai_sdk, transcript, system_prompt, args.model)
        summarize_case(case, result)

        results.append(
            {
                "case_id": case.get("id"),
                "case_type": case.get("type"),
                "description": case.get("description"),
                "expected": case.get("expected_behavior"),
                "actual_output": result,
            }
        )

    return results


def ask_input_mode() -> str:
    """Ask user to choose transcript input mode in interactive flow."""
    print("请选择输入方式：")
    print("  [1] 直接粘贴课堂转写文本")
    print("  [2] 上传文本文件路径（可把文件拖到终端）")
    while True:
        choice = input("请输入 1 或 2: ").strip()
        if choice in {"1", "2"}:
            return choice
        print("请输入 1 或 2。")


def collect_pasted_transcript() -> str:
    """Collect multiline transcript from stdin until END line."""
    print("\n请粘贴转写文本。完成后输入 END 并回车结束。")
    lines: list[str] = []
    while True:
        line = input()
        if line.strip() == "END":
            break
        lines.append(line)

    transcript = "\n".join(lines).strip()
    if not transcript:
        raise ValueError("未读取到文本内容。")
    return transcript


def prompt_transcript_path() -> tuple[str, str]:
    """Prompt for transcript file path and return (text, source_label)."""
    while True:
        raw_path = input("请输入 .txt/.md 文件路径（或输入 q 退出）: ").strip()
        path = normalize_user_path_input(raw_path)
        if path.lower() == "q":
            raise ValueError("用户取消了文件输入。")
        if not path:
            print("路径不能为空，请重试。")
            continue
        try:
            transcript = read_text_file(path)
        except FileNotFoundError as exc:
            print(f"{exc}，请重试。")
            continue
        source = Path(path).expanduser().name or "Input File"
        return transcript, source


def ask_yes_no(prompt: str) -> bool:
    """Prompt for yes/no answer."""
    value = input(prompt).strip().lower()
    return value in {"y", "yes", "是", "好"}


def run_interactive_mode(
    client: Any,
    genai_sdk: Any,
    system_prompt: str,
    model_name: str,
    default_output_path: str | None = None,
) -> None:
    """Run interactive transcript processing mode."""
    print("\n================ LectureFlow Interactive Mode ================")
    print("你可以上传课堂录音转写文件，或直接粘贴文本。")
    print("系统会自动提取 Action Items，并输出 Markdown Todo List。\n")

    choice = ask_input_mode()
    if choice == "1":
        transcript = collect_pasted_transcript()
        source = "Interactive Input"
    else:
        transcript, source = prompt_transcript_path()

    result = call_gemini(client, genai_sdk, transcript, system_prompt, model_name)
    markdown = render_markdown_todo(result, source)

    print("\n" + markdown)

    if ask_yes_no("是否保存为 Markdown 文件？ [y/N]: "):
        suggested = default_output_path or "lectureflow_todo.md"
        output_path = input(f"输出路径 [{suggested}]: ").strip() or suggested
        write_output(output_path, markdown)
        print(f"已保存到: {output_path}")


def run_single_file_mode(
    args: argparse.Namespace,
    client: Any,
    genai_sdk: Any,
    system_prompt: str,
) -> None:
    """Run single-transcript mode from --input."""
    transcript = read_text_file(args.input)
    source = Path(args.input).expanduser().name or "Input File"
    result = call_gemini(client, genai_sdk, transcript, system_prompt, args.model)

    output_text, ext_hint = format_single_output(result, args.format, source)
    print(output_text, end="")

    if args.output:
        write_output(args.output, output_text)
        print(f"Saved to: {args.output}")
    else:
        # Helpful hint for markdown default path when user wants a file copy.
        if args.format == "markdown":
            print(f"\nHint: use --output lectureflow_todo{ext_hint} to save this result.")


def main() -> None:
    """Program entrypoint."""
    args = parse_args()

    api_key = resolve_api_key()
    if not api_key:
        print("Error: Please set GEMINI_API_KEY or GOOGLE_API_KEY.")
        print("Get a key at: https://aistudio.google.com/apikey")
        sys.exit(1)

    try:
        system_prompt = load_system_prompt(args.system_prompt)
    except Exception as exc:  # pylint: disable=broad-except
        print(f"Error loading system prompt: {exc}")
        sys.exit(1)

    try:
        client, genai_sdk = create_genai_client(api_key)
    except RuntimeError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    try:
        if args.eval:
            results = run_eval_mode(args, client, genai_sdk, system_prompt)
            rendered = json.dumps(results, indent=2, ensure_ascii=False) + "\n"
            if args.output:
                write_output(args.output, rendered)
                print(f"\nEvaluation results saved to: {args.output}")
            else:
                print(rendered, end="")
        elif args.input:
            run_single_file_mode(args, client, genai_sdk, system_prompt)
        else:
            run_web_mode(
                client=client,
                genai_sdk=genai_sdk,
                system_prompt=system_prompt,
                model_name=args.model,
                port=args.port,
            )
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(130)


if __name__ == "__main__":
    main()
