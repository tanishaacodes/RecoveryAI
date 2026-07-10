---
name: Agent Recovery Protocol (ARP)
description: A specialized service that diagnoses failed API calls and tells AI agents exactly how to recover.
---

# Agent Recovery Protocol (ARP)

This skill provides a standardized protocol for autonomous AI agents to diagnose failed HTTP requests, clarify out-of-order workflow execution, and dynamically retrieve precise recovery plans and retry configurations.

**Base URL**: `https://recoveryai-production.up.railway.app`

---

## 1. Endpoints Specification

### POST /diagnose
Diagnoses a failed HTTP call, classifies it into our deterministic taxonomy, and returns a suggested fix.
* **Headers**: `Content-Type: application/json`
* **Request Body**:
  ```json
  {
    "method": "POST",
    "url": "/weather",
    "status": 405,
    "response": "Method Not Allowed"
  }
  ```
* **Response Body**:
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

---

### POST /retry-plan
Retrieves a concrete HTTP request structure for retrying based on a previous diagnosis ID.
* **Headers**: `Content-Type: application/json`
* **Request Body**:
  ```json
  {
    "diagnosis_id": "diag_abc123"
  }
  ```
* **Response Body**:
  ```json
  {
    "next_request": {
      "method": "GET",
      "url": "/weather?city=Boston"
    }
  }
  ```

---

### POST /explain
Explains HTTP error code status and body message details in plain text terms, showing retry safety.
* **Headers**: `Content-Type: application/json`
* **Request Body**:
  ```json
  {
    "status": 429,
    "body": "Rate limit exceeded"
  }
  ```
* **Response Body**:
  ```json
  {
    "meaning": "Too many requests",
    "wait_seconds": 60,
    "retry": true
  }
  ```

---

### POST /workflow-recovery
Examines the goal and history of actions taken by an agent to identify out-of-order steps and return the correct next execution step.
* **Headers**: `Content-Type: application/json`
* **Request Body**:
  ```json
  {
    "goal": "Buy ticket",
    "history": [
      "Initialized checkout",
      "Called payment endpoint"
    ]
  }
  ```
* **Response Body**:
  ```json
  {
    "next_step": "Reserve seat first to obtain reservation ID",
    "reason": "No reservation ID found in workflow history before calling payment.",
    "retry": false
  }
  ```

---

### POST /recover
Generates a complete step-by-step checklist of actions for an agent to recover from a specific error status code.
* **Headers**: `Content-Type: application/json`
* **Request Body**:
  ```json
  {
    "status": 404,
    "body": "Not Found"
  }
  ```
* **Response Body**:
  ```json
  {
    "plan": [
      "Verify endpoint exists",
      "Check version prefix (e.g. /v1 vs /v2)",
      "Verify base URL matches the latest specifications",
      "Retry request with correct parameters",
      "Contact alternate endpoint or check service status if available"
    ],
    "severity": "HIGH",
    "confidence": 97,
    "recoverable": true,
    "estimated_success": 94
  }
  ```

---

## 2. Deterministic Error Taxonomy

AI agents must choose or receive error classifications exclusively from the following taxonomy:

| Category | Description |
|---|---|
| `AUTH_ERROR` | Missing or invalid authentication credentials/headers |
| `METHOD_ERROR` | Wrong HTTP method verb (e.g. POST used instead of GET) |
| `PARAMETER_ERROR` | Missing required parameters or wrong format |
| `TIMEOUT` | Request timed out during transmission |
| `RATE_LIMIT` | API rate limit exceeded (e.g. HTTP 429) |
| `NETWORK` | DNS resolution or network connectivity issues |
| `JSON_FORMAT` | Malformed JSON in request payload |
| `SCHEMA_ERROR` | Request payload fails schema validation |
| `PERMISSION_DENIED` | Valid credentials, but forbidden from accessing the resource (e.g. HTTP 403) |
| `RESOURCE_NOT_FOUND` | Path or endpoint does not exist (e.g. HTTP 404) |
| `SERVER_ERROR` | Downstream server error (e.g. HTTP 500) |
| `SERVICE_SLEEPING` | Server in cold start or sleeping state |
| `DEPENDENCY_DOWN` | Downstream dependent microservice is unavailable |

---

## 3. Agent Execution Procedure

When an autonomous AI agent encounters an API request failure or workflow roadblock:
1. **Interrupt** the current execution loop.
2. **Submit** the failed request context (method, URL, status code, and response payload) to `POST /diagnose`.
3. **Parse** the response.
   - If `retry` is `false`, **stop** execution and seek human intervention or follow alternative paths based on the `fix` instructions.
   - If `retry` is `true`, **call** `POST /retry-plan` using the returned `id` as `diagnosis_id`.
4. **Execute** the corrected HTTP request details returned in the `next_request` field.
5. **Verify** the response. If successful, continue normal agent execution.
