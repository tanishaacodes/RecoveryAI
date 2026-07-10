# RecoveryAI (Agent Recovery Protocol)

RecoveryAI (Agent Recovery Protocol - ARP) is a microservice designed to help autonomous AI agents recover from API failures and workflow execution blocks. Instead of returning raw, developer-centric HTTP errors (like `405 Method Not Allowed`), RecoveryAI classifies errors into a strict deterministic taxonomy, diagnoses the root cause, and returns structured, actionable instructions (and concrete retry payloads) that an agent can parse to dynamically recover.

## Features
- **API Call Diagnosis**: Identifies errors, determines retry safety, and suggests precise fixes.
- **Dynamic Retry Plans**: Translates diagnosis data into corrected HTTP requests.
- **Workflow Order Validation**: Detects out-of-order execution states and points out missing steps (e.g. paying before booking).
- **Taxonomy Enforcement**: Restricts diagnostics to a deterministic list of categories.
- **Micro-Plan Generator**: Generates custom recovery check-lists, confidence values, and estimated success rates.
- **Dual-Engine Pipeline**: Uses OpenRouter (Gemini/Claude) for intelligent reasoning and a robust local rule-fallback engine for common cases.

---

## Getting Started

### Prerequisites
- Python 3.12+
- (Optional) OpenRouter API Key

### Local Installation
1. Navigate to the project directory:
   ```bash
   cd recovery_ai
   ```

2. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set your environment variables (optional, for LLM support):
   ```bash
   export OPENROUTER_API_KEY="your_api_key_here"
   ```

5. Start the FastAPI server:
   ```bash
   uvicorn main:app --reload --port 8000
   ```

6. Open your browser and navigate to `http://localhost:8000` to view the interactive API reference documentation.

---

## Hosting & Deployment

RecoveryAI is stateless and uses a local SQLite database in WAL mode, making it extremely easy to host.

### Containerized Deployment (Render, Railway, Fly.io)
You can deploy this repository directly using the provided `Dockerfile`.

1. Deploy the directory on your platform (e.g., connect GitHub repository or use CLI).
2. Set the environment variable `OPENROUTER_API_KEY` in your settings.
3. The server will dynamically bind to the platform's `$PORT` environment variable and start listening.

---

## NANDA Agent Integration

Stock AI agents can discover and use this service autonomously. Copy `SKILL.md` to your agent's customization directory or direct the agent to fetch the raw skill file from:
```
GET https://<your-hosted-endpoint>/skill.md
```
The agent reads this markdown file, learns the JSON schemas, and intercepts any error states by sending details to `/diagnose` and `/retry-plan`.
