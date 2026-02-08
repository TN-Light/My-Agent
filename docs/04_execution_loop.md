# 04. Execution Loop Architecture

## Overview
The execution logic has been decoupled from the main entry point and centralized in the `ExecutionEngine` class. This engine orchestrates the cycle of Planning, Acting, and Verifying, ensuring that every instruction follows a strict safety and validation protocol.

## The Execution Cycle

### 1. Plan (Logic Layer)
- **Component**: `Planner` (`logic/planner.py`)
- **Input**: Natural language instruction (e.g., "Open notepad and type hello").
- **Process**:
    - **Parsing**: Decomposes complex instructions into atomic sub-tasks using recursive decomposition.
    - **Graph Generation**: Creates a `PlanGraph` of `PlanStep`s.
    - **Strategy**: 
        - **Deterministic**: For standard OS commands (open, type, close) to ensure speed and reliability.
        - **LLM-based**: For complex reasoning or unknown tasks (future phase).
- **Output**: A sequence of `Action` objects (e.g., `launch_app`, `type_text`).

### 2. Policy & Approval (Safety Layer)
- **Component**: `ExecutionEngine` + `User Interaction`
- **Process**:
    - **Policy Check**: Validates that intended actions do not violate restrictions (e.g., restricted file paths).
    - **Human-in-the-Loop**: If a plan contains critical actions or if configured for "step-by-step" mode, the engine pauses and requests user approval via the UI/CLI.

### 3. Act (Execution Layer)
- **Component**: `Controller` (`execution/controller.py`)
- **Input**: A validated `Action` object.
- **Process**:
    - **Context Routing**: Routes action to the appropriate handler (Desktop, Web, File).
    - **Execution**: Uses `pywinauto` regarding Windows Automation and `keyboard` library for reliable text injection.
    - **Robustness**: 
        - Handles modal dialogs (e.g., "Save As", "Unsaved Changes").
        - Manages window focus and "Freshness Checks" (ensuring new documents).
        - Translates virtual commands (e.g., `^s` -> `Ctrl+S`) for compatibility.

### 4. Verify & Observe (Perception Layer)
- **Component**: `Critic` / `Observer`
- **Process**:
    - **Verification**: Checks if the action had the intended effect (e.g., Did the window open? Did the file save?).
    - **Feedback**: Provides success/failure signals back to the engine.

## Code Structure

```mermaid
graph TD
    User[User Instruction] --> Engine[Execution Engine]
    
    subgraph "Logic Layer"
        Engine --> Planner
        Planner --> Plan[Plan Graph]
    end
    
    subgraph "Execution Layer"
        Engine --> Controller
        Controller --> Desktop[Desktop (pywinauto/keyboard)]
        Controller --> Web[Web (Playwright)]
    end
    
    subgraph "Safety Layer"
        Plan --> Policy[Policy Check]
        Policy --> Approval{User Approval?}
    end
    
    Approval -- Yes --> Controller
    Approval -- No --> Abort
```

## Failure Recovery
- **Planner Repair**: The planner detects sequences that are prone to failure (e.g., "Close" immediately after "Type") and injects safety buffers (e.g., `wait` actions).
- **Dialog Handling**: The controller automatically detects blocking dialogs (like "Do you want to save?") and handles them gracefully (defaults to "Don't Save" for cleanup).
