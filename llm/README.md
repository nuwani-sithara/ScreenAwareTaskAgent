# LLM Prompt Engineering - Human-like Test Automation Agent

## Project Overview

This project implements a **human-like test automation agent** that executes **functional and exploratory testing** based on **natural language instructions**. It leverages **Large Language Models (LLMs)** and prompt engineering to convert human instructions into automated test scripts, eliminating the need for manual scripting.

---

## Motivation / Problem Statement

Automated testing tools today often require scripting, lack natural language support, and struggle to adapt to dynamic user interfaces.  
This project addresses these issues by:  
- Accepting natural language test instructions.  
- Generating automation scripts dynamically.  
- Adapting to UI changes without manual intervention.  

---

## Key Features

- **Natural Language Driven:** Enter test instructions in plain English.  
- **Functional & Exploratory Testing:** Supports multiple test scenarios.  
- **Dynamic UI Adaptation:** Handles changes in the application interface automatically.  
- **No Manual Scripting Required:** LLMs generate automation steps intelligently.  

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/Tharushi-Nethmini/LLM_PromptEngineering.git
cd LLM_PromptEngineering

2. Create and activate a virtual environment

Windows PowerShell:

python -m venv venv
venv\Scripts\Activate.ps1


Windows Command Prompt (cmd):

python -m venv venv
venv\Scripts\activate.bat

3. Install dependencies
pip install -r requirements.txt


This installs all required packages, including:
hf_xet, huggingface_hub[hf_xet], selenium, webdriver-manager, transformers, torch, langchain-community, and others.

Usage

Ensure the virtual environment is activated.

Run the main script:

python demo.py


Enter your test instructions in natural language.

The agent will perform the corresponding automation steps.

Project Structure
LLM_PromptEngineering/
├─ demo.py                  # Main script to test automation agent
├─ requirements.txt         # Python dependencies
├─ .gitignore               # Ignored files like venv, __pycache__, .env
├─ README.md                # Project documentation
└─ venv/                    # Virtual environment (ignored in Git)

Dependencies

Python 3.11+

Libraries: torch, transformers, selenium, webdriver-manager, langchain-community, hf_xet, huggingface_hub[hf_xet]

Notes

Do not commit the venv/ folder — it is ignored via .gitignore.

Use requirements.txt to recreate the environment on another machine:

python -m venv venv
pip install -r requirements.txt


Make sure your system has Python 3.11 or higher installed.

References

Hugging Face Transformers Documentation

LangChain Documentation

Selenium WebDriver Documentation

License

This project is for academic purposes (Final Year Project) and may be adapted for non-commercial research use.


