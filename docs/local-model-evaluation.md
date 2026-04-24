# MeetScribe Local Model Improvement: Double-Pass Approach & Prompt Engineering

Created: 2026-04-24
Context: Research session evaluating local models as potential replacements for Sonnet 4.6 in meetscribe's meeting transcript summarization pipeline.

---

## Background

MeetScribe uses an LLM to summarize meeting transcripts into a structured 5-section Markdown format (Overview, Topics, Actions, Decisions, Open Questions). The current production backend is **Sonnet 4.6** via claudemax proxy, with **Ollama** as fallback. The Ollama default was `qwen3.5:9b` (now changed to `gpt-oss:20b`).

The goal is to determine whether local models can match Sonnet 4.6 quality for fully offline summarization.

### Relevant files

- **System prompt:** `/home/kasita/models/meet/meet/prompts/summarize_system.md`
- **User prompt:** `/home/kasita/models/meet/meet/prompts/summarize_user.md`
- **User prompt (non-English):** `/home/kasita/models/meet/meet/prompts/summarize_user_lang.md`
- **Summarization code:** `/home/kasita/models/meet/meet/summarize.py` (753 lines, 4 backends: claudemax, openrouter, ollama, openai)
- **Language headers:** `/home/kasita/models/meet/meet/languages.py` (section header translations for DE, FR, ES, TR, FA)
- **Default Ollama model:** `gpt-oss:20b` (changed from `qwen3.5:9b` during this session, line 33 of `summarize.py`)

### Typical meeting characteristics

| Metric | Range |
|--------|-------|
| Transcript size | 15-120 KB (plain text) |
| Token count | 4K-30K tokens |
| Duration | 15-90 min |
| Speakers | 2-8 |
| Languages | English (primary), German, Turkish, Farsi |
| Output size (Sonnet 4.6) | 3-9 KB Markdown |

### Test meetings used in this evaluation

| Meeting | Size | Tokens | Lang | Speakers | Complexity |
|---------|------|--------|------|----------|------------|
| DEVSTANDUP (20260416) | 26 KB | ~7K | EN | 4 | Medium — standup + debugging + side topics |
| DEVSYNC (20260414) | 67 KB | ~17K | EN | 6 | High — multi-topic technical sync |
| SOCRATICSEMINAR (20260325) | 118 KB | ~30K | DE | 8+ | Very high — 18+ topics, German language |
| BLINKSTUFF (20260423) | 79 KB | ~20K | EN | 4 | High — business dev, 11+ distinct topics |

---

## Models Tested

| Model | Ollama ID | Size | Context | Architecture | Speed (tg128) |
|-------|-----------|------|---------|--------------|---------------|
| Sonnet 4.6 | N/A (cloud) | N/A | 200K | Anthropic | N/A |
| GPT-OSS 20B | `gpt-oss:20b` | 13 GB | 128K | OpenAI MoE, MXFP4 | ~50 t/s |
| Qwen3.6 27B | `qwen3.6:27b` | 17 GB | 262K | Qwen3.5/DeltaNet hybrid | 36 t/s |
| Qwen3.5 27B | `qwen3.5:27b` | 17 GB | 262K | Qwen3.5 | ~8 t/s (partial CPU) |
| Gemma4 26B | `gemma4-26b-16k` | 17 GB | 16K | Google Gemma4 | 137 t/s |

Hardware: RTX 3090 (24 GB VRAM), 64 GB RAM.

---

## Current System Prompt

File: `meet/prompts/summarize_system.md`

