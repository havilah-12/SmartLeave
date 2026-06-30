# Smart Leave Application Agent

This project is a multi-agent HR system built with **Google ADK 2.0** and **Python 3.13**. It orchestrates multiple autonomous agents to assist employees in applying for leave, evaluating HR policies, and securely persisting approved applications to a database.

## Architecture & Demonstration Features

This system fully satisfies all technical requirements:
1. **Parallel Execution:** `employee_agent` and `holiday_agent` execute simultaneously to fetch data from the SQLite database.
2. **Sequential Execution:** The workflow joins the parallel tasks and sequentially feeds the data into the `leave_calculation_agent`.
3. **Computation:** The `leave_calculation_agent` uses a tool to calculate precise working days (excluding weekends and holidays) and applies HR policies (e.g., maximum monthly paid leave limit).
4. **Human-in-the-loop Interactions:** The system presents a perfectly formatted summary to the human and explicitly halts execution to ask for confirmation (`Yes/No`) before submission.
5. **Database Retrieval & Data Persistence:** The system fetches records from the SQLite `employees` and `holidays` tables, and securely persists new leave requests into the `leave_applications` table.

## Tech Stack
- **Framework:** Google Agent Development Kit (ADK) 2.x
- **Language:** Python 3.13
- **Database:** SQLite
- **Package Manager:** `uv`

---

## 🚀 Complete Command Guide

### 1. Project Setup & Database Initialization
*Run these commands to set up your environment from scratch.*

**Step 1: Set up the environment and install dependencies**
```bash
uv venv
uv sync
```

**Step 2: Configure your API Key**
Create a `.env` file in the root directory (or export it in your terminal) with your Gemini API key:
```env
GEMINI_API_KEY="your_api_key_here"
```

**Step 3: Initialize the Database**
This command will create the SQLite database and automatically populate it with mock employees, HR admins, and public holidays.
```bash
uv run python src/database/init_db.py
```

### 2. Local Testing (ADK Web UI)
*Run this command to test your agent on your local machine using the built-in UI.*

```bash
uv run adk web src/workflows
```
*After running, open `http://localhost:8080` in your browser.*

### 3. Deploy to Google Cloud (Agent Engine)
*Run these commands to deploy your workflows as highly scalable cloud APIs.*

**Step 1: Authenticate with Google Cloud**
```bash
gcloud auth login
gcloud auth application-default login
```

**Step 2: Deploy the Parallel Agent Workflow**
```bash
uv run adk deploy agent_engine src/workflows/leaves_agent_parallel --project id --region us-central1
```

**Step 3: Deploy the Sequential Agent Workflow**
```bash
uv run adk deploy agent_engine src/workflows/leaves_agent_sequential --project id --region us-central1
```

### 4. Interact with the Deployed Cloud Agent
*Run these commands to connect the local UI to your live cloud deployments (acting as a thin client).*

**Test the Deployed Parallel Agent:**
```bash
uv run adk web src/workflows --session_service_uri "agentengine://7161161562902757376"
```

**Test the Deployed Sequential Agent:**
```bash
uv run adk web src/workflows --session_service_uri "agentengine://5545776671560302592"
```
*(If you deploy again in the future, just replace the numbers at the end of the `agentengine://` URI with your new Resource IDs!)*
