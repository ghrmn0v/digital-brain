You are working on the Fly / Connectome part of our AI Developer Companion project.

Your responsibility is ONLY the Fly system and its interaction with Core Brain events.

Important architecture rule:

Core Brain is the intelligence.
Fly is NOT the AI and must NOT make its own reasoning or detect bugs.
Core Brain detects/analyzes problems and sends structured Brain Events.
Fly visualizes those events and moves to the relevant location.

We are introducing a new "Developer Mode".

When Developer Mode is OFF:

* Keep the existing Fly behavior unchanged.

When Developer Mode is ON:

* Fly should be able to receive a structured Brain Event from Core Brain.
* For a bug-related event, Fly should move to the relevant code location.
* Fly should display a thought bubble / explanation above itself.
* The text inside the thought bubble MUST come from Core Brain.
* Fly must not generate, modify, or infer the explanation.

FIRST TASK — do only this:

1. Inspect the existing Fly repository completely.
2. Understand:

   * current architecture
   * Fly state system
   * movement system
   * rendering
   * Electron / Three.js integration
   * current communication/API mechanism
3. Do NOT rewrite the existing architecture unnecessarily.
4. Do NOT add unrelated features.
5. Do NOT implement bug detection.
6. Do NOT implement LLM calls.
7. Do NOT implement code analysis.
8. Do NOT implement Git, testing, deployment, or code fixing yet.

Create the minimal Developer Mode foundation.

Define a clean event contract for a Brain → Fly developer event.

Use a structure conceptually similar to:

{
"type": "developer.bug_detected",
"event_id": "...",
"repository": "...",
"file": "src/auth/login.ts",
"line": 42,
"column": 10,
"title": "Possible null reference",
"message": "user may be undefined before accessing user.email",
"severity": "warning"
}

Adapt the exact structure to the existing Fly project's technology and architecture.

Requirements:

* event type must be extensible for future events:

  * developer.bug_detected
  * developer.explanation
  * developer.fix_proposed
  * developer.test_result
  * developer.review_finding
  * developer.deploy_status
* Do not implement all of those yet.
* Only developer.bug_detected needs to work now.

Developer Mode:

* Add a Developer Mode state/toggle if the existing application architecture has a suitable place for it.
* Developer Mode must be OFF by default unless the existing product already has a mode system.
* When OFF, developer events must not alter normal Fly behavior.
* When ON, the Fly can react to developer events.

Bug event behavior:

1. Receive Brain event.
2. Validate required fields.
3. Identify repository/file/line.
4. Move Fly to the corresponding code location if the existing Fly system supports location mapping.
5. Show the Brain-provided title/message as a thought bubble.
6. Keep the bubble visible for a reasonable configurable duration.
7. Do not generate any text locally.
8. If the file/line cannot be mapped to a visual location yet, gracefully fall back to displaying the event without breaking Fly.

IMPORTANT:
The Fly does not need to literally understand source code.
The Core Brain will provide the location and explanation.

Create a clean interface/API between Brain and Fly so that later the Core Brain can send:

Brain Event
↓
Fly Event Handler
↓
Fly State
↓
Movement
↓
Thought Bubble

If the current project uses WebSocket, HTTP, IPC, or another communication mechanism, reuse the existing mechanism instead of introducing another transport unnecessarily.

Testing:

Add tests for:

* valid developer.bug_detected event
* invalid/missing required fields
* Developer Mode OFF
* Developer Mode ON
* event does not crash Fly
* Brain-provided message is displayed unchanged
* unsupported developer event is safely ignored

Run all existing tests.

Do not break existing Fly behavior.

Do NOT implement:

* LLM
* bug detection
* code analysis
* code fixing
* Git operations
* test generation
* deployment
* RL changes
* new AI logic

At the end, report:

1. files created
2. files modified
3. event contract
4. Developer Mode implementation
5. Brain → Fly communication mechanism
6. bug event flow
7. tests
8. existing test results
9. any limitations
10. exact commands used for verification

Do NOT commit or push.
Stop after this task.