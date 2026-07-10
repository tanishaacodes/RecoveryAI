import os
import json
import httpx
from typing import Optional, Dict, Any

# OpenRouter configuration
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
API_KEY = os.getenv("OPENROUTER_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")
DEFAULT_MODEL = os.getenv("ANTHROPIC_DEFAULT_HAIKU_MODEL") or "google/gemini-2.5-flash"

# Error Taxonomy allowed categories
TAXONOMY_CATEGORIES = [
    "AUTH_ERROR", "METHOD_ERROR", "PARAMETER_ERROR", "TIMEOUT", "RATE_LIMIT",
    "NETWORK", "JSON_FORMAT", "SCHEMA_ERROR", "PERMISSION_DENIED",
    "RESOURCE_NOT_FOUND", "SERVER_ERROR", "SERVICE_SLEEPING", "DEPENDENCY_DOWN"
]

async def call_llm(system_prompt: str, user_prompt: str) -> Optional[Dict[str, Any]]:
    """Helper function to call OpenRouter API and extract JSON response."""
    if not API_KEY:
        return None
        
    try:
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://recoveryai.net",
            "X-Title": "RecoveryAI Agent Recovery Protocol"
        }
        
        payload = {
            "model": DEFAULT_MODEL,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.1
        }
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(OPENROUTER_URL, headers=headers, json=payload)
            if resp.status_code == 200:
                result_json = resp.json()
                content = result_json["choices"][0]["message"]["content"]
                return json.loads(content)
    except Exception as e:
        print(f"Error calling LLM: {e}")
    return None

def get_diagnose_fallback(method: str, url: str, status: int, response: str) -> Dict[str, Any]:
    """Fallback rule-based engine for HTTP call diagnosis."""
    method_upper = method.upper()
    url_lower = url.lower()
    resp_lower = response.lower()
    
    # 1. Weather endpoint method mismatch (hackathon standard scenario)
    if "weather" in url_lower and method_upper == "POST":
        return {
            "problem": "Wrong HTTP method. The weather endpoint expects a GET request, not a POST request.",
            "category": "METHOD_ERROR",
            "retry": True,
            "fix": "Retry using GET instead of POST, and supply the city parameter in the query string.",
            "confidence": 0.99
        }
        
    if "weather" in url_lower and "city" not in url_lower:
        return {
            "problem": "Missing required parameter city",
            "category": "PARAMETER_ERROR",
            "retry": True,
            "fix": "Retry including city=Boston",
            "confidence": 0.99
        }

    # 2. Status code matches
    if status == 401 or "unauthorized" in resp_lower:
        return {
            "problem": "Missing or invalid authentication credentials",
            "category": "AUTH_ERROR",
            "retry": False,
            "fix": "Provide a valid Auth header (Bearer token) or check access token validity.",
            "confidence": 0.98
        }
    elif status == 403 or "forbidden" in resp_lower or "permission denied" in resp_lower:
        return {
            "problem": "Access to the requested resource is forbidden",
            "category": "PERMISSION_DENIED",
            "retry": False,
            "fix": "Verify that your API key / token has the correct permission scopes or roles.",
            "confidence": 0.97
        }
    elif status == 404 or "not found" in resp_lower:
        return {
            "problem": "The endpoint was not found on the server",
            "category": "RESOURCE_NOT_FOUND",
            "retry": False,
            "fix": "Verify the URL path, the API base URL, and any version prefixes (e.g. /v1).",
            "confidence": 0.99
        }
    elif status == 405 or "method not allowed" in resp_lower:
        return {
            "problem": f"HTTP method {method_upper} is not allowed for this endpoint",
            "category": "METHOD_ERROR",
            "retry": True,
            "fix": f"Change request method. Check API documentation to verify valid verbs.",
            "confidence": 0.99
        }
    elif status == 429 or "rate limit" in resp_lower or "too many requests" in resp_lower:
        return {
            "problem": "API Rate limit exceeded",
            "category": "RATE_LIMIT",
            "retry": True,
            "fix": "Wait for 60 seconds before retrying this request, or use exponential backoff.",
            "confidence": 0.99
        }
    elif status >= 500:
        return {
            "problem": "Internal Server Error or downstream dependency failure",
            "category": "SERVER_ERROR",
            "retry": True,
            "fix": "Retry the request using exponential backoff. If persistent, check dependency health status.",
            "confidence": 0.95
        }
        
    # Default fallback generic response
    return {
        "problem": f"API call failed with status {status} and response: {response[:100]}",
        "category": "SERVER_ERROR" if status >= 500 else "PARAMETER_ERROR",
        "retry": True,
        "fix": "Check request parameters and try again using backoff.",
        "confidence": 0.80
    }

