# NoteFlow: Automating Action Item Extraction from Meeting and Lecture Transcripts

## Business Use Case

Knowledge workers, researchers, and students routinely participate in meetings and lectures where critical action items — tasks, deadlines, and responsibilities — are stated verbally and then buried within lengthy discussion. The conventional response is manual note-taking or post-hoc transcript review, both of which are slow and error-prone. A project manager reviewing a 60-minute team meeting recording might spend 20 to 30 minutes identifying the handful of follow-up items scattered across the conversation, and even careful reviewers miss ambiguous assignments or vague deadlines that were never pinned to a specific person. The cost of a missed action item is real: a delayed vendor contract response, an unsubmitted paper revision, a skipped product demo preparation.

NoteFlow addresses this problem by using a large language model to automatically extract structured action items from raw transcripts. The system takes unstructured text as input and produces a Markdown todo list with checkboxes, a timeline summary table that highlights deadlines at a glance, and a time_references section that lists every temporal expression found in the transcript — making it immediately clear whether the meeting established concrete deadlines or left everything vague. The workflow is applicable across two primary contexts: business meetings (team standups, client calls, research RA meetings) and academic lectures (homework assignments, exam dates, in-class tasks). Each context uses a tuned system prompt that reflects its specific vocabulary and conventions.

## Model Selection

The prototype uses Google Gemini (gemini-2.5-flash) through the google-genai Python SDK (version 1.47.0). This choice was driven by three practical considerations. First, the Gemini API provides free access through Google AI Studio, making it frictionless for academic prototyping without a paid subscription. Second, gemini-2.5-flash offers a strong balance between output quality and response speed — it handles structured JSON generation reliably while keeping latency under a few seconds per request. Third, the google-genai SDK is well-documented and easy to integrate, which aligned with the assignment's reproducibility requirements. The model name is configurable via a command-line argument, making it trivial to swap variants without code changes.

## Application Architecture

NoteFlow is implemented as a single self-contained Python script (app.py) with three run modes. No-argument invocation starts a local web server at http://127.0.0.1:8765 with a split-layout browser UI; users select Meeting or Lecture mode via a tab selector, paste or upload a transcript, choose output language, and receive a Markdown preview with live rendering. The `--input` flag processes a single transcript file from the command line, printing Markdown or JSON. The `--eval` flag runs batch evaluation over a JSON array of test cases. API key resolution reads from environment variables first, then falls back to a `.env` file in the project directory, so reproduction requires only creating a `.env` file with no code changes.

The JSON parsing pipeline includes multiple fallback strategies — direct parsing, code fence stripping, brace-balanced extraction — to handle cases where the model wraps output in unexpected formatting. Each normalized result includes action items, a one-sentence summary, a natural-language recap, a time_references array, and a warnings array. The Markdown renderer outputs a checkbox list followed by a summary table (Task | Owner | Deadline | Priority) and a time references section, giving both a scannable task list and a compact deadline overview in a single document.

## Prompt Iteration: Baseline vs. Final Design

The initial system prompt was a single sentence instructing the model to "read the transcript and extract action items." Running this against the evaluation set revealed four systematic problems: inconsistent output formats (sometimes bullet points, sometimes prose), hallucination of study tasks from lecture explanations, silent conversion of vague deadlines into fabricated specific dates, and no mechanism for communicating extraction uncertainty to the user.

The first revision introduced structured JSON output, explicit anti-hallucination rules, a priority field, and handling for the zero-action-item case. This resolved formatting inconsistency and significantly reduced hallucination, but the model still occasionally invented deadlines for vague timeframes and handled mixed-language transcripts inconsistently.

The final revision was developed in two variants. The Lecture Mode prompt added confidence scoring per item, a warnings array, a natural_language_summary field, a time_references array, and two rules derived from testing with a real 1800-line lecture recording: Rule 8 instructing the model to focus on buried explicit assignments in noisy filler-heavy text, and Rule 9 preventing it from converting relative dates ("next week", "by Friday") to fabricated calendar dates. The Meeting Mode prompt retuned these same principles for business contexts: Rule 1 was updated to preserve business shorthand (EOD, EOW, Q2, sprint end) exactly as spoken rather than converting to calendar dates, and Rule 5 added specific guidance for research meeting contexts where paper submission deadlines and advisor-directed tasks carry high priority.

Testing the Meeting Mode prompt against Cases 6, 8, and 9 — a product team meeting, a research RA meeting, and a business sync with dense time expressions and ambiguous ownership — confirmed that the tuned prompt correctly preserves shorthand deadlines, surfaces coverage ambiguities as warnings, and distinguishes informational updates (the abstract will be handled by the professor) from assignable action items.

## Limitations and Failure Modes

The most significant limitation is handling extremely long transcripts. When a transcript exceeds several thousand words, the model occasionally misses action items that appear deep within the text, particularly when surrounded by lengthy explanations. This is demonstrated in Case 7, which tests attention to a single buried action item in a long educational passage. A chunking strategy with overlapping segments could address this in a future iteration.

A second limitation is implicit action items — things a reasonable listener would understand as tasks but that are never explicitly stated. The system conservatively does not generate these, which avoids hallucination but may miss items that experienced meeting participants would capture. Whether this is a feature or a limitation depends on the use case.

Third, confidence scoring is a heuristic based on textual clarity, not a calibrated probability from the model's internal state. Users should treat confidence levels as rough guidance for where human review is most needed, not as precise reliability estimates.

Fourth, the web UI runs as a local unauthenticated HTTP server, appropriate for single-user local use but not suitable for shared deployment without additional security controls.

## Deployment Recommendation

NoteFlow demonstrates that LLM-based action item extraction is viable and immediately useful for both business and academic contexts. The system reliably handles standard cases, degrades gracefully on ambiguous input by flagging uncertainty rather than fabricating specifics, and produces output in a format (Markdown checkboxes) that can be directly pasted into any task management tool.

That said, deployment without human review would be premature. The recommended configuration is human-in-the-loop: NoteFlow generates a first draft after each meeting or lecture, and the user reviews and confirms items before acting on them. For business meetings, this review step takes under two minutes for a typical 60-minute meeting — a significant reduction from 20-30 minutes of manual scanning. Under these conditions, with human oversight as a standard workflow step, NoteFlow is ready for personal and team use. The next meaningful improvement would be a chunking strategy for very long transcripts and an option to merge results from multiple sessions of the same ongoing project.
