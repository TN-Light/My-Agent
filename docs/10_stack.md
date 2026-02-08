# 10_stack.md

## 2026 Standardized Tech Stack
To maintain consistency, the agent must stick to these versions and libraries. No switching to unverified "experimental" frameworks.

| Layer | Technology | Version / Spec |
| :--- | :--- | :--- |
| **Language** | **Python** | 3.12 (Stable version) |
| **Brain (LLM)** | **Ollama** | Local hosting; `Llama 3.2` or `Phi-4` |
| **Vision (VLM)** | **Qwen3-VL** | Local via Ollama (Excellent 2026 performance) |
| **UI Framework** | **PySide6** | 6.10.1 (Official Qt for Python) |
| **OS Control** | **pywinauto** | Using `backend="uia"` for Windows accessibility |
| **Screen Math** | **OpenCV** | 4.x (For basic pixel math and masking) |
| **Memory (Vector)**| **ChromaDB** | Using `PersistentClient` for local disk storage |
| **Memory (Relational)**| **SQLite** | Standard library; for audit logs and history |

## Coding Standards
1. **Type Hinting:** All functions must have Python type hints (e.g., `def act(coords: tuple) -> bool:`).
2. **Async-First:** Use `asyncio` for the tray daemon and chat UI to prevent the interface from freezing during "Brain" reasoning.
3. **Graceful Degradation:** If the VLM (Layer 4) fails to load, the system must still function using the Accessibility Tree (Layer 1).
4. **Comment Density:** Every class and public method must have a docstring explaining its role in the "Perception Authority Hierarchy."