```markdown
You are a professional meeting assistant. Analyze the meeting transcript below and produce a structured summary in exactly the Markdown format specified.

## OUTPUT FORMAT (use exactly this structure):

## {overview}
2-3 sentences covering: what the meeting type was, who was involved (by role/function if unclear), and the main themes discussed.

## {topics}
* **Topic name:** 1-2 sentence description of what was discussed, including any key technical details, tools, or product names mentioned.
(List every substantive topic — aim for 6-10 bullet points for a 60-90 min meeting. Scale proportionally for shorter/longer meetings.)

## {actions}
* Action item in imperative form, with enough context to act on it — **Owner** (use exact name from transcript)
(Capture both explicitly assigned AND clearly implied items, e.g. "I'll look into that" = action for that speaker. If owner is unclear, write **Owner Unknown**. If none, write "{none_stated}".)

## {decisions}
* Concrete decision reached, stated as a fact (e.g. "X was chosen over Y", "Z is deprioritized")
(Only include things actually agreed upon, not merely suggested or explored. If none, write "{none_stated}".)

## {questions}
* Unresolved question, open dependency, or follow-up item — include enough context to understand why it matters
(Include unresolved debates, blockers waiting on third parties, and things flagged as "we need to figure out". If none, write "{none_stated}".)

## RULES:
1. Use speaker labels EXACTLY as they appear in the transcript. Do not rename, merge, or invent speakers.
2. Do NOT hallucinate. Every item must be traceable to something said in the transcript.
3. Be concise but information-dense. Avoid filler phrases like "the team discussed..." — state the substance directly.
4. For technical topics, preserve specificity: name the exact tools, frameworks, APIs, error types, or architectural patterns mentioned.
5. Actions: include items that were explicitly assigned AND items clearly implied (e.g. "I'll look into that" = action for that speaker).
6. Decisions: only include things actually agreed upon, not things merely suggested or explored.
7. Questions: include unresolved debates, blockers waiting on third parties, and things flagged as "we need to figure out".
8. Keep the summary professional and objective.
{lang_instruction}
```

The `{overview}`, `{topics}`, `{actions}`, `{decisions}`, `{questions}`, `{none_stated}` placeholders are replaced by language-specific headers at runtime via `_build_system_prompt()` in `summarize.py`. The `{lang_instruction}` placeholder is replaced with a language directive for non-English transcripts.

---

## Single-Pass Results (Current Approach)

### Test: DEVSTANDUP (26 KB, ~7K tokens, English)

| Dimension | Sonnet 4.6 | gpt-oss:20b | qwen3.6:27b | qwen3.5:27b | gemma4-26b-16k |
|-----------|:-:|:-:|:-:|:-:|:-:|
| 5-section format | 5/5 | **5/5** | 0/5 | 0/5 | 0/5 |
| Topics covered | 10 | 10 | 1 (tunneled) | 1 (tunneled) | 3 |
| Action items | 5 with owners | 10 (some generic) | 0 | 0 | Generic, no names |
| Decisions | 3 | 0 | 0 | 0 | 0 |
| Open questions | 5 | 5 | 0 | 0 | 0 |
| Time | 40s | 36s | 132s | 98s | 23s |

### Test: BLINKSTUFF (79 KB, ~20K tokens, English)

| Dimension | Sonnet 4.6 | gpt-oss:20b | qwen3.6:27b |
|-----------|:-:|:-:|:-:|
| 5-section format | 5/5 | 4/5 (tables, extra sections) | 0/5 (offered a menu) |
| Topics covered | 11 | 5 (grouped) | 0 |
| Action items | 13 with owners | 4 vague | 0 |
| Decisions | 6 | 5 (some fabricated) | 0 |
| Open questions | 8 | 0 | 0 |
| Hallucinations | None | 3 (wrong date, wrong names) | N/A |
| Output size | 8.4 KB | 3.1 KB | 657 chars |
| Time | 64s | 65s | 147s |

### Failure modes identified

1. **Format non-compliance** — All local models except gpt-oss deviate from the specified 5-section Markdown structure. They invent their own formats (tables, numbered sections, "Executive Summary" layouts).
2. **Content tunneling** — Local models fixate on 1-3 topics (usually the most prominent or the last one discussed) and ignore the rest of the meeting.
3. **System prompt ignorance** — qwen3.6 and qwen3.5 treat the transcript as a conversation to respond to, not a document to summarize. qwen3.6 literally offered a menu of things it *could* do instead of following the system prompt.
4. **Hallucination** — gpt-oss invents dates, misnames entities ("BlinkBuzzers" instead of "BlinkBosses", "La Maison de TPV" instead of "La Casa de TPV", "Bitcoin Association" — never mentioned).
5. **Context limitation** — gemma4-26b-16k has a 16K context limit, truncating 2 of 3 test meetings.

---

## Improved Prompt (Single-Pass)

Tested on BLINKSTUFF with gpt-oss:20b. This prompt was designed to address format non-compliance, hallucination, and content tunneling.

