# 08_failure_modes.md

## Anticipated Failure Taxonomy
The agent must recognize when it is failing and enter a "Safe State" rather than guessing.

### 1. The "Ghost Click" (UI Drift)
- **Mode:** The Accessibility Tree identifies a button, but it is obscured by a popup or has moved.
- **Detection:** The Verification Loop (Critic) sees no change in screen state after the click.
- **Recovery:** 1. Refresh the Accessibility Tree.
    2. Attempt a "Visual Search" (Layer 3) to find the new location.
    3. If search fails, **Pause and Notify User.**

### 2. Semantic Hallucination
- **Mode:** The VLM misinterprets a chart (e.g., seeing a "Buy Signal" in a downward trend).
- **Detection:** The Critic compares the VLM's logic with the Hard Policy Engine.
- **Recovery:** Log the logic discrepancy. If the task is "Trading," immediately abort the action and present the logic conflict to the user for review.

### 3. Application Hang / Latency
- **Mode:** An app (like VS Code or a Browser) stops responding to UI Automation queries.
- **Detection:** Timeout exceeded (>10 seconds) on a Layer 1 query.
- **Recovery:** 1. Check if the process is still running via OS `tasklist`.
    2. If running, wait another 10s with a "Loading" status in the Tray.
    3. If crashed, ask the user: "App X seems to have crashed. Should I restart it?"

### 4. Policy Violation Loop
- **Mode:** The agent's plan repeatedly requests a blocked action (e.g., trying to delete a file).
- **Detection:** Policy Engine denies the same action type 3 times in a row.
- **Recovery:** Clear the Short-Term Memory. Explain to the user: "I cannot fulfill this request due to safety policy [X]."