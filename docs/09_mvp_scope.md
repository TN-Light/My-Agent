# 09_mvp_scope.md

## MVP Objectives
The Minimum Viable Product must focus on the "See-Think-Do" loop for basic productivity. We are building the *foundation*, not the final Jarvis.

### ✅ MVP INCLUDES
1. **Basic OS Control:** - Opening/Closing whitelisted apps (Chrome, VS Code, Terminal).
   - Basic window manipulation (Minimize, Maximize, Move).
2. **Deterministic UI Interaction:**
   - Clicking buttons and typing in text fields confirmed by the **Accessibility Tree**.
3. **Assisted Shopping/Trading:**
   - Navigating to a specific URL (Amazon/Zerodha).
   - Reading price/item info and asking the user: "Should I proceed with [Action]?"
4. **Simple Coding Workflow:**
   - Open VS Code to a specific directory.
   - Create a `.py` file and write a "Hello World" or basic script provided by the user.

### ❌ MVP EXCLUDES (Post-MVP)
- **Multi-Monitor Support:** The agent will only "see" and "act" on the Primary monitor.
- **Autonomous Decision Making:** No high-frequency trading or unsupervised spending.
- **Visual-Only Navigation:** If a button is not in the Accessibility Tree/DOM, the MVP will skip it rather than "guessing."
- **Natural Language Voice Input:** Interaction is text-only via the Chat UI.