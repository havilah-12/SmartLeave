# Smart Leave Application Agent

This project is a multi-agent HR system built with **Google ADK 2.0** and **Python 3.12+**. It orchestrates multiple autonomous agents to assist employees in applying for leave, evaluating HR policies, and securely persisting approved applications to a database.

## Architecture & Demonstration Features

This system fully satisfies all technical requirements:
1. **Parallel Execution:** `employee_agent` and `holiday_agent` execute simultaneously to fetch data from the SQLite database.
2. **Sequential Execution:** The workflow joins the parallel tasks and sequentially feeds the data into the `leave_calculation_agent`.
3. **Computation:** The `leave_calculation_agent` uses a tool to calculate precise working days (excluding weekends and holidays) and applies HR policies (e.g., maximum monthly paid leave limit).
4. **Human-in-the-loop Interactions:** The `coordinator_agent` presents a perfectly formatted summary to the human and explicitly halts execution to ask for confirmation (`Yes/No`) before submission.
5. **Database Retrieval & Data Persistence:** The system fetches records from the SQLite `employees` and `holidays` tables, and securely persists new leave requests into the `leave_applications` table.

## Tech Stack
- **Framework:** Google Agent Development Kit (ADK) 2.x
- **Language:** Python 3.12+
- **Database:** SQLite
- **Package Manager:** `uv`

## Setup Instructions

### 1. Install Dependencies
Ensure you have `uv` installed, then sync your project dependencies:
```bash
uv sync
```

### 2. Initialize the Database
Run the provided initialization script to create the SQLite database and populate it with mock employees and holidays:
```bash
python src/database/init_db.py
```

### 3. Set Environment Variables
Create a `.env` file in the root directory and add your Gemini API key:
```env
GEMINI_API_KEY="your_api_key_here"
```

### 4. Run the ADK Web UI
Start the local ADK developer server:
```bash
uv run adk web src/agents
```
Open the provided `localhost` link in your browser to interact with the `coordinator_agent`.
