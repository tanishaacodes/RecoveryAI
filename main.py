from fastapi import FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from uuid import uuid4
from contextlib import asynccontextmanager
import pathlib

import db
import llm

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize the SQLite database tables on startup
    db.init_db()
    yield

app = FastAPI(
    title="RecoveryAI - Agent Recovery Protocol (ARP)",
    description="Diagnoses failed API calls and tells AI agents exactly how to recover.",
    version="1.0.0",
    lifespan=lifespan
)

# --- Pydantic Schemas ---

class DiagnoseInput(BaseModel):
    method: str = Field(..., example="POST", description="HTTP request method")
    url: str = Field(..., example="/weather", description="Requested URL path or full URL")
    status: int = Field(..., example=405, description="Received HTTP status code")
    response: str = Field(..., example="Method Not Allowed", description="Raw HTTP response body or message")

class DiagnoseOutput(BaseModel):
    id: str = Field(..., description="Unique diagnosis ID")
    problem: str = Field(..., description="Identified problem description")
    category: str = Field(..., description="Taxonomy classification category")
    retry: bool = Field(..., description="Whether a retry is safe and suggested")
    fix: str = Field(..., description="Actionable correction instruction for the agent")
    confidence: float = Field(..., description="Confidence score between 0.0 and 1.0")

class RetryPlanInput(BaseModel):
    diagnosis_id: str = Field(..., example="diag_abc123", description="ID returned by /diagnose")

class RetryPlanOutput(BaseModel):
    next_request: Dict[str, Any] = Field(..., description="Corrected HTTP request parameters")

class ExplainInput(BaseModel):
    status: int = Field(..., example=429, description="Received HTTP status code")
    body: str = Field(..., example="Rate limit exceeded", description="Raw response content")

class ExplainOutput(BaseModel):
    meaning: str = Field(..., description="Simplified explanation of the error meaning")
    wait_seconds: int = Field(..., description="Number of seconds the agent should wait before retrying")
    retry: bool = Field(..., description="Whether a retry is safe")

class WorkflowRecoveryInput(BaseModel):
    goal: str = Field(..., example="Buy ticket", description="The agent's target objective")
    history: List[str] = Field(..., example=["Reserve seat", "Payment failed"], description="Chronological log of events/actions")

class WorkflowRecoveryOutput(BaseModel):
    next_step: str = Field(..., description="The correct next action/step the agent should take")
    reason: str = Field(..., description="Explanation of why this action is correct")
    retry: bool = Field(..., description="Whether the last failed action should be retried directly")

class RecoverInput(BaseModel):
    status: int = Field(..., example=404, description="Received HTTP status code")
    body: str = Field(..., example="Not Found", description="Raw response text")

class RecoverOutput(BaseModel):
    plan: List[str] = Field(..., description="Ordered recovery checklist steps")
    severity: str = Field(..., description="Problem severity classification (LOW, MEDIUM, HIGH, CRITICAL)")
    confidence: int = Field(..., description="Confidence score from 0 to 100")
    recoverable: bool = Field(..., description="Whether recovery is possible")
    estimated_success: int = Field(..., description="Estimated success probability percent")

# --- Routes ---

@app.get("/health", status_code=status.HTTP_200_OK)
def health():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}

@app.post("/diagnose", response_model=DiagnoseOutput)
async def diagnose(data: DiagnoseInput):
    """Diagnose a failed API call, classify it in the taxonomy, and return a structured recovery fix."""
    diagnosis = await llm.diagnose_error(data.method, data.url, data.status, data.response)
    
    diag_id = f"diag_{uuid4().hex[:12]}"
    
    # Persist the diagnosis in SQLite
    db.save_diagnosis(
        diag_id=diag_id,
        method=data.method,
        url=data.url,
        status=data.status,
        response=data.response,
        problem=diagnosis["problem"],
        category=diagnosis["category"],
        retry=diagnosis["retry"],
        fix=diagnosis["fix"],
        confidence=diagnosis["confidence"]
    )
    
    return {
        "id": diag_id,
        "problem": diagnosis["problem"],
        "category": diagnosis["category"],
        "retry": diagnosis["retry"],
        "fix": diagnosis["fix"],
        "confidence": diagnosis["confidence"]
    }

@app.post("/retry-plan", response_model=RetryPlanOutput)
async def retry_plan(data: RetryPlanInput):
    """Suggest the exact request structure to try next based on a previous diagnosis ID."""
    diagnosis = db.get_diagnosis(data.diagnosis_id)
    if not diagnosis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Diagnosis with ID {data.diagnosis_id} not found."
        )
    
    plan = await llm.suggest_retry(diagnosis)
    return plan

