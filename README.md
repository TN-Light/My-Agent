# My Agent - Phase-0

Local-first desktop AI agent for productivity automation.

## Phase-0 Implementation

This is the foundational Phase-0 implementation with:

- ✅ Accessibility Tree inspector (Windows UIA via pywinauto)
- ✅ System tray daemon + minimal chat UI (PySide6)
- ✅ Policy engine loading `config/policy.yaml`
- ✅ Typed Action schema for type-safe execution
- ✅ Strict execution loop: **PLAN → POLICY → ACT → VERIFY → COMMIT**
- ✅ SQLite audit logging

### Demo Task

Phase-0 supports **one verified action**:
```
open notepad and type hello world
```

## Installation

1. **Python 3.12** required

2. Install dependencies:
```powershell
pip install -r requirements.txt
```

## Usage

Run the agent:
```powershell
python main.py
```

A system tray icon will appear. The chat window opens automatically.

### Supported Commands (Phase-0)

- `open notepad`
- `open notepad and type [your text here]`

### Example

In the chat window, type:
```
open notepad and type hello world
```

The agent will:
1. **PLAN**: Parse instruction into actions
2. **POLICY CHECK**: Validate against whitelist in `config/policy.yaml`
3. **ACT**: Launch Notepad via subprocess, type text via pywinauto
4. **VERIFY**: Check Windows UI Automation tree for Notepad window and focus
5. **COMMIT**: Log action to `db/history.db`

## Project Structure

```
my_agent/
├── config/
│   └── policy.yaml              # Safety rules and whitelists
├── common/
│   └── actions.py               # Typed Action schema
├── perception/
│   └── accessibility_client.py  # Windows UIA inspector
├── logic/
│   ├── planner.py              # Deterministic planner (no LLM)
│   ├── critic.py               # State-based verifier
│   └── policy_engine.py        # Safety gatekeeper
├── execution/
│   └── controller.py           # Low-level OS control
├── storage/
│   └── action_logger.py        # SQLite audit log
├── interface/
│   ├── chat_ui.py              # PySide6 chat window
│   └── tray_daemon.py          # System tray daemon
├── main.py                     # Entry point
├── requirements.txt
└── README.md
```

## Key Design Principles

### Perception Authority Hierarchy

1. **Level 1 (Highest)**: Windows UI Automation (pywinauto)
2. **Level 2**: DOM/API (future: Playwright)
3. **Level 3**: Visual scaffolding (future: SAM-2)
4. **Level 4 (Lowest)**: Vision/OCR (future: VLM)

Phase-0 uses **Level 1 only** for maximum reliability.

### Execution Loop

Every instruction follows this strict sequence:

```
PLAN → POLICY CHECK → ACT → VERIFY → COMMIT
```

- **PLAN**: Parse instruction into typed Actions
- **POLICY CHECK**: Validate against `policy.yaml` whitelist/blacklist
- **ACT**: Execute via Controller (subprocess/pywinauto)
- **VERIFY**: State-based verification via Accessibility Tree
- **COMMIT**: Log to SQLite for audit trail

### Type Safety

Actions are **type-safe** via the `Action` dataclass:

```python
@dataclass(frozen=True)
class Action:
    action_type: Literal["launch_app", "type_text", "close_app"]
    target: Optional[str] = None
    text: Optional[str] = None
    coordinates: Optional[tuple[int, int]] = None
```

No raw dictionaries accepted by Controller.

## What's NOT in Phase-0

- ❌ LLM integration (future phases)
- ❌ Vision models (future phases)
- ❌ Playwright/browser automation
- ❌ Trading/shopping logic
- ❌ Retry logic (fails after 1 attempt)
- ❌ Multi-step reasoning

Phase-0 is the **foundation** for future capabilities.

## Logs

- **Console logs**: Real-time in terminal
- **File logs**: `agent.log`
- **Action history**: `db/history.db` (SQLite)

Query action history:
```python
from storage.action_logger import ActionLogger

logger = ActionLogger()
recent = logger.get_recent_actions(limit=10)
print(recent)
```

## Safety

All actions must pass through `PolicyEngine` before execution:

- ✓ Whitelisted apps only (defined in `config/policy.yaml`)
- ✓ No destructive filesystem operations
- ✓ Financial actions require confirmation (not in Phase-0)

## Future Phases

- **Phase-1**: LLM integration (Ollama), multi-step reasoning
- **Phase-2**: Vision models (VLM), browser automation
- **Phase-3**: Trading/shopping with confirmation popups
- **Phase-4**: Memory augmentation (ChromaDB), workflow learning

---

Built with Python 3.12, PySide6, pywinauto, and SQLite.