```markdown
You are a meeting summarizer. Read the transcript and output EXACTLY the Markdown structure shown below — no other sections, no tables, no preamble, no closing remarks.

## {overview}
2-3 sentences: meeting type, participants (by name as they appear in the transcript), and main themes.

## {topics}
* **Topic name:** 1-2 sentence description with specific details (tools, product names, numbers, URLs mentioned).
(Cover EVERY substantive topic. Aim for 6-10 bullets for a 60-90 min meeting. Do NOT group multiple topics into one bullet. Do NOT skip topics from the beginning or middle of the meeting.)

## {actions}
* Action description with enough context to act on it — **Owner** (exact speaker name from transcript)
(Include both explicitly stated AND implied commitments, e.g. "I'll look into that" = action for that speaker. If owner is unclear, write **Owner Unknown**. If none exist, write "{none_stated}".)

## {decisions}
* Decision stated as a fact (e.g. "X was chosen over Y")
(ONLY include things explicitly agreed upon by participants. If someone merely suggested something or expressed interest without commitment, it is NOT a decision — put it in Open Questions instead. If none, write "{none_stated}".)

## {questions}
* Unresolved question or open dependency — include context for why it matters
(Include: unresolved debates, items waiting on third parties, things flagged as "we need to figure out", and suggestions that were NOT confirmed as decisions. If none, write "{none_stated}".)

RULES:
- Output ONLY the 5 sections above. Do NOT add any other sections, headers, metadata, dates, participant lists, "Next Steps", "Prepared by", or sign-off lines.
- Do NOT use tables. Use bullet lists only.
- Do NOT invent or guess dates, company names, or product names. Use ONLY names and terms that appear verbatim in the transcript.
- Use speaker labels EXACTLY as they appear in the transcript. Do not rename, abbreviate, or invent speakers.
- Every item must be directly traceable to something said in the transcript. Do not infer or fabricate.
- Be concise but information-dense. State substance directly — avoid filler like "the team discussed..." or "there was a conversation about...".
- Preserve technical specificity: exact tool names, frameworks, URLs, version numbers, error messages.
- Scan the ENTIRE transcript from start to finish. Do not focus only on the most recent or most prominent portion.
{lang_instruction}
```

### Key changes from original prompt

| Change | Rationale |
|--------|-----------|
| Removed `## OUTPUT FORMAT (use exactly this structure):` header | Local models confused this instructional header with an output header |
| Added explicit "no tables, no preamble, no closing remarks" | gpt-oss added tables, "Prepared by" footer, date metadata |
| `Do NOT use tables. Use bullet lists only.` | gpt-oss reformatted into tables, breaking expected structure |
| `Do NOT invent or guess dates, company names, or product names` | Addresses specific hallucination pattern (dates, entity names) |
| `Do NOT group multiple topics into one bullet` | Prevents the content compression that local models default to |
| `Do NOT skip topics from the beginning or middle` | Addresses attention/tunneling bias |
| Decisions → Open Questions cross-reference | "if someone merely suggested something... it is NOT a decision — put it in Open Questions" |
| `Scan the ENTIRE transcript from start to finish` | Directly targets the content tunneling problem |
| Removed `## RULES:` heading | The `##` prefix made it look like part of the output format |
| Removed redundant rules 5, 6, 7 | Already stated in section descriptions; duplication adds noise |

### Result: Improved prompt made things WORSE

On BLINKSTUFF with gpt-oss:20b:
- Format compliance dropped from 4/5 to 0/5 (reverted to table layout)
- Topic coverage went from 5 to 6 but still grouped
- Hallucinations persisted
- Output size decreased from 3.1 KB to 2.3 KB

**Conclusion:** Prompt engineering alone cannot fix the core issues with 20B-class models on this task. The model has a strong prior toward table formatting that overrides explicit prohibitions. Content tunneling is a fundamental attention/capability limitation, not a prompt problem.

**However, the improved prompt should still be evaluated with Sonnet 4.6** to ensure no regression. The cleaner structure and explicit anti-hallucination rules may benefit the cloud model even if they don't help local models.

---

## Double-Pass Approach

### Design

Split the summarization into two sequential LLM calls:

