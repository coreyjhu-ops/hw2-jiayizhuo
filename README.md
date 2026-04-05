# NoteFlow — Meeting & Lecture Transcript → Action Items

**HW2 | Information Systems and AI | Johns Hopkins University**

**Author:** Jiayi Zhuo

## Overview

NoteFlow is a GenAI-powered tool that extracts structured action items from business meeting and lecture transcripts. It uses the Google Gemini API (gemini-2.5-flash) to identify tasks, owners, deadlines, priorities, and confidence scores from unstructured spoken text — turning messy recordings into clean, actionable to-do lists rendered as Markdown checkboxes.

The tool supports two modes: **Meeting mode** for business meetings, team standups, client calls, and research RA meetings (with enhanced sensitivity to business time shorthand like EOD, EOW, Q2, sprint end), and **Lecture mode** for academic transcripts (homework assignments, exam dates, in-class tasks). Three run modes are available: a local web UI for browser-based interaction, a command-line single-file mode, and a batch evaluation mode for systematic prompt testing.

## Business Workflow

**Workflow:** Converting spoken meeting and lecture transcripts into structured, reviewable action item lists.

**Users:** Knowledge workers, project managers, research assistants, and students who attend meetings or lectures and need to track assignments, deadlines, and responsibilities without manually scanning long recordings.

**Input:** Raw text transcript from a meeting or lecture recording (supports multilingual input including English-Chinese mixed text).

**Output:** Markdown todo list with checkboxes (`- [ ]`) and a timeline summary table, each action item annotated with task description, owner, deadline, priority, confidence score, and contextual notes. A time_references section captures all explicit time expressions from the transcript.

**Why automate:** Manually reviewing a 60-minute meeting recording to extract action items can take 20-30 minutes and still miss items buried in discussion. NoteFlow reduces this to seconds, produces a structured output ready to copy into any Markdown-compatible task manager (Notion, Obsidian, GitHub Issues), and flags ambiguities that require human review rather than silently guessing.

## Setup & Reproduction Guide

### Prerequisites

- Python 3.10 or higher
- A Google Gemini API key (free tier available)

### Step 1: Clone the Repository

```bash
git clone https://github.com/coreyjhu-ops/hw2-jiayizhuo.git
cd hw2-jiayizhuo
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

This installs the only third-party dependency: `google-genai==1.47.0`.

### Step 3: Configure API Key

Get a free Gemini API key at: https://aistudio.google.com/apikey

Then configure it using **one** of these methods:

**Option A — Environment variable (recommended for quick use):**

```bash
export GEMINI_API_KEY="your-api-key-here"
```

**Option B — `.env` file (recommended for persistent use):**

Create a `.env` file in the project root directory:

```
GEMINI_API_KEY=your-api-key-here
```

The app reads `GEMINI_API_KEY` or `GOOGLE_API_KEY` from environment variables first, then falls back to the `.env` file. The `.env` file supports `export` prefix, quoted values, and comment lines starting with `#`.

### Step 4: Run

See the **Usage** section below for all three run modes.

## Usage

### Mode 1: Web UI (default — no arguments)

```bash
python app.py
```

This launches a local web server at `http://127.0.0.1:8765` and opens it in your default browser. The split-layout web UI allows you to:

- Select **Meeting** or **Lecture** mode via tab (different system prompt per mode)
- Upload a `.txt` or `.md` transcript file, paste text, or provide a local path
- Choose output language (English or Chinese)
- Preview Markdown output live in the browser
- Save results automatically to `~/Downloads/`

### Mode 2: Command-Line Single File

```bash
# Meeting mode (default), Markdown output
python app.py --input transcript.txt

# Lecture mode
python app.py --input transcript.txt --mode lecture

# JSON output
python app.py --input transcript.txt --format json

# Save to file
python app.py --input transcript.txt --output todo.md
```

### Mode 3: Evaluation Mode

```bash
# Run all 9 eval cases and print results
python app.py --eval eval_set.json

# Save results to file
python app.py --eval eval_set.json --output eval_results.json --mode meeting
```

### CLI Arguments Reference

| Argument | Description | Default |
|---|---|---|
| `--input FILE` | Path to transcript `.txt` file | — |
| `--eval FILE` | Path to `eval_set.json` | — |
| `--mode {meeting,lecture}` | Prompt mode | `meeting` |
| `--format {markdown,json}` | Output format for single-file mode | `markdown` |
| `--output FILE` | Save output to file | — |
| `--system-prompt FILE` | Override system prompt with custom file | — |
| `--model NAME` | Gemini model name | `gemini-2.5-flash` |
| `--port PORT` | Web UI port | `8765` |

## Project Structure

```
hw2-jiayizhuo/
├── README.md            # This file
├── app.py               # Main application (three run modes, two prompt modes)
├── prompts.md           # Prompt iteration log (v1 → v2 → v3 Lecture + Meeting variants)
├── eval_set.json        # Evaluation set (9 test cases: academic + business)
├── report.md            # Final report
└── requirements.txt     # Python dependencies (google-genai==1.47.0)
```

## Video Walkthrough

[Video Link — https://youtu.be/85sR_97pb18]
