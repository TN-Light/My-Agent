# 02_constraints.md

## Hard Constraints (Technical)
- **Zero-Subscription Dependency:** The core system must run using Free and Open Source Software (OSS).
- **Local LLM Priority:** Use **Ollama** or equivalent for local inference. Optional paid APIs (OpenAI/Anthropic) may be used for "Advanced Reasoning," but the system must be functional without them.
- **OS Compatibility:** Initial build targets Windows 10/11, utilizing the Windows UI Automation framework.
- **Offline Capability:** Core logic, vision processing (SAM-2/OpenCV), and memory (ChromaDB) must work without an internet connection.

## Safety Rules (Non-Negotiable)
1. **The Confirmation Rule:** Any action categorized as "Financial" (Trading, Shopping Checkout) or "Destructive" (Deleting system files) REQUIRES explicit user approval via a popup GUI.
2. **Read-Only by Default:** The agent should prioritize "Read" actions (Analyzing charts, checking prices) and only "Write" (Clicking, Typing) when instructed.
3. **Data Sovereignty:** No user data, screenshots, or memory logs are to be uploaded to external servers unless the user explicitly configures a cloud LLM provider.
4. **Credential Safety:** The agent is strictly FORBIDDEN from storing passwords or API keys in plain text. Use OS-level secret management (e.g., Windows Credential Manager).

## Environmental Limits
- **Resource Capping:** The agent should not consume more than 20% of CPU or 4GB of RAM in "Idle/Monitoring" mode.
- **Privacy:** Visual capture must stop immediately if the "Privacy Mode" is toggled in the System Tray.