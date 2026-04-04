#!/usr/bin/env python3
"""
LectureFlow — Lecture Transcript to Action Items
A GenAI workflow that extracts structured action items from lecture transcripts.
Uses Google Gemini API for LLM processing.

Usage:
    python app.py --input <transcript_file> [--system-prompt <prompt_file>] [--output <output_file>] [--model <model_name>]

Examples:
    python app.py --input transcript.txt
    python app.py --input transcript.txt --system-prompt custom_prompt.txt --output results.json
    python app.py --eval eval_set.json --output eval_results.json
"""

import argparse
import json
import os
import sys
from google import genai

# ── Default system prompt (v3 — Final) ────────────────────────────────────────
DEFAULT_SYSTEM_PROMPT = """You are a precise task extraction assistant specialized in processing university lecture transcripts and meeting notes.

MISSION: Extract ONLY explicitly stated action items — tasks that someone is clearly expected to complete. Do not infer, assume, or create tasks from general discussion, explanations, or opinions.

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
  "warnings": ["List any ambiguities, unclear references, or items that need human review"]
}

RULES:
1. NEVER fabricate deadlines — if the speaker says "soon" or "whenever", mark deadline as approximate, do not invent a specific date.
2. NEVER assign ownership when the speaker is vague — use "Unspecified (needs clarification)" instead of guessing.
3. NEVER turn lecture content, explanations, or theoretical discussions into action items.
4. If the transcript contains NO actionable items, return an empty action_items array and explain in the summary.
5. Handle multilingual input gracefully — extract tasks regardless of language, and output consistently in English.
6. Add a "confidence" field: High if the task, owner, and deadline are all clear; Medium if one element is ambiguous; Low if multiple elements are unclear.
7. Use the "warnings" array to flag anything a human should double-check.

RESPOND ONLY WITH THE JSON OBJECT. No additional text before or after."""


def load_system_prompt(prompt_path: str | None) -> str:
    """Load system prompt from file or return default."""
    if prompt_path and os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return DEFAULT_SYSTEM_PROMPT


def extract_action_items(transcript: str, system_prompt: str, model_name: str) -> dict:
    """Send transcript to Gemini API and extract action items."""
    client = genai.Client()

    response = client.models.generate_content(
        model=model_name,
        contents=transcript,
        config=genai.types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.2,
        ),
    )

    # Parse the JSON response
    raw_text = response.text.strip()
    # Remove markdown code fences if present
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[1]
        if raw_text.endswith("```"):
            raw_text = raw_text[: raw_text.rfind("```")]
        raw_text = raw_text.strip()

    try:
        result = json.loads(raw_text)
    except json.JSONDecodeError:
        result = {
            "action_items": [],
            "summary": "Failed to parse model output as JSON.",
            "warnings": ["Raw model output was not valid JSON. Manual review needed."],
            "raw_output": raw_text,
        }

    return result


def run_single(args) -> dict:
    """Process a single transcript file."""
    with open(args.input, "r", encoding="utf-8") as f:
        transcript = f.read()

    system_prompt = load_system_prompt(args.system_prompt)
    result = extract_action_items(transcript, system_prompt, args.model)

    return result


def run_eval(args) -> list[dict]:
    """Run evaluation on all test cases in eval_set.json."""
    with open(args.eval, "r", encoding="utf-8") as f:
        eval_cases = json.load(f)

    system_prompt = load_system_prompt(args.system_prompt)
    results = []

    for case in eval_cases:
        print(f"\n{'='*60}")
        print(f"  Case {case['id']} [{case['type']}]: {case['description']}")
        print(f"{'='*60}")

        result = extract_action_items(case["input"], system_prompt, args.model)
        entry = {
            "case_id": case["id"],
            "case_type": case["type"],
            "description": case["description"],
            "expected": case["expected_behavior"],
            "actual_output": result,
        }
        results.append(entry)

        # Print summary
        n_items = len(result.get("action_items", []))
        print(f"  → Extracted {n_items} action item(s)")
        if result.get("warnings"):
            for w in result["warnings"]:
                print(f"  ⚠ {w}")

    return results


def display_result(result: dict) -> None:
    """Pretty-print a single extraction result to the console."""
    print(f"\n{'='*60}")
    print("  LECTUREFLOW — Extraction Results")
    print(f"{'='*60}\n")

    if result.get("summary"):
        print(f"Summary: {result['summary']}\n")

    items = result.get("action_items", [])
    if not items:
        print("  No action items found.\n")
    else:
        for i, item in enumerate(items, 1):
            print(f"  [{i}] {item.get('task', 'N/A')}")
            print(f"      Owner:      {item.get('owner', 'N/A')}")
            print(f"      Deadline:   {item.get('deadline', 'N/A')}")
            print(f"      Priority:   {item.get('priority', 'N/A')}")
            print(f"      Confidence: {item.get('confidence', 'N/A')}")
            if item.get("notes"):
                print(f"      Notes:      {item['notes']}")
            print()

    if result.get("warnings"):
        print("Warnings:")
        for w in result["warnings"]:
            print(f"  ⚠ {w}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="LectureFlow — Extract action items from lecture transcripts using Gemini AI"
    )
    parser.add_argument(
        "--input", type=str, help="Path to a transcript text file to process"
    )
    parser.add_argument(
        "--eval", type=str, help="Path to eval_set.json to run evaluation on all test cases"
    )
    parser.add_argument(
        "--system-prompt", type=str, default=None,
        help="Path to a custom system prompt file (overrides the built-in prompt)"
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Path to save JSON output (if omitted, prints to console)"
    )
    parser.add_argument(
        "--model", type=str, default="gemini-2.0-flash",
        help="Gemini model to use (default: gemini-2.0-flash)"
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.input and not args.eval:
        parser.error("Please provide either --input <file> or --eval <eval_set.json>")

    # Check for API key
    if not os.environ.get("GEMINI_API_KEY") and not os.environ.get("GOOGLE_API_KEY"):
        print("Error: Please set the GEMINI_API_KEY or GOOGLE_API_KEY environment variable.")
        print("  Get your free API key at: https://aistudio.google.com/apikey")
        sys.exit(1)

    # Set the API key for google-genai
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    os.environ["GOOGLE_API_KEY"] = api_key

    if args.eval:
        # Evaluation mode
        results = run_eval(args)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"\nEvaluation results saved to: {args.output}")
        else:
            print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        # Single transcript mode
        result = run_single(args)
        display_result(result)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()