@app.post("/explain", response_model=ExplainOutput)
async def explain(data: ExplainInput):
    """Explain an API error status/response body and indicate retry safety and waiting time."""
    explanation = await llm.explain_error(data.status, data.body)
    return explanation

@app.post("/workflow-recovery", response_model=WorkflowRecoveryOutput)
async def workflow_rec(data: WorkflowRecoveryInput):
    """Inspect agent goal and history of actions, detect out-of-order execution, and return correct next action."""
    recovery = await llm.workflow_recovery(data.goal, data.history)
    
    wf_id = f"wf_{uuid4().hex[:12]}"
    # Save workflow trace to DB
    db.save_workflow(
        wf_id=wf_id,
        goal=data.goal,
        history=data.history,
        next_step=recovery["next_step"],
        reason=recovery["reason"],
        retry=recovery["retry"]
    )
    
    return recovery

@app.post("/recover", response_model=RecoverOutput)
async def recover(data: RecoverInput):
    """Generate a multi-step recovery checklist plan, severity classification, and recovery metrics."""
    plan = await llm.recover_plan(data.status, data.body)
    return plan

@app.get("/skill.md", response_class=PlainTextResponse)
def get_skill():
    """Serve the NANDA-compliant SKILL.md file contents for agent consumption."""
    skill_path = pathlib.Path(__file__).parent / "SKILL.md"
    if skill_path.exists():
        return skill_path.read_text()
    raise HTTPException(status_code=404, detail="SKILL.md file not found on server.")

