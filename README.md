<div align="center">

# RecoveryAI

**An Agent Recovery Protocol (ARP) for Autonomous AI Agents**

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![SQLite](https://img.shields.io/badge/SQLite-07405E?style=for-the-badge&logo=sqlite)](https://www.sqlite.org/)
[![pytest](https://img.shields.io/badge/pytest-passing-success?style=for-the-badge&logo=pytest)](https://docs.pytest.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

*Built for the next 20 years of agentic architectures.*

</div>

---

## Overview

**RecoveryAI** (Agent Recovery Protocol - ARP) is a lightweight, stateless diagnostic microservice designed specifically to resolve failures in multi-agent systems. When autonomous AI agents execute tasks, they frequently encounter failed HTTP requests or out-of-order workflow actions. Instead of returning raw developer-facing HTTP errors (e.g. `405 Method Not Allowed`), RecoveryAI:
1. Intercepts the failure.
2. Classifies the issue into a strict deterministic error taxonomy.
3. Provides the exact request payload or corrected workflow step the agent must take next to successfully recover.

> **Design Philosophy**: To maintain strict execution simplicity for LLMs and autonomous agents, RecoveryAI provides structured, actionable instructions (the "Recovery Protocol"). This removes the need for client agents to guess raw logs, hallucinate retry arguments, or seek manual human intervention.

---

## Security & Architecture Features

We take recovery accuracy and platform stability seriously. RecoveryAI is hardened for agent interactions:

- **Deterministic Error Taxonomy:** The system restricts LLM responses to a strict, pre-defined taxonomy of failure states (e.g. `AUTH_ERROR`, `METHOD_ERROR`, `PARAMETER_ERROR`, `RATE_LIMIT`), eliminating model hallucinations.
- **Dynamic Retry Generator:** Parses failed HTTP request shapes and dynamically constructs ready-to-run corrected request structures (e.g. converting a bad POST into a query-parametrized GET).
- **Workflow Sequence Engine:** Analyzes the chronological history of agent events to detect missing prerequisites (e.g. attempts to call a ticket payment endpoint before seat reservation).
- **SQLite WAL Mode Logging:** Utilizes a local SQLite database running in Write-Ahead Logging mode to log transaction diagnoses, allowing subsequent calls to retrieve previous context safely.
- **Dual-Engine Pipeline:** Uses OpenRouter API completions (`google/gemini-2.5-flash`) for general errors, backed by a zero-latency heuristic rule engine for common hackathon cases.

---

## System Architecture

```text
recovery_ai/
├── main.py             # FastAPI router, models, and endpoints
├── db.py               # SQLite schema setup & WAL transactions
├── llm.py              # LLM integration & offline rule heuristic fallbacks
├── requirements.txt    # Pinned dependencies (fastapi, httpx, uvicorn)
├── Dockerfile          # Production OCI-compliant container build
└── test_api.py         # Comprehensive in-memory API test suite
```

---

## Quickstart & Deployment

RecoveryAI is entirely self-contained. It operates with a local SQLite database and requires no external brokers, databases, or keys for its offline fallbacks, making it highly portable.

### Local Development

```bash
# 1. Clone and enter the repository
git clone https://github.com/tanishaacodes/RecoveryAI.git
cd RecoveryAI

# 2. Set up the virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Run the test suite
python test_api.py

# 4. Start the server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Docker Deployment

RecoveryAI includes a production-ready `Dockerfile` that automatically handles environment port bindings, making it perfect for platforms like Render, Railway, or Fly.io:

```bash
docker build -t recoveryai .
docker run -p 8000:8000 recoveryai
```

---

## API Reference

### 1. Diagnose a Failure
`POST /diagnose`
Accepts a failed request context and classifies the problem into the protocol's error taxonomy.
- **Request:**
  ```json
  {
    "method": "POST",
    "url": "/weather",
    "status": 405,
    "response": "Method Not Allowed"
  }
  ```
- **Response:**
  ```json
  {
    "id": "diag_abc123",
    "problem": "Wrong HTTP method. The weather endpoint expects a GET request, not a POST request.",
    "category": "METHOD_ERROR",
    "retry": true,
    "fix": "Retry using GET instead of POST, and supply the city parameter in the query string.",
    "confidence": 0.99
  }
  ```

### 2. Get Retry Plan
`POST /retry-plan`
Retrieves the exact HTTP request format the agent should try next based on a diagnosis ID.
- **Request:**
  ```json
  {
    "diagnosis_id": "diag_abc123"
  }
  ```
- **Response:**
  ```json
  {
    "next_request": {
      "method": "GET",
      "url": "/weather?city=Boston"
    }
  }
  ```

### 3. Workflow Recovery
`POST /workflow-recovery`
Validates agent workflow sequence history and suggests correct next steps.
- **Request:**
  ```json
  {
    "goal": "Buy ticket",
    "history": [
      "checkout initialized",
      "payment failed"
    ]
  }
  ```
- **Response:**
  ```json
  {
    "next_step": "Reserve seat first to obtain reservation ID",
    "reason": "No reservation ID found in workflow history before calling payment.",
    "retry": false
  }
  ```

---

## Autonomous Agent Integration

RecoveryAI exposes a `SKILL.md` file detailing exactly how external LLMs and AI agents can autonomously format requests and handle recoveries. Agents can dynamically read this skill at runtime:
```
GET https://recoveryai-production.up.railway.app/skill.md
```
Adding this skill definition into an agent's context window enables it to call RecoveryAI and recover from API roadblocks without human intervention.