**Pass 1 — Extraction:** Ask the model to scan the full transcript and produce raw numbered lists of topics, actions, decisions, and questions. No formatting pressure.

**Pass 2 — Formatting:** Take the Pass 1 output (~2-3K tokens) and ask the model to organize it into the exact 5-section Markdown structure.

### Why it helps

- **Content tunneling:** Pass 1 only asks the model to extract (simpler task). The explicit instruction to "be exhaustive, cover entire transcript" is more effective when the model isn't simultaneously worrying about format.
- **Format compliance:** Pass 2 receives a short input (~2K tokens) and only needs to reformat. Formatting a short list is much easier than extracting + formatting from 20K tokens simultaneously.
- **Hallucination:** Pass 2 can only work with what Pass 1 extracted — it can't invent new facts from a transcript it never saw.

### Pass 1 Prompt (Extraction)

```
You are a meeting transcript analyzer. Your job is to extract information — NOT to summarize or format.

Read the entire transcript below from the very first line to the very last line.
Extract ALL of the following and output them as simple numbered lists.

TOPICS:
(Every distinct topic discussed — one line per topic. Include key details: names, tools, products, URLs, numbers mentioned. Do NOT group related topics — list each one separately. Aim for 10+ topics for a meeting over 60 minutes.)

ACTIONS:
(Every action item or commitment made by any speaker — state WHAT needs to be done and WHO said they would do it. Include both explicit "I'll do X" and implied commitments. Use speaker names exactly as they appear in the transcript.)

DECISIONS:
(Only things explicitly agreed upon by participants — NOT suggestions, interests, or proposals. A decision requires confirmation from the relevant parties.)

QUESTIONS:
(Unresolved items, open dependencies, things someone said "we need to figure out", proposals that were NOT confirmed, and blockers waiting on external factors.)

RULES:
- Be exhaustive. Cover the ENTIRE transcript from start to finish.
- Use speaker names EXACTLY as they appear in the transcript. Do NOT rename or invent names.
- Do NOT invent dates, company names, or product names not in the transcript.
- Output plain numbered lists only. No Markdown formatting, no tables, no headers beyond the four category labels above.
```

### Pass 2 Prompt (Formatting)

```
You are a meeting summary formatter. You will receive pre-extracted meeting data. Your ONLY job is to organize it into the EXACT Markdown structure below.

Do NOT add any information that is not in the extracted data.
Do NOT remove any information from the extracted data.
Do NOT use tables. Use bullet lists only.
Do NOT add preamble, metadata, dates, participant lists, or closing remarks.
Start your output with "## Meeting Overview" — nothing before it.

## Meeting Overview
2-3 sentences: meeting type, who was involved (use names from the data), and the main themes.

## Key Topics Discussed
* **Topic name:** 1-2 sentence description with specifics from the extracted data.

## Action Items
* Action description with context — **Owner**

## Decisions Made
* Decision stated as a fact.
(If no decisions were extracted, write "None explicitly stated".)

## Open Questions / Follow-ups
* Unresolved question with context for why it matters.
(If none were extracted, write "None explicitly stated".)
```

**Note:** The Pass 2 prompt uses hardcoded English headers. For non-English meetings, the headers need to be language-specific (same as the current prompt system). The `{lang_instruction}` should be appended to Pass 1 to ensure extraction happens in the target language, and Pass 2 headers should use the language-specific section headers from `languages.py`.

### User prompts

**Pass 1:**
```
Extract all topics, actions, decisions, and questions from this transcript:

---
{transcript}
---
```

**Pass 2:**
```
Organize the following extracted meeting data into the required format:

---
{pass1_output}
---
```

### Configuration

- Temperature: 0.2 (slightly lower than 0.3 for more deterministic extraction)
- Pass 1 context: dynamically sized based on transcript length + 4K headroom
- Pass 2 context: dynamically sized based on Pass 1 output length + 4K headroom (typically ~5-8K)
- `think: False` for qwen models (prevents hidden reasoning that inflates latency)

---

## Double-Pass Results

### Test: BLINKSTUFF (79 KB, ~20K tokens, English)

#### gpt-oss:20b

