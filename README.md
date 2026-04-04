# LectureFlow — Lecture Transcript → Action Items

**HW2 | EN.705.603 Information Systems and AI | Johns Hopkins University**

**Author:** Jiayi Zhuo

## Overview

LectureFlow is a GenAI-powered tool that extracts structured action items from lecture transcripts and meeting notes. It uses the Google Gemini API (gemini-2.5-flash) to identify tasks, owners, deadlines, priorities, and confidence scores from unstructured text — turning messy lecture recordings into clean, actionable to-do lists rendered as Markdown checkboxes.

The tool supports three run modes: a local web UI for browser-based interaction, a command-line single-file mode, and a batch evaluation mode for systematic prompt testing. Output can be formatted as Markdown todo lists or structured JSON. Bilingual output (English / Chinese) is supported.

## Business Workflow

**Workflow:** Converting lecture transcripts into structured action items with `- [ ]` Markdown checkboxes.

**User:** University students and teaching assistants who attend lectures and need to track assignments, deadlines, and responsibilities.

**Input:** Raw text transcript from a lecture recording (supports multilingual input including English-Chinese mixed text).

**Output:** Markdown todo list with checkboxes (default) or structured JSON, each action item annotated with task description, owner, deadline, priority, confidence score, and contextual notes.

**Why automate:** Students spend significant time manually reviewing lecture recordings to extract homework assignments and deadlines. This workflow reduces a 30-minute review session to seconds, while catching items that manual note-taking might miss.

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

```bash
echo 'GEMINI_API_KEY=your-api-key-here' > .env
```

The app reads `GEMINI_API_KEY` or `GOOGLE_API_KEY` from environment variables first, then falls back to the `.env` file. The `.env` file supports `export` prefix, quoted values, and comment lines starting with `#`.

### Step 4: Run

See the **Usage** section below for all three run modes.

## Usage

### Mode 1: Web UI (default — no arguments)

```bash
python app.py
```

This launches a local web server at `http://127.0.0.1:8765` and opens it in your default browser. The web UI provides a split-layout interface where you can:

- Upload a `.txt` or `.md` transcript file
- Paste transcript text directly
- Provide a local file path
- Choose output language (English or Chinese)
- Set a custom source name and output filename

Generated Markdown is saved to `~/Downloads/` by default and previewed live in the browser via marked.js rendering.

Use `--port` to change the default port:

```bash
python app.py --port 9000
```

### Mode 2: Command-Line Single File

```bash
# Default output: Markdown todo list printed to terminal
python app.py --input transcript.txt

# Output as JSON instead
python app.py --input transcript.txt --format json

# Save output to a file
python app.py --input transcript.txt --output todo.md
python app.py --input transcript.txt --format json --output results.json
```

### Mode 3: Evaluation Mode

```bash
# Run eval and print results to terminal
python app.py --eval eval_set.json

# Run eval and save results to file
python app.py --eval eval_set.json --output eval_results.json
```

Evaluation mode processes all test cases in the JSON array, calls Gemini for each, and outputs structured JSON results comparing expected behavior against actual output. A summary is printed to the terminal for each case.

### Additional Options

```bash
# Use a custom system prompt file
python app.py --input transcript.txt --system-prompt custom_prompt.txt

# Use a different Gemini model
python app.py --input transcript.txt --model gemini-2.0-flash
```

### CLI Arguments Reference

| Argument | Description | Default |
|---|---|---|
| `--input FILE` | Path to transcript `.txt` file (single-file mode) | — |
| `--eval FILE` | Path to `eval_set.json` (evaluation mode) | — |
| `--format {markdown,json}` | Output format for single-file mode | `markdown` |
| `--output FILE` | Save output to file | — |
| `--system-prompt FILE` | Custom system prompt file | Built-in v3 prompt |
| `--model NAME` | Gemini model name | `gemini-2.5-flash` |
| `--port PORT` | Web UI port | `8765` |

## Project Structure

```
hw2-jiayizhuo/
├── README.md            # This file
├── app.py               # Main application (1380+ lines, three run modes)
├── prompts.md           # Prompt iteration log (3 versions)
├── eval_set.json        # Evaluation set (7 test cases)
├── report.md            # Final report
├── video_script.md      # Video walkthrough script
└── requirements.txt     # Python dependencies (google-genai==1.47.0)
```

## Video Walkthrough

[Video Link — TODO: Add after recording]