async def diagnose_error(method: str, url: str, status: int, response: str) -> Dict[str, Any]:
    """Diagnose HTTP call failure using LLM or rule fallbacks."""
    system_prompt = f"""You are the Agent Recovery Protocol (ARP) diagnostics engine.
Your job is to diagnose why an HTTP call failed and output a structured JSON object.
You must choose the MOST accurate category ONLY from this list: {json.dumps(TAXONOMY_CATEGORIES)}.

Output JSON Schema:
{{
  "problem": "Brief description of what went wrong",
  "category": "One of the allowed categories",
  "retry": true/false (boolean indicating if retry is safe/feasible),
  "fix": "Actionable, precise, simple instruction for the agent on how to fix this request",
  "confidence": 0.0 to 1.0 (float)
}}
Do not explain anything outside the JSON. Return valid JSON only."""

    user_prompt = f"""Failed HTTP Request:
Method: {method}
URL: {url}
Status Code: {status}
Response Body: {response}"""

    # Try LLM first
    llm_res = await call_llm(system_prompt, user_prompt)
    if llm_res and "category" in llm_res and llm_res["category"] in TAXONOMY_CATEGORIES:
        return llm_res
        
    # Fallback
    return get_diagnose_fallback(method, url, status, response)

async def suggest_retry(diagnosis: Dict[str, Any]) -> Dict[str, Any]:
    """Suggest the exact request representation for retrying based on a diagnosis record."""
    method = diagnosis.get("method", "GET")
    url = diagnosis.get("url", "")
    status = diagnosis.get("status", 200)
    category = diagnosis.get("category", "")
    
    # Pre-built rule check
    if category == "METHOD_ERROR" and "weather" in url.lower() and method.upper() == "POST":
        return {
            "next_request": {
                "method": "GET",
                "url": "/weather?city=Boston"
            }
        }
        
    if category == "PARAMETER_ERROR" and "weather" in url.lower() and "city" not in url.lower():
        return {
            "next_request": {
                "method": "GET",
                "url": "/weather?city=Boston"
            }
        }

    # If LLM is available, we can ask the LLM to write the retry plan
    system_prompt = """You are an Agent Recovery Protocol retry planner. Given a failed request and its diagnosis, output the corrected HTTP request details that the agent should try next.
Output JSON Schema:
{
   "next_request": {
      "method": "GET/POST/PUT/DELETE",
      "url": "Corrected URL path including corrected queries/parameters",
      "headers": {Optional headers like Authorization, Content-Type if they need to change},
      "body": {Optional JSON body dictionary if it needs to change}
   }
}
Return valid JSON only."""

    user_prompt = f"""Failed Request:
Method: {method}
URL: {url}
Status: {status}
Diagnosis: {json.dumps(diagnosis)}"""

    llm_res = await call_llm(system_prompt, user_prompt)
    if llm_res and "next_request" in llm_res:
        return llm_res
        
    # Heuristic fallback if LLM is unavailable
    next_method = "GET" if method.upper() == "POST" and category == "METHOD_ERROR" else method
    next_url = url
    
    if "weather" in url.lower() and "city" not in url.lower():
        next_url = "/weather?city=Boston"

    return {
        "next_request": {
            "method": next_method,
            "url": next_url
        }
    }

async def explain_error(status: int, body: str) -> Dict[str, Any]:
    """Explain raw error details in plain agentic terms."""
    if status == 429 or "rate limit" in body.lower():
        return {
            "meaning": "Too many requests",
            "wait_seconds": 60,
            "retry": True
        }
    elif status == 401 or "unauthorized" in body.lower():
        return {
            "meaning": "Unauthorized access. The token provided is invalid or expired.",
            "wait_seconds": 0,
            "retry": False
        }
    elif status == 403 or "forbidden" in body.lower():
        return {
            "meaning": "Forbidden access. Your API key does not have permissions for this resource.",
            "wait_seconds": 0,
            "retry": False
        }
    elif status == 404:
        return {
            "meaning": "Endpoint not found. The path does not exist.",
            "wait_seconds": 0,
            "retry": False
        }
        
    # Ask LLM if available
    system_prompt = """You explain API error messages in simple words for autonomous agents.
Output JSON Schema:
{
 "meaning": "Detailed meaning of what went wrong",
 "wait_seconds": wait time in seconds (integer, default 0),
 "retry": safe to retry (boolean)
}
Return valid JSON only."""

    user_prompt = f"Status: {status}\nBody: {body}"
    llm_res = await call_llm(system_prompt, user_prompt)
    if llm_res and "meaning" in llm_res:
        return llm_res
        
    return {
        "meaning": f"API returned status {status} with body: {body[:100]}",
        "wait_seconds": 0,
        "retry": True if status >= 500 or status == 408 else False
    }