| Dimension | Single-pass (original prompt) | Single-pass (improved prompt) | **Double-pass** | Sonnet 4.6 |
|-----------|:-:|:-:|:-:|:-:|
| 5-section format | 4/5 | 0/5 | **5/5** | 5/5 |
| Topics covered | 5 | 6 | **5** | 11 |
| Action items | 4 vague | 6 vague | **6 with owners** | 13 with owners |
| Decisions | 5 (some fabricated) | 0 | **4 (plausible)** | 6 |
| Open questions | 0 | 0 | **0 ("None stated")** | 8 |
| Hallucinations | 3 | 2 | **1** | 0 |
| Output size | 3.1 KB | 2.3 KB | **2.4 KB** | 8.4 KB |
| Time | 65s | 24s | **94s** | 64s |

**Pass 1 behavior:** Still produced its characteristic table+preamble format despite being told "plain numbered lists only." However, it DID extract more content than the single-pass approach. The extraction included topics, actions, decisions, and next steps (though not in the requested numbered list format).

**Pass 2 behavior:** Successfully reformatted the Pass 1 output into perfect 5-section Markdown structure. No tables, correct headers, bullet lists only, no preamble or closing remarks.

**Remaining issues:**
- Content coverage still ~50% of Sonnet 4.6 (5 topics vs 11)
- Open questions section empty despite 8 genuine open items in the meeting
- 1 hallucination persisted ("Fluff" store — not in transcript)
- Pass 1 does not follow its own format instructions (tables instead of numbered lists) — but Pass 2 compensates

#### qwen3.6:27b

| Dimension | Single-pass (original prompt) | **Double-pass** | Sonnet 4.6 |
|-----------|:-:|:-:|:-:|
| 5-section format | 0/5 (refused to summarize) | **5/5** | 5/5 |
| Topics covered | 0 | **5** | 11 |
| Action items | 0 | **5 with owners** | 13 with owners |
| Decisions | 0 | **3 (reasonable)** | 6 |
| Open questions | 0 | **0 ("None stated")** | 8 |
| Hallucinations | N/A | **2** | 0 |
| Output size | 657 chars | **2.8 KB** | 8.4 KB |
| Time | 147s | **353s** | 64s |

**Pass 1 behavior:** Still produced its characteristic "let me help you" preamble with tables and emojis. However, it DID extract meaningful content (topics, action items, strategic notes) — far more than its single-pass attempt where it simply offered a menu.

**Pass 2 behavior:** Successfully reformatted Pass 1 output into perfect 5-section Markdown. The extraction-first approach completely broke qwen3.6's "conversation mode" refusal pattern.

**Remaining issues:**
- Very slow (353s total — 236s extraction + 118s formatting)
- Content coverage ~50% of Sonnet 4.6
- Hallucinated "Kamal" (should be "Kemal") and "Blink Buzzers" (should be "BlinkBosses")
- Open questions section empty

---

## Summary of All Approaches

### On BLINKSTUFF meeting (the hardest test — 79 KB, ~20K tokens, 11 topics)

| Approach | Format | Content | Hallucination | Speed | Verdict |
|----------|:-:|:-:|:-:|:-:|:--|
| Sonnet 4.6 single-pass | 5/5 | 11 topics, 13 actions, 6 decisions, 8 questions | 0 | 64s | Gold standard |
| gpt-oss single-pass (original prompt) | 4/5 | 5 topics, 4 actions | 3 | 65s | Usable but poor |
| gpt-oss single-pass (improved prompt) | 0/5 | 6 topics | 2 | 24s | Regression |
| **gpt-oss double-pass** | **5/5** | **5 topics, 6 actions, 4 decisions** | **1** | **94s** | **Best local** |
| qwen3.6 single-pass | 0/5 | 0 (refused) | N/A | 147s | Unusable |
| **qwen3.6 double-pass** | **5/5** | **5 topics, 5 actions, 3 decisions** | **2** | **353s** | **Good but slow** |
| qwen3.5 single-pass | 0/5 | 1 topic (tunneled) | 0 | 98s | Unusable |
| gemma4 single-pass | 0/5 | 3 topics (context-limited) | 0 | 23s | Context-limited |

### Remaining quality gap vs Sonnet 4.6 (even with double-pass)

1. **Content coverage (~50%):** Local models extract ~5 topics where Sonnet finds 11. This is a fundamental attention/capability limitation of 20B-class models processing 20K tokens.
2. **Open questions (0 vs 8):** No local model identified any open questions. This requires understanding the difference between "agreed upon" and "discussed but unresolved" — a nuanced distinction that smaller models miss.
3. **Action item specificity:** Sonnet extracts 13 specific action items with exact owners and context. Local models find 4-6, often vague.
4. **Hallucination resistance:** gpt-oss consistently hallucinates 1-3 proper nouns per summary despite explicit anti-hallucination instructions.

---

## Implementation Plan

### Phase 1: Implement double-pass in summarize.py (recommended)

Add a `_summarize_ollama_twopass()` function to `summarize.py` that:

1. Runs Pass 1 (extraction) with the full transcript
2. Runs Pass 2 (formatting) with the Pass 1 output
3. Returns the Pass 2 output as the summary

**Key implementation details:**
- Only used by the `ollama` backend — claudemax/openrouter/openai continue using single-pass (they don't need it)
- Pass 1 context: dynamically sized via existing `_dynamic_num_ctx()` function
- Pass 2 context: ~8192 (Pass 1 output is typically 2-4K tokens)
- Temperature: 0.2 for both passes
- `think: False` option for qwen models
- Timeout: Pass 1 gets 80% of the 600s total timeout, Pass 2 gets 20%
- Metadata: `summary.meta.json` should record both pass timings
- Language support: Pass 1 gets `{lang_instruction}` appended, Pass 2 headers use language-specific section headers from `languages.py`

**Estimated effort:** ~50-80 lines of new code, isolated to `summarize.py`. No changes to CLI, GUI, or other modules.

### Phase 2: Evaluate improved prompt for Sonnet 4.6 (optional)

The improved prompt (see above) was designed for local models but contains useful clarifications that might benefit Sonnet 4.6:
- Explicit decision vs. suggestion distinction
- Anti-hallucination specifics
- "Scan entire transcript" instruction

Test by running Sonnet 4.6 with the improved prompt on 2-3 meetings and comparing against existing Sonnet summaries. Only adopt if quality is maintained or improved.

### Phase 3: Explore larger local models (future)

The content coverage gap (~50%) is a model capability issue. Options to close it:
- **Qwen3.6 70B+ (quantized):** Would require significant CPU offload or a second GPU. Not practical on current hardware.
- **Future model releases:** As 27B-class models improve in instruction following and long-context attention, the gap will narrow. Re-evaluate in 3-6 months.
- **Hybrid approach:** Use local model for Pass 1 (extraction) and a cloud model for Pass 2 (formatting). This keeps the transcript local but uses the cloud model only for formatting — the extracted data contains no secrets. This is a privacy compromise but a quality improvement.

---

## Appendix: Model-Specific Notes

### gpt-oss:20b (recommended local model for meetscribe)
- 13 GB, fits comfortably in 24 GB VRAM
- 128K context — handles all meeting sizes without truncation
- MoE architecture with MXFP4 native quantization (OpenAI)
- Best local model for this task: follows format (especially in double-pass), reasonable speed
- Persistent weakness: hallucinated proper nouns (entity names, dates)
- Ollama ID: `gpt-oss:20b` (9M pulls, well-tested)

### qwen3.6:27b
- 17 GB, fits in 24 GB VRAM
- 262K context
- In single-pass mode: completely ignores system prompt and offers a menu instead of summarizing
- In double-pass mode: produces good results but very slow (353s)
- Hallucinated speaker names ("Kamal" instead of "Kemal")
- Not recommended for meetscribe due to speed, but viable as a fallback

### qwen3.5:27b
- 17 GB, requires partial CPU offload at 16K+ context (23 GB total with KV cache)
- Very slow when partially offloaded (~8 t/s)
- Same architecture as qwen3.6, similar failure modes
- Not recommended for meetscribe

### gemma4-26b-16k
- 17 GB, 16K context limit — truncates most meetings
- Fast (137 t/s) but context-limited
- Does not follow the 5-section format
- Not suitable for meetscribe summarization (context too small)

### Sonnet 4.6 (current production model)
- Consistently perfect format compliance
- Comprehensive topic coverage (11+ topics on complex meetings)
- No hallucinations observed
- 40-90s per meeting via claudemax proxy
- Remains the only model that reliably produces publication-ready summaries