@app.get("/", response_class=HTMLResponse)
def home():
    """Serve a premium developer-friendly API reference page for RecoveryAI."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RecoveryAI - Agent Recovery Protocol</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #08090f;
            --card-bg: rgba(255, 255, 255, 0.03);
            --border-color: rgba(255, 255, 255, 0.08);
            --text-color: #e2e8f0;
            --text-muted: #94a3b8;
            --accent-primary: #818cf8;
            --accent-secondary: #06b6d4;
            --success: #10b981;
        }
        body {
            background-color: var(--bg-color);
            color: var(--text-color);
            font-family: 'Outfit', sans-serif;
            margin: 0;
            padding: 0;
            line-height: 1.6;
        }
        .container {
            max-width: 1000px;
            margin: 0 auto;
            padding: 40px 20px;
        }
        header {
            text-align: center;
            margin-bottom: 60px;
            position: relative;
        }
        header::after {
            content: '';
            position: absolute;
            bottom: -20px;
            left: 50%;
            transform: translateX(-50%);
            width: 100px;
            height: 3px;
            background: linear-gradient(90deg, var(--accent-primary), var(--accent-secondary));
            border-radius: 2px;
        }
        h1 {
            font-size: 3rem;
            font-weight: 800;
            margin: 0;
            background: linear-gradient(135deg, #fff 30%, var(--accent-primary) 70%, var(--accent-secondary) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .subtitle {
            font-size: 1.2rem;
            color: var(--text-muted);
            margin-top: 10px;
        }
        .grid {
            display: grid;
            grid-template-columns: 1fr;
            gap: 30px;
        }
        .card {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 30px;
            backdrop-filter: blur(12px);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .card:hover {
            border-color: rgba(129, 140, 248, 0.4);
            box-shadow: 0 10px 30px -10px rgba(129, 140, 248, 0.15);
            transform: translateY(-2px);
        }
        h2 {
            font-size: 1.5rem;
            color: #fff;
            margin-top: 0;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .endpoint-badge {
            font-size: 0.8rem;
            padding: 4px 10px;
            border-radius: 6px;
            font-family: 'Fira Code', monospace;
            font-weight: 500;
        }
        .post {
            background-color: rgba(6, 182, 212, 0.15);
            color: var(--accent-secondary);
            border: 1px solid rgba(6, 182, 212, 0.3);
        }
        .get {
            background-color: rgba(16, 185, 129, 0.15);
            color: var(--success);
            border: 1px solid rgba(16, 185, 129, 0.3);
        }
        p {
            color: var(--text-muted);
        }
        pre {
            background-color: #030408;
            border: 1px solid var(--border-color);
            padding: 18px;
            border-radius: 8px;
            overflow-x: auto;
            font-family: 'Fira Code', monospace;
            font-size: 0.9rem;
            color: #38bdf8;
        }
        .taxonomy-container {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 15px;
        }
        .taxonomy-badge {
            font-family: 'Fira Code', monospace;
            font-size: 0.75rem;
            padding: 4px 8px;
            background-color: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            color: #c084fc;
        }
        .skill-link {
            text-align: center;
            margin-top: 40px;
        }
        .btn {
            display: inline-block;
            padding: 12px 28px;
            background: linear-gradient(135deg, var(--accent-primary), #6366f1);
            color: #fff;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 600;
            transition: opacity 0.2s;
        }
        .btn:hover {
            opacity: 0.9;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>RecoveryAI</h1>
            <div class="subtitle">Agent Recovery Protocol (ARP) — Diagnoses failures and recovers AI agents</div>
        </header>

        <div class="grid">
            <div class="card">
                <h2><span class="endpoint-badge post">POST</span> /diagnose</h2>
                <p>Accepts a failed request parameters and returns a classification problem, category validation, retry instruction, and confidence.</p>
                <pre>Input:
{
  "method": "POST",
  "url": "/weather",
  "status": 405,
  "response": "Method Not Allowed"
}

Output:
{
  "id": "diag_abc123",
  "problem": "Wrong HTTP method",
  "category": "METHOD_ERROR",
  "retry": true,
  "fix": "Use GET instead",
  "confidence": 0.99
}</pre>
            </div>

            <div class="card">
                <h2><span class="endpoint-badge post">POST</span> /retry-plan</h2>
                <p>Generates the corrected HTTP request query and setup to attempt recovery based on a previous diagnosis ID.</p>
                <pre>Input:
{
  "diagnosis_id": "diag_abc123"
}

Output:
{
  "next_request": {
    "method": "GET",
    "url": "/weather?city=Boston"
  }
}</pre>
            </div>

            <div class="card">
                <h2><span class="endpoint-badge post">POST</span> /explain</h2>
                <p>Explains error meaning, wait time requirements, and safe retry conditions in agent-friendly fields.</p>
                <pre>Input:
{
  "status": 429,
  "body": "Rate limit exceeded"
}

Output:
{
  "meaning": "Too many requests",
  "wait_seconds": 60,
  "retry": true
}</pre>
            </div>

            <div class="card">
                <h2><span class="endpoint-badge post">POST</span> /workflow-recovery</h2>
                <p>Detects out-of-order execution states in workflow history and provides correct next step directions.</p>
                <pre>Input:
{
  "goal": "Buy ticket",
  "history": ["payment failed"]
}

Output:
{
  "next_step": "Reserve seat first",
  "reason": "No reservation ID found",
  "retry": false
}</pre>
            </div>

            <div class="card">
                <h2><span class="endpoint-badge post">POST</span> /recover</h2>
                <p>Outputs a structured list plan checklist, estimated success rates, and severity index indicators.</p>
                <pre>Input:
{
  "status": 404,
  "body": "Not Found"
}

Output:
{
  "plan": [
    "Verify endpoint exists",
    "Check version",
    "Verify base URL",
    "Retry"
  ],
  "severity": "HIGH",
  "confidence": 97,
  "recoverable": true,
  "estimated_success": 94
}</pre>
            </div>

            <div class="card">
                <h2>Deterministic Error Taxonomy</h2>
                <p>Autonomous AI agents are restricted to classyfying failures under these exact protocol categories:</p>
                <div class="taxonomy-container">
                    <span class="taxonomy-badge">AUTH_ERROR</span>
                    <span class="taxonomy-badge">METHOD_ERROR</span>
                    <span class="taxonomy-badge">PARAMETER_ERROR</span>
                    <span class="taxonomy-badge">TIMEOUT</span>
                    <span class="taxonomy-badge">RATE_LIMIT</span>
                    <span class="taxonomy-badge">NETWORK</span>
                    <span class="taxonomy-badge">JSON_FORMAT</span>
                    <span class="taxonomy-badge">SCHEMA_ERROR</span>
                    <span class="taxonomy-badge">PERMISSION_DENIED</span>
                    <span class="taxonomy-badge">RESOURCE_NOT_FOUND</span>
                    <span class="taxonomy-badge">SERVER_ERROR</span>
                    <span class="taxonomy-badge">SERVICE_SLEEPING</span>
                    <span class="taxonomy-badge">DEPENDENCY_DOWN</span>
                </div>
            </div>
            
            <div class="card">
                <h2><span class="endpoint-badge get">GET</span> /skill.md</h2>
                <p>Fetches the machine-readable skill instruction page so autonomous stock agents can discover and dynamically call this service.</p>
            </div>
        </div>

        <div class="skill-link">
            <a href="/skill.md" class="btn">View Raw SKILL.md</a>
        </div>
    </div>
</body>
</html>"""
