# 05_modules.md

## Separation of Concerns
To ensure maintainability and prevent "God-Object" scripts, the codebase is divided into discrete modules. No module should overstep its functional boundary.

### 📂 `perception/`
- **`screen_capture.py`**: High-speed frame grabbing; converts pixels to tensors for the VLM.
- **`accessibility_client.py`**: Queries Windows UI Automation (UIA). Maps screen coordinates to UI elements.
- **`vision_model.py`**: Interface for local VLM (Ollama/Molmo). Handles image-to-text and object proposals.

### 📂 `logic/`
- **`brain.py`**: The "Actor." High-level reasoning, intent parsing, and step-by-step planning.
- **`critic.py`**: The "Verifier." Analyzes the screen *after* an action to confirm success or failure.
- **`policy_engine.py`**: The "Gatekeeper." Validates actions against `07_policy.yaml` before execution.

### 📂 `execution/`
- **`controller.py`**: Low-level OS control (mouse clicks, keystrokes, CLI commands).
- **`app_handlers/`**: Specific logic for complex apps (e.g., `vs_code_handler.py`, `browser_handler.py`).

### 📂 `storage/`
- **`vector_store.py`**: Interface for ChromaDB (Long-term memory/preferences).
- **`action_logger.py`**: Manages SQLite for transactional history and audit logs.

### 📂 `interface/`
- **`tray_daemon.py`**: Background process management and system tray icon.
- **`chat_ui.py`**: The PySide6 window for user instructions and "Human-in-the-Loop" confirmations.