🧠 A Human-Like Agent for Screen-Aware Task Automation
📘 Project Summary

An Agentic AI-based automation system that observes a computer screen using an external camera and performs keyboard and mouse actions through Bluetooth HID emulation.
Unlike traditional automation tools, ScreenPilot works in black-box environments — no APIs, no installations, and no system-level access — making it ideal for legacy systems, secure environments, and exploratory testing.

The system follows a human-like Perceive → Plan → Act → Evaluate loop:

Perceive: Capture and analyze live screen visuals using a camera (OpenCV + OCR).
Plan: Interpret LLM-based instructions and plan contextual actions.
Act: Execute keyboard/mouse actions via an ESP32-based HID emulator.
Evaluate: Verify task success using visual feedback and logs.