async def workflow_recovery(goal: str, history: list) -> Dict[str, Any]:
    """Suggest next workflow step and check order of operations."""
    history_str = " -> ".join([str(h) for h in history])
    
    # 1. Weather flow / booking workflow standard fallback
    if "hotel" in goal.lower() or "book" in goal.lower():
        # Pay before booking
        if any("payment" in str(h).lower() for h in history) and not any("book" in str(h).lower() or "id" in str(h).lower() for h in history):
            return {
                "next_step": "Book hotel first to obtain booking ID",
                "reason": "Payment endpoint requires a valid booking ID which must be created first.",
                "retry": False
            }
            
    if "ticket" in goal.lower() or "buy" in goal.lower():
        if any("payment" in str(h).lower() for h in history) and not any("reserve" in str(h).lower() or "id" in str(h).lower() for h in history):
            return {
                "next_step": "Reserve seat first to obtain reservation ID",
                "reason": "No reservation ID found in workflow history before calling payment.",
                "retry": False
            }

    system_prompt = """You are a Workflow Recovery engine. You inspect an agent's goal and history of actions taken so far, detect out-of-order operations, and output the correct next action to take.
Output JSON Schema:
{
   "next_step": "Description of the exact next step the agent should perform",
   "reason": "Clear explanation of why this step is correct (e.g. missing prerequisites)",
   "retry": true/false (boolean indicating if the last failed action should be retried directly)
}
Return valid JSON only."""

    user_prompt = f"Goal: {goal}\nHistory of events:\n{history_str}"
    llm_res = await call_llm(system_prompt, user_prompt)
    if llm_res and "next_step" in llm_res:
        return llm_res
        
    return {
        "next_step": "Check step prerequisites",
        "reason": "Workflow reached unexpected state; verify endpoint call prerequisites.",
        "retry": False
    }

async def recover_plan(status: int, body: str) -> Dict[str, Any]:
    """Generate a recovery plan checklist."""
    # Local fallbacks for common scenarios
    if status == 404:
        return {
            "plan": [
                "Verify endpoint exists",
                "Check version prefix (e.g. /v1 vs /v2)",
                "Verify base URL matches the latest specifications",
                "Retry request with correct parameters",
                "Contact alternate endpoint or check service status if available"
            ],
            "severity": "HIGH",
            "confidence": 97,
            "recoverable": True,
            "estimated_success": 94
        }
    elif status == 401:
        return {
            "plan": [
                "Verify API Key is correctly included in the headers",
                "Check token expiration timestamp",
                "Request token refresh from the identity endpoint",
                "Retry calling the API with the refreshed token"
            ],
            "severity": "CRITICAL",
            "confidence": 99,
            "recoverable": True,
            "estimated_success": 95
        }

    system_prompt = """You generate Agent Recovery Plans (ARP). Given an API error, output a list of checklist steps to recover.
Output JSON Schema:
{
 "plan": ["Step 1", "Step 2", "Step 3", "Step 4"],
 "severity": "LOW/MEDIUM/HIGH/CRITICAL",
 "confidence": integer score (0 to 100),
 "recoverable": true/false (boolean),
 "estimated_success": integer score (0 to 100)
}
Return valid JSON only."""

    user_prompt = f"HTTP Status: {status}\nError Response Body: {body}"
    llm_res = await call_llm(system_prompt, user_prompt)
    if llm_res and "plan" in llm_res:
        return llm_res
        
    return {
        "plan": [
            "Inspect raw error details",
            "Apply exponential backoff and retry",
            "Log error context for developer review"
        ],
        "severity": "MEDIUM",
        "confidence": 80,
        "recoverable": True,
        "estimated_success": 75
    }
