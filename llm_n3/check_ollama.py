"""Check for Ollama CLI and HTTP server availability and print setup instructions.

Run this script to get actionable next steps for installing/running Ollama on your machine.
"""
import subprocess
import sys
import socket
import json

HTTP_URL = "http://127.0.0.1:11434"


def check_cli():
    try:
        out = subprocess.check_output(["ollama", "--version"], stderr=subprocess.STDOUT, universal_newlines=True)
        return True, out.strip()
    except FileNotFoundError:
        return False, "`ollama` CLI not found on PATH"
    except Exception as e:
        return False, str(e)


def check_http():
    try:
        # Lazy import requests
        import requests
    except Exception:
        return False, "`requests` not installed (optional for HTTP checks)"

    try:
        r = requests.get(HTTP_URL + "/api/models", timeout=2)
        if r.ok:
            try:
                data = r.json()
                return True, json.dumps(data)[:200]
            except Exception:
                return True, r.text[:200]
        else:
            return False, f"HTTP returned {r.status_code}"
    except Exception as e:
        return False, str(e)


def main():
    print("Ollama availability check\n" + "="*30)

    cli_ok, cli_msg = check_cli()
    print(f"CLI: {'OK' if cli_ok else 'MISSING'}")
    print(f"  {cli_msg}\n")

    http_ok, http_msg = check_http()
    print(f"HTTP API ({HTTP_URL}): {'OK' if http_ok else 'UNAVAILABLE'}")
    print(f"  {http_msg}\n")

    if cli_ok or http_ok:
        print("You can run the integration demos now. Example:")
        print("  python -m llm_n.integrate_with_project --prompt \"Play 2048 game: restart game\" --model mistral")
    else:
        print("Next steps to get Ollama working:")
        print("  1. Install Ollama: https://ollama.com/docs/installation")
        print("     - For macOS: brew install ollama (or follow Ollama installer)")
        print("     - For Windows: download the installer from Ollama docs and add `ollama` to PATH")
        print("  2. Start the Ollama daemon (if using server mode) or ensure `ollama` CLI is available on PATH")
        print("  3. (Optional) Install Python requests: pip install requests")
        print("After installation, re-run this checker to confirm availability.")


if __name__ == '__main__':
    main()
