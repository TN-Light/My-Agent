# 03_architecture.md

## Perception Authority Hierarchy
To eliminate "Visual Hallucination" (clicking a non-existent button), the agent must follow a strict hierarchy of data sources. Higher levels override lower levels.

| Rank | Source | Technical Tool | Reliability |
| :--- | :--- | :--- | :--- |
| **1** | **Accessibility Tree** | `pywinauto` / `UIAutomation` | **Highest** (Ground Truth for OS) |
| **2** | **DOM / Sidecar** | `Playwright` / `Extension API` | **High** (Truth for Web/IDE) |
| **3** | **Visual Scaffolding** | `SAM-2` (Object Masks) | **Medium** (Structural hints) |
| **4** | **Raw Vision / OCR** | `Molmo` / `Llama-3.2-V` / `EasyOCR` | **Lowest** (Inference-based) |

### Key Rule: No Blind Clicking
The Vision Layer (Level 4) is a **Proposal Layer** only. It suggests where a button might be. Level 1 or 2 must **Validate** the existence of that element before the Controller clicks.

## Component Layout


1. **The Brain (Actor):** Proposes a plan based on user intent and current screen state.
2. **The Critic (Verifier):** A separate, smaller model (e.g., Phi-4) tasked solely with confirming if the Actor's proposed action is logical and if the previous action succeeded.
3. **The Policy Engine:** Middleware that sits between the Brain and the Controller. It intercepts all "click" or "type" commands and checks them against `07_policy.yaml`.
4. **The Controller:** The low-level interface (`PyAutoGUI`) that moves the mouse ONLY after Policy approval.