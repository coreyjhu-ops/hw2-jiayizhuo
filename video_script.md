# Video Walkthrough Script (45-120 seconds)

> Camera on. Screen share on. Speak naturally. Short sentences. Keep energy up.

---

## Opening (10 sec)

"Hey, I'm Jiayi. This is my HW2 project — LectureFlow. It takes messy lecture transcripts and turns them into clean, actionable to-do lists using Gemini AI."

## Business Workflow (10 sec)

"The problem is simple. Students sit through long lectures. Important deadlines and assignments get buried in the discussion. LectureFlow fixes that — you paste in a transcript, and it pulls out every task, every deadline, every owner."

## Evaluation Set (10 sec)

"Here's my eval set — seven test cases. Normal lectures, edge cases like pure discussion with no tasks, and tricky ones with vague deadlines and bilingual input. This keeps evaluation fair and repeatable."

## Prompt Iteration (15 sec)

"I went through three versions of the system prompt. Version one was too loose — it hallucinated study tasks from lecture content. Version two added structure and JSON output. Version three added confidence scores, a warnings array, and rules for handling noisy transcripts with filler words. Each revision was driven by real output failures."

## Running the App (20 sec)

"Let me show the web UI. Just run `python app.py` with no arguments. It launches a local server and opens in your browser. I can paste a transcript here, pick English or Chinese output, and hit generate. The markdown preview shows up on the right — checkboxes, owners, deadlines, confidence scores. It also saves the file to my Downloads folder automatically."

"For command line: `python app.py --input transcript.txt` prints a markdown todo list. Add `--format json` for structured JSON output."

## GitHub Repo (10 sec)

"Here's my GitHub repo — clean commit history. README, eval set, app, prompts, and report. The README has a full reproduction guide — clone, pip install, set your API key, and run."

## Reflection (15 sec)

"One thing I learned — prompt engineering is really about debugging. You run tests, see where the model fails, and fix the instructions. The biggest surprise was how much real lecture transcripts differ from clean test data. Filler words, buried action items, relative dates — that's where the final two prompt rules came from. Thanks for watching."

---

**Total: ~90 seconds**
