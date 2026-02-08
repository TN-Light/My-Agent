# 01_project_vision.md

## Project Vision
Build a local-first, desktop-resident AI agent that acts as a "Digital Twin" for productivity, trading assistance, and computer control. The agent must be capable of perceiving the screen, reasoning about intent, and executing actions with precision and safety.

### Core Pillars
- **Local-First:** All primary reasoning, screen processing, and memory storage must happen on the user's machine.
- **Persistent Presence:** Runs as a background daemon with a System Tray interface for constant accessibility.
- **Multimodal Perception:** Uses a "Tri-Layer" approach (Accessibility Tree, DOM/API, and Vision) to understand the screen.
- **Action-Oriented:** Not just a chatbot; it must control the OS (mouse, keyboard, CLI) to fulfill tasks.
- **Memory-Augmented:** Uses persistent local storage to remember user preferences and past workflow outcomes.

## Non-Goals
To prevent feature creep and maintain architectural integrity, the following are explicitly **OUT OF SCOPE**:
- **SaaS/Cloud Hosting:** This is NOT a web-hosted service. It must never require a central server to function.
- **Autonomous Financial Risk:** This is NOT an "Auto-Trader" that can spend money without a human-in-the-loop confirmation.
- **Browser-Only Tool:** This is NOT a Chrome extension. It must work across the entire OS (VS Code, Desktop Apps, Terminal).
- **Perfect Vision:** We do not expect 100% accuracy from raw pixels; we prioritize structured data (Accessibility/DOM) over visual guessing.
- **Hardware Control:** No integration with external IoT or hardware beyond the standard PC peripherals.

## Success Metric
The project is successful if a user can give a natural language instruction (e.g., "Add a mechanical keyboard to my Amazon cart" or "Setup a new Python project in VS Code") and the agent executes the steps correctly while verifying each action.