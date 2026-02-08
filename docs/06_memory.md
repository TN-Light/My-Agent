# 06_memory.md

## Memory Hierarchy
The agent utilizes a tiered memory system to balance speed, context, and privacy.

### 1. Short-Term Memory (Context Window)
- **Scope:** Current task session only.
- **Storage:** In-memory RAM (Python Dictionary/List).
- **Content:** Last 5 screenshots, current plan, and immediate feedback from the Critic.
- **Persistence:** Cleared when the task is marked "Complete" or "Aborted."

### 2. Episodic Memory (Action History)
- **Scope:** Past actions and their outcomes.
- **Storage:** **SQLite** (`history.db`).
- **Content:** Timestamp, Application, Action (e.g., Click), Result (Success/Fail), and Error Logs.
- **Purpose:** Used by the Critic to avoid repeating the same mistake twice in a single session.

### 3. Long-Term Memory (Semantic Knowledge)
- **Scope:** User preferences, learned workflows, and "Trading" habits.
- **Storage:** **ChromaDB** (Vector Database).
- **Content:** Embeddings of user instructions like "I prefer dark mode" or "Always check the RSI indicator on trading charts."
- **Retrieval:** Queried at the start of every new PLAN phase to ground the agent in user-specific "vibes."

## Privacy & Security Constraints
- **Zero-Secret Storage:** Passwords, API keys, or credit card numbers must **NEVER** be stored in the Vector DB or SQLite.
- **Screenshot Retention:** Screenshots used for processing must be deleted from disk within 60 seconds of task completion.
- **Local-Only:** The `db/` folder must be excluded from any cloud sync services (e.g., OneDrive/Dropbox) to ensure data stays on the local hardware.