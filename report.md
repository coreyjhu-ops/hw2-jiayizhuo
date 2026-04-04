# LectureFlow: Automating Action Item Extraction from Lecture Transcripts

## Business Use Case

University students routinely attend lectures where instructors assign homework, set deadlines, delegate responsibilities, and make schedule changes — all embedded within long spoken explanations. The conventional approach to capturing these action items relies on manual note-taking during the lecture or painstaking review of recorded transcripts afterward. Both methods are error-prone and time-consuming. A student reviewing a 50-minute lecture recording might spend 20 to 30 minutes scanning for the handful of sentences that actually contain actionable information, and even then, subtle items buried within tangential discussions are easy to miss.

LectureFlow addresses this problem by using a large language model to automatically extract structured action items from raw lecture transcripts. The system takes unstructured text as input and produces a JSON object containing discrete tasks, each annotated with an owner, a deadline, a priority level, and a confidence score. This workflow is particularly valuable in graduate-level programs where students juggle multiple courses, group projects, and shifting deadlines simultaneously.

## Model Selection

The prototype uses Google Gemini (gemini-2.0-flash) through the google-genai Python SDK. This choice was driven by three practical considerations. First, the Gemini API provides free access through Google AI Studio, making it frictionless for academic prototyping without requiring a paid subscription. Second, the gemini-2.0-flash model offers a strong balance between output quality and response speed — it handles structured JSON generation reliably while keeping latency under a few seconds per request. Third, the google-genai SDK is well-documented and straightforward to integrate into a command-line Python script, which aligned well with the assignment's reproducibility requirements.

No alternative models were tested in this iteration, though the architecture of app.py makes it trivial to swap in a different provider by changing the model parameter and API client initialization.

## Prompt Iteration: Baseline vs. Final Design

The initial system prompt was deliberately minimal: a single sentence instructing the model to "read the transcript and extract action items." Running this baseline against the evaluation set revealed several systematic problems. The model produced inconsistent output formats across different inputs, sometimes using bullet points and sometimes numbered lists. More critically, it frequently hallucinated action items from general lecture content — for example, turning a professor's explanation of gradient descent into a fabricated study task. Deadlines mentioned vaguely in the transcript were often silently converted into specific dates that the speaker never stated.

The first revision introduced structured JSON output, explicit rules against hallucination, and a clear schema specifying task, owner, deadline, and priority for each item. This immediately resolved the formatting inconsistency and reduced hallucination significantly. However, the model still occasionally fabricated specific dates for vague deadlines and handled mixed-language transcripts inconsistently.

The final revision added three key improvements: a per-item confidence score (High, Medium, or Low) that signals how much human verification each item requires, a warnings array that flags ambiguities at the transcript level, and explicit instructions for handling multilingual input. These additions transformed the system from a simple extraction tool into one that actively communicates its own uncertainty — a property that is essential for any workflow where errors carry real consequences, such as missing an assignment deadline.

Across the evaluation set, the final prompt version correctly handled all seven test cases, including the edge case with no action items, the ambiguous-reference case that earlier versions hallucinated through, and the buried-action-item case that tests attention to detail in long transcripts.

## Limitations and Failure Modes

The prototype has several known limitations that would require attention before any production deployment. The most significant is its handling of extremely long transcripts. When a transcript exceeds several thousand words, the model occasionally misses action items that appear deep within the text, particularly when those items are surrounded by lengthy explanations. This could be mitigated by implementing a chunking strategy that processes the transcript in overlapping segments and merges the results.

A second limitation involves implicit action items — things a reasonable human listener would understand as tasks but that are never explicitly stated. For example, if a professor says "the exam covers Chapters 1 through 5," a student would naturally create a study plan, but the system correctly does not generate this as an action item because it was never explicitly assigned. Whether this conservative behavior is a feature or a limitation depends on the use case.

Third, the confidence scoring, while useful, is ultimately a heuristic based on how clearly the transcript states each task's parameters. It does not reflect the model's actual internal certainty about its extraction, and users should treat it as a rough guide rather than a calibrated probability.

## Deployment Recommendation

LectureFlow demonstrates that LLM-based action item extraction is viable and valuable for academic contexts. The system reliably handles standard cases, gracefully degrades on ambiguous input by flagging uncertainty, and avoids the most dangerous failure mode — confidently hallucinating nonexistent tasks.

That said, deploying this workflow without human review would be premature. The recommended approach is a human-in-the-loop configuration: the system generates a first draft of action items after each lecture, and the student reviews and confirms them before adding them to their task management system. This review step should take under two minutes for a typical lecture, compared to the 20 to 30 minutes of manual transcript scanning it replaces. Under these conditions — with human oversight as a standard part of the workflow — LectureFlow is ready for personal use and could be extended into a shared tool for study groups or teaching assistant teams.
