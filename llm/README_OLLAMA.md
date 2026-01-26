Ollama setup and quick start
=================================

This folder provides a lightweight integration with Ollama (LLaMA/Mistral runtimes).

Quick checklist to use the integration:

1) Install Ollama

   - Follow: https://ollama.com/docs/installation
   - On macOS: `brew install ollama` or follow installer
   - On Windows: download installer from Ollama docs and add `ollama` to your PATH

2) (Optional) Install `requests` for HTTP checks:

   ```bash
   pip install requests
   ```

3) Start Ollama (if using daemon mode) or ensure `ollama` CLI runs in terminal.

4) Generate with the integration:

   ```bash
   python -m llm_n.integrate_with_project --prompt "Play 2048 game: restart game" --model mistral
   ```

Utilities
---------

- `check_ollama.py` — quick script to detect `ollama` CLI and HTTP server availability and print next steps.
- `ollama_client.py` — wrapper that calls Ollama HTTP API or CLI fallback.
- `ollama_adapter.py` — converts Ollama text outputs into the project's step schema.
- `integrate_with_project.py` — writes formatted results into the project (default inside `llm_n`).

If you want me to attempt a live generation now, I can run the checker and then the integration command once Ollama is available on your machine.

Automated installer script
-------------------------

An automated PowerShell installer is provided: `install_ollama.ps1`.

Usage (PowerShell, run from project root):

```powershell
cd llm_n
.
\install_ollama.ps1
```

Options:
- `-RunIntegration` : after install, also run the integration demo (may require elevated prompt for installer).

Example:

```powershell
.
\install_ollama.ps1 -RunIntegration -IntegrationArgs "--prompt \"Play 2048 game: restart game\" --model mistral"
```
