# Agent Flow Studio — Feature Roadmap

> Living document tracking planned features, priorities, and progress.
> Last updated: March 30, 2026

---

## Current State (v0.1 — Foundation)

- [x] Visual node-based flow editor (Drawflow)
- [x] LLM integrations (OpenAI, Anthropic, Ollama)
- [x] Core nodes: Start, LLM Call, Prompt Template, Conditional, Code, Merge, Output
- [x] Script & I/O nodes: Shell, HTTP Request, File Read, File Write
- [x] Flow control: Loop node (code / LLM / shell modes), Human-in-the-Loop (HITL)
- [x] Per-node error handling with retry logic
- [x] Real-time execution monitoring via WebSocket
- [x] Flow save / load / delete
- [x] Export as standalone ZIP (config + scripts + HTML runner)
- [x] Dynamic model dropdowns for OpenAI & Anthropic
- [x] Example flows library

---

## Phase 1 — Developer Experience (v0.2) ✅

*Goal: Make building and iterating on flows dramatically faster.*

### 1.1 Quick Test per Node ✅
- **Priority:** Critical
- **Effort:** Small
- **Description:** Right-click any node → "Test with sample input." Runs that single node in isolation with either its upstream data from the last run or custom text pasted into a popup. Displays output immediately without running the full flow.
- **Why:** Prompt engineering is iterative. Running the entire flow every time you change a word is the #1 friction point. This cuts iteration cycles from minutes to seconds.
- **Implementation notes:**
  - New `/api/test-node` endpoint accepting `node_type`, `node_data`, `input_text`, and `settings`
  - Reuse executor logic for individual node types
  - Context menu on right-click with "Test Node" option
  - Modal showing input textarea, "Run" button, and output display

### 1.2 Step-Through Debug Mode ✅
- **Priority:** Critical
- **Effort:** Medium
- **Description:** A "Debug" button alongside "Run." Executes the flow but pauses before each node, highlighting it on the canvas and showing the input data in an inspector panel. Controls: Step (advance one node), Continue (run to next breakpoint), Stop. Users can set breakpoints by clicking a dot on any node. Mid-flow, users can edit the data before stepping forward.
- **Why:** Debugging agent flows is an industry-wide pain point (Microsoft Research published AgentRx specifically for this). No local-first visual builder has good step-through debugging. This would be a differentiator.
- **Implementation notes:**
  - New WebSocket message types: `debug_pause`, `debug_step`, `debug_continue`, `debug_edit`
  - Server-side: executor yields control at each node boundary, waits for client signal
  - Client-side: breakpoint indicators (red dots) on nodes, inspector panel showing input/output JSON
  - Highlight active node with a pulsing border during pause

### 1.3 Variable Inspector Panel ✅
- **Priority:** Medium
- **Effort:** Small
- **Description:** A toggleable sidebar showing every `{{variable}}` placeholder across the flow — which node produces it, which nodes consume it, and its last known value from the most recent run. Click a variable to highlight its path through the graph.
- **Why:** In complex flows with 10+ nodes, tracing how data moves is difficult. This makes data flow transparent and debuggable at a glance.
- **Implementation notes:**
  - Parse all node data for `{{...}}` patterns
  - Build a dependency map: producer → variable → consumers
  - Overlay highlighted edges on the Drawflow canvas when a variable is selected

---

## Phase 2 — Intelligence & Autonomy (v0.3) ✅

*Goal: Enable true autonomous agent behavior, not just linear pipelines.*

### 2.1 ReAct Agent Node ("Autonomous Agent") ✅
- **Priority:** Critical
- **Effort:** Large
- **Description:** A single node implementing the full Think → Act → Observe loop. Configure which "tools" the agent can use (shell commands, HTTP requests, code execution, file read/write) and give it a goal. The LLM autonomously decides what action to take, the system executes it, the LLM observes the result, and the cycle repeats until the goal is met or a max iteration/budget limit is hit.
- **Why:** This is *the* core pattern behind every serious agent framework (LangGraph, CrewAI, AutoGen). It elevates the app from "workflow builder" to "agent platform." Users can build agents that solve open-ended problems, not just follow predetermined paths.
- **Implementation notes:**
  - Tool definitions as structured JSON (name, description, parameter schema)
  - LLM generates tool calls via function-calling or structured output parsing
  - Execution sandbox for each tool type (reuse existing shell/HTTP/code/file logic)
  - Configurable: max iterations, budget cap (token limit), allowed tools, safety guardrails
  - Execution log streams each Think/Act/Observe step in real time
  - Conversation history accumulates across iterations for full context

### 2.2 Conversation Memory Node ✅
- **Priority:** Medium
- **Effort:** Medium
- **Description:** Maintains multi-turn conversation state within and across flow executions. Stores `[{role, content}]` message history and injects it into downstream LLM calls. Supports configurable context window management (sliding window, summarization, token-budget trimming).
- **Why:** Current LLM nodes are single-shot. Real agents need to remember what they said and what they learned. This enables chatbot-style interactions, interview agents, and multi-turn reasoning chains.
- **Implementation notes:**
  - New node type with configurable memory strategy (full, sliding window, summarize-and-forget)
  - Persistent storage option: save memory to JSON file between runs
  - Integration with LLM node: inject memory as system/user messages before the current prompt
  - Memory viewer in properties panel showing current conversation state

### 2.3 Natural Language Flow Builder ✅
- **Priority:** High
- **Effort:** Large
- **Description:** A prominent text input: "Describe what your flow should do." The system uses the user's configured LLM to generate a complete flow graph — nodes, connections, and configurations — from a plain-English description. The generated flow appears on the canvas for the user to review and tweak.
- **Why:** The biggest barrier to adoption is the blank canvas. Users know *what* they want but not *how* to wire it up. This eliminates the cold-start problem entirely. No other local-first builder does this.
- **Implementation notes:**
  - System prompt with full schema of available node types, their properties, and Drawflow JSON structure
  - LLM outputs structured JSON matching the flow format
  - Validation layer to catch malformed graphs before rendering
  - "Refine" button to iterate: "Also add error handling" or "Make it process files in parallel"
  - Could work with any configured provider — use the default model from settings

---

## Phase 3 — Composition & Scale (v0.4) ✅

*Goal: Enable building complex systems from tested, reusable components.*

### 3.1 Sub-Flows (Composable Modules) ✅
- **Priority:** High
- **Effort:** Large
- **Description:** Select a group of nodes → right-click → "Save as Sub-Flow." The group collapses into a single reusable node with defined input/output ports. Sub-flows appear in the node palette under a "My Modules" section. Double-click to expand and edit the internals.
- **Why:** Without composition, every flow is built from scratch. Sub-flows are like functions in programming — build once, test, reuse everywhere. Essential for managing complexity as flows grow beyond 10-15 nodes.
- **Implementation notes:**
  - Sub-flow stored as a separate JSON file with declared input/output ports
  - At execution time, inline-expand the sub-flow into the parent graph
  - Nested sub-flows supported (sub-flow within a sub-flow)
  - Version tracking: updating a sub-flow definition optionally propagates to all flows using it

### 3.2 Map-Reduce Node ✅
- **Priority:** Medium
- **Effort:** Medium
- **Description:** Takes a list as input (JSON array, newline-delimited text, or file glob pattern), splits it into individual items, runs a configurable sub-flow on each item in parallel, and collects/reduces the results (concatenate, merge JSON, or custom code reducer).
- **Why:** Real workflows operate on collections: "review every file in this directory," "summarize each section of this document," "process every row in this CSV." Without Map-Reduce, users have to manually duplicate nodes or write custom loop code.
- **Implementation notes:**
  - Depends on Sub-Flows (3.1) for the "map" function
  - Configurable parallelism (max concurrent, rate limiting for API calls)
  - Progress reporting: "Processing item 7/23..."
  - Error handling: continue on failure (collect errors), or stop on first failure

### 3.3 Prompt Library / Snippets ✅
- **Priority:** Low
- **Effort:** Small
- **Description:** Save and tag reusable prompt templates with descriptions. Browse/search when configuring Prompt Template or LLM nodes. Ships with a curated starter library (code review, summarization, extraction, etc.).
- **Why:** Reduces the "blank page" problem. Good prompts are hard to write — reusing proven ones saves time and improves quality.
- **Implementation notes:**
  - JSON file storage: `prompts/` directory with metadata (name, tags, description, template)
  - "Insert from Library" button in Prompt Template and LLM node property panels
  - Import/export prompts as JSON for sharing

---

## Phase 4 — Knowledge & RAG (v0.5) ✅

*Goal: Enable knowledge-grounded agents that can reference documents and data.*

### 4.1 Embed Node ✅
- **Priority:** Medium
- **Effort:** Medium
- **Description:** Converts text input into vector embeddings using OpenAI embeddings API, or a local model (SentenceTransformers via Python). Configurable chunking strategy (chunk size, overlap). Outputs structured embedding data.
- **Why:** Embeddings are the foundation of RAG. This node is the entry point to the entire knowledge pipeline.

### 4.2 Vector Store Node ✅
- **Priority:** Medium
- **Effort:** Medium
- **Description:** Stores and retrieves vector embeddings locally. Uses ChromaDB (pip-installable, zero infrastructure) or SQLite-vec for persistence. Supports operations: insert, query (similarity search with top-k), and delete.
- **Why:** ChromaDB keeps everything local-first, matching the app's philosophy. No cloud services required.

### 4.3 RAG Retrieve Node ✅
- **Priority:** Medium
- **Effort:** Small (builds on 4.1 + 4.2)
- **Description:** Combines embedding + similarity search + context injection in one convenience node. Takes a query, retrieves relevant chunks from a vector store, and formats them as context for an LLM prompt. Configurable: top-k results, similarity threshold, output format.
- **Why:** RAG is the #1 production LLM use case. This makes it a drag-and-drop operation instead of requiring manual wiring of embed → search → format → LLM.

---

## Phase 5 — Automation & Integration (v0.6)

*Goal: Make flows autonomous — triggered by events, running on schedules.*

### 5.1 Webhook Trigger Node
- **Priority:** Medium
- **Effort:** Medium
- **Description:** Replaces the Start node with an HTTP endpoint. When the flow is "armed," it listens at `/webhook/{flow_id}` for incoming POST requests. The request body becomes the flow's input data. Supports optional authentication (API key header).
- **Why:** Enables integration with external systems: GitHub webhooks trigger code review flows, Slack messages trigger research flows, form submissions trigger processing flows. This is what makes n8n sticky — flows that run themselves.
- **Implementation notes:**
  - FastAPI route dynamically registered per armed webhook flow
  - Queue system for concurrent webhook hits
  - Response mode: async (return 202 immediately) or sync (wait for flow completion, return output)

### 5.2 Cron / Schedule Trigger Node
- **Priority:** Medium
- **Effort:** Small
- **Description:** Trigger node that fires on a configurable schedule (every N minutes, hourly, daily at a specific time, cron expression). The flow runs automatically in the background.
- **Why:** Monitoring, reporting, data collection — many useful flows need to run periodically without human intervention.
- **Implementation notes:**
  - APScheduler integration (pip-installable)
  - UI: schedule configuration in the trigger node's properties
  - Background execution with results logged to execution history

### 5.3 Email / Notification Node
- **Priority:** Low
- **Effort:** Small
- **Description:** Sends flow outputs via email (SMTP), desktop notification, or writes to a notification log. Useful as a terminal node for automated flows that need to alert a human.
- **Why:** Automated flows need a way to report results. Pairs naturally with webhook and cron triggers.

---

## Phase 6 — Observability & Optimization (v0.7)

*Goal: Understand what your flows are doing, how well, and at what cost.*

### 6.1 Execution History & Run Comparison
- **Priority:** High
- **Effort:** Medium
- **Description:** Every run is logged with full data: inputs/outputs per node, timing, token counts, and estimated cost. A "History" panel shows a timeline of past runs. Click any run to replay its execution visually on the canvas (nodes light up in sequence with their outputs). Compare two runs side-by-side to see which configuration produced better results.
- **Why:** Without history, you can't systematically improve flows. You forget what you changed, can't compare results, and lose good outputs. This is the foundation for prompt optimization.
- **Implementation notes:**
  - SQLite database for run storage (lightweight, local)
  - Each run record: flow_id, timestamp, duration, per-node data (input, output, timing, tokens, cost)
  - History modal with search/filter by flow, date, status
  - Visual replay: animate node execution on canvas with timing
  - Diff view: side-by-side output comparison for two selected runs

### 6.2 Cost Estimator & Token Counter
- **Priority:** Medium
- **Effort:** Small
- **Description:** Before running, estimate token cost per LLM node based on input size and model pricing tables. After running, show actual tokens consumed and cost. Small badge on each LLM node (e.g., "~1.2k tokens · $0.003"). Summary at flow completion: "Total: 8,400 tokens · ~$0.02."
- **Why:** Cost surprises are the #1 reason people abandon LLM workflows. Visibility before and after running builds confidence and enables optimization.
- **Implementation notes:**
  - Pricing table: hardcoded per-model input/output token costs (update periodically)
  - Pre-run estimation: count tokens via tiktoken (OpenAI) or approximation (chars/4)
  - Post-run actuals: capture token counts from LLM API responses
  - Display: badge overlay on LLM nodes + summary in execution log

### 6.3 Flow Versioning & Diff
- **Priority:** Low
- **Effort:** Medium
- **Description:** Every save creates a version snapshot. View a version timeline, compare two versions visually (highlight added, removed, or changed nodes and connections), and rollback to any previous state.
- **Why:** Gives users confidence to experiment — they can always go back. Essential once flows become valuable assets.
- **Implementation notes:**
  - Store version history as array of flow snapshots in the flow JSON file
  - Visual diff: overlay highlighting on the canvas (green = added, red = removed, yellow = modified)
  - One-click rollback to any version

---

## Release Summary

| Phase | Version | Theme | Key Features |
|-------|---------|-------|--------------|
| 1 | v0.2 | Developer Experience | Quick Test, Debug Mode, Variable Inspector |
| 2 | v0.3 | Intelligence & Autonomy | ReAct Agent, Conversation Memory, NL Flow Builder |
| 3 | v0.4 | Composition & Scale | Sub-Flows, Map-Reduce, Prompt Library |
| 4 | v0.5 | Knowledge & RAG | Embed, Vector Store, RAG Retrieve |
| 5 | v0.6 | Automation & Integration | Webhooks, Cron Triggers, Notifications |
| 6 | v0.7 | Observability & Optimization | Execution History, Cost Estimator, Versioning |

---

## Design Principles

These principles should guide every feature decision:

1. **Local-first** — Everything runs on the user's machine. No cloud dependencies unless the user chooses them (LLM APIs). Data never leaves the local system.
2. **Zero-config start** — New features should work out of the box. Sensible defaults, no required setup steps.
3. **Progressive complexity** — Simple flows should be simple to build. Advanced features (ReAct, RAG, Sub-Flows) are available but never in the way.
4. **Visual transparency** — Every piece of data flowing through the system should be inspectable. No black boxes.
5. **Composable** — Small, tested pieces combine into complex systems. Sub-flows, prompt library, and node reuse all serve this.
