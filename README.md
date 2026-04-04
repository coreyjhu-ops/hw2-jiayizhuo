# LectureFlow — Lecture Transcript → Action Items

**HW2 | EN.705.603 Information Systems and AI | Johns Hopkins University**

**Author:** Jiayi Zhuo

## Overview

LectureFlow is a GenAI-powered tool that extracts structured action items from lecture transcripts and meeting notes. It uses the Google Gemini API to identify tasks, owners, deadlines, and priorities from unstructured text — turning messy lecture recordings into clear, actionable to-do lists.

## Business Workflow

- **Workflow:** Converting lecture transcripts into structured action items
- **User:** University students and teaching assistants who attend lectures and need to track assignments, deadlines, and responsibilities
- **Input:** Raw text transcript from a lecture recording (can be multilingual)
- **Output:** Structured JSON containing action items with task descriptions, owners, deadlines, priorities, and confidence scores
- **Why automate:** Students spend significant time manually reviewing lecture recordings to extract homework assignments and deadlines. This workflow reduces a 30-minute review session to seconds, while catching items that manual note-taking might miss.

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set your Gemini API key (get one free at https://aistudio.google.com/apikey)
export GEMINI_API_KEY="your-api-key-here"
```

## Usage

```bash
# Process a single transcript
python app.py --input transcript.txt

# Process with a custom system prompt
python app.py --input transcript.txt --system-prompt custom_prompt.txt

# Run evaluation on all test cases
python app.py --eval eval_set.json --output eval_results.json

# Save output to a file
python app.py --input transcript.txt --output results.json
```

## Project Structure

```
hw2-jiayizhuo/
├── README.md            # This file
├── app.py               # Main application script
├── prompts.md           # Prompt iteration log (3 versions)
├── eval_set.json        # Evaluation set (7 test cases)
├── report.md            # Final report
└── requirements.txt     # Python dependencies
```

## Video Walkthrough

[Video Link — TODO: Add after recording]
