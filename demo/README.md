# Safe Demo Subsystem (Dedicated Demo Package)
> **Implementation status notice (2026-10-26):** The former process-spawn/suspend demo is retired. The supported demonstration is the synthetic disk-cache workflow described in the root `README.md`.

This directory contains the isolated demonstration subsystem for **Zombie Data & Task Purger**.

It is completely separated from the core analysis engine to ensure clean modularity, absolute safety, and easy demonstration for academic reviews and college viva.

---

## 📂 Directory Structure

| File | Purpose |
|---|---|
| __init__.py | Package initializer exposing DemoTaskManager and create_safe_demo_environment |
| demo_tasks.py | Lifecycle manager for simulated background applications (spawning, tracking, termination) |
| demo_worker.py | Standalone worker process simulating RAM allocation, I/O rates, and idle states |
| demo_data.py | File sandbox generator creating backdated cache/temp/log files and active databases |
| 
un_demo.py | Standalone 1-click automated demo runner executing all 5 presentation steps |
| 	est_demo.py | Verification test suite testing spawning, classification, suspension, and resumption |

---

## 🎯 The 6 Simulated Demo Applications

| Application | Role / Simulated Behavior | Expected Result |
|---|---|---|
| **Google Chrome** | Active file download (> 200 KB/s write rate) | **PROTECTED** (Score 0) |
| **WhatsApp Desktop** | Closed to tray (0 visible windows, 52 mins idle) | **POTENTIAL ZOMBIE** (Score 85) |
| **Oracle Database** | Background daemon service (2 days idle) | **POTENTIAL ZOMBIE** (Score 100) |
| **Node.js Dev Server** | Forgotten background console process (3 hrs idle) | **POTENTIAL ZOMBIE** (Score 85) |
| **Python Worker** | Orphaned background worker script (2 hrs idle) | **POTENTIAL ZOMBIE** (Score 85) |
| **Spotify Player** | Active audio stream (music playing in background) | **PROTECTED** (Score 0) |

---

## 🚀 How to Run the Demo

### 1. Standalone Automated Demo (Command Line)
From the project root:
`powershell
python demo/run_demo.py
`

### 2. Full Graphical User Interface (GUI)
From the project root:
`powershell
python main.py
`
Then click the **🚀 Guided College Demo Walkthrough** button at the top right!
