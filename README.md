
# 🧠 Doki Backend Overview

## 🧩 Purpose
The **backend** powers the logic behind Doki’s intelligent sync engine. Built on **FastAPI** and deployed on **Google Cloud Run**, it integrates with the **Google Agent Development Kit (ADK)** to host AI agents capable of interpreting user goals, analyzing schemas, and orchestrating sync operations.

---

## 🏗️ Architecture Overview

### **Core Components**
| Component | Description |
|------------|-------------|
| **FastAPI Gateway** | Central API layer that serves frontend requests, handles OAuth callbacks, and routes to agents. |
| **Orchestrator Agent (ADK)** | Interprets user input, delegates schema/mapping tasks to other agents, and manages workflow logic. |
| **Mapping Agent (ADK)** | Analyzes schemas from Sheets and Supabase, suggests mappings using embedding similarity or heuristics. |
| **Sync Engine** | Executes data syncs between Sheets and Supabase, tracks logs, and resolves conflicts. |
| **Supabase Integration** | Persists configurations, mapping rules, credentials, and job logs. |
| **Google API Connector** | Interacts with Sheets and Drive APIs for schema introspection and data operations. |

---

## ⚙️ Data Flow
```
Frontend (Next.js) → FastAPI Gateway → Orchestrator Agent → Mapping Agent →
  ├── Google Sheets API
  └── Supabase REST / Realtime API
```

1. **User describes task** → Sent to Orchestrator Agent.
2. **Orchestrator Agent** calls Mapping Agent for schema mapping.
3. **Mapping Agent** uses Sheets & Supabase connectors to fetch schemas and generate a mapping plan.
4. **Sync Engine** applies mappings via Cloud Run Job.
5. **Supabase** stores results, logs, and mappings.

---

## 🧰 Technologies
| Layer | Technology |
|--------|-------------|
| Framework | FastAPI (Python) |
| AI / Agent SDK | Google Agent Development Kit (ADK) |
| Storage | Supabase (Postgres + Realtime + Auth) |
| API Connectors | Google Sheets API, Supabase API |
| Deployment | Cloud Run (Services + Jobs) |
| Monitoring | Cloud Logging / Stackdriver |
| Secrets | Cloud Secret Manager |

---

## 🧩 Cloud Run Layout
| Component | Type | Role |
|------------|------|------|
| **FastAPI Gateway** | Cloud Run Service | Handles API and auth endpoints |
| **Orchestrator Agent** | Cloud Run Service | Manages workflow logic |
| **Mapping Agent** | Cloud Run Service | Suggests and validates mappings |
| **Sync Engine** | Cloud Run Job | Executes data sync between connectors |

---

## 🔗 Interactions Between Frontend & Backend
| Flow | Description |
|------|-------------|
| **Authentication** | User logs in via Google OAuth → Backend manages tokens → Supabase Auth manages session |
| **Prompt Submission** | User describes goal → Frontend sends to `/agent/interpret` → Orchestrator processes |
| **Schema Fetch** | Backend connects to Sheets / Supabase APIs → Returns JSON schema |
| **Mapping Review** | AI suggests field matches → Frontend visualizes and allows edits |
| **Sync Execution** | Frontend calls `/start-sync-job` → Cloud Run Job executes mapping |
| **Monitoring** | Supabase and Cloud Logging push updates back to frontend dashboard |

---

These overviews describe the core architecture, flows, and integration boundaries for **Doki’s frontend and backend**, ensuring both teams can develop and deploy independently while maintaining tight synchronization through shared APIs and Supabase storage.

