# 🤖 Autonomous Support Resolution Agent

An AI-powered customer support agent that autonomously resolves tickets using a ReAct-style reasoning loop with full tool integration, audit logging, and intelligent escalation.

---

## 🚀 Overview

This agent simulates a production-grade support system where Claude handles customer tickets end-to-end — from ingestion to resolution — without human intervention. It reasons through each ticket, chains tools together, and decides whether to resolve or escalate based on policy rules.

---

## 🧠 Key Features

- **ReAct Loop** — Think → Act → Observe reasoning cycle per ticket
- **Multi-step tool chaining** — chains up to 10 tool calls per ticket
- **Async concurrent processing** — handles multiple tickets in parallel via `asyncio`
- **Intelligent escalation** — routes to human agents based on tier, refund size, legal threats, and fraud signals
- **Failure handling** — guards against malformed inputs, missing order IDs, rate limits, and tool errors
- **Audit logs** — full step-by-step reasoning and action trace per ticket

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+ |
| LLM | Anthropic Claude (Haiku) |
| Async runtime | `asyncio` |
| API client | `anthropic` Python SDK |
| Config | `python-dotenv` |

---

## 📁 Project Structure

```
.
├── agent.py            # Core ReAct agent loop
├── tool_executor.py    # Safe tool wrappers with error handling
├── tools.py            # Tool implementations (refund, lookup, reply, etc.)
├── models.py           # Pydantic models (EnrichedTicket, AgentStep, AgentResult)
├── .env                # API key (not committed)
└── README.md
```

---

## ⚙️ Setup

1. **Clone the repo**
   ```bash
   git clone <repo-url>
   cd <repo-folder>
   ```

2. **Install dependencies**
   ```bash
   pip install anthropic python-dotenv
   ```

3. **Add your API key**
   ```bash
   echo "ANTHROPIC_API_KEY=sk-..." > .env
   ```

4. **Run the agent**
   ```bash
   python agent.py
   ```

---

## 🔄 Workflow

```
Ticket Input
     │
     ▼
get_customer → get_order
     │
     ▼
Escalation Check
  ├─ VIP + refund?       → escalate (medium)
  ├─ Price ≥ $200?       → escalate (medium)
  ├─ Chargeback history? → escalate (high)
  └─ Legal / fraud?      → escalate (high)
     │
     ▼ (no triggers)
get_product → check_refund_eligibility
     │
     ├─ eligible=true  → issue_refund → send_reply
     └─ eligible=false → send_reply (explain denial)
```

---

## 🎯 Capabilities

| Capability | Description |
|---|---|
| Refund processing | Checks eligibility, issues refunds, handles defects |
| Order tracking | Looks up status, delivery dates, return windows |
| Policy reasoning | Applies return windows, VIP exceptions, cancellation rules |
| Social engineering detection | Catches false tier claims, non-existent policies |
| Customer communication | Sends personalised, context-aware replies |
| Edge case handling | Missing order IDs, expired windows, duplicate refunds |
| Escalation | Routes complex/risky tickets to human agents with full summary |

---

## 🛡️ Escalation Triggers

The agent automatically escalates (and stops processing) when:

- Customer tier is `vip` and the request involves a refund or dispute
- Refund amount is **$200 or more**
- Customer notes mention a prior **chargeback**
- Ticket contains **legal threats** (`lawyer`, `sue`, `legal action`)
- Ticket mentions **fraud** or **unauthorized charges**

---

## 📋 Example Output

```json
{
  "ticket_id": "TKT-002",
  "outcome": "escalated",
  "final_action": "escalate",
  "confidence": 0.75,
  "tool_calls": 5,
  "escalated": true,
  "steps": [
    { "action": "get_customer", ... },
    { "action": "get_order", ... },
    { "action": "get_product", ... },
    { "action": "escalate", "priority": "medium", ... }
  ]
}
```

---

## ⚠️ Notes

- Requires a valid `ANTHROPIC_API_KEY` in `.env`
- Designed for **hackathon demonstration** — not production-hardened
- The `maybe_fail` wrapper in `tool_executor.py` simulates real-world tool flakiness
- Max 10 reasoning rounds per ticket to prevent runaway loops

---

## 🏆 Highlights

- Production-style agent architecture with clean separation of concerns
- Robust failure handling at every layer (API, tool, logic)
- Deterministic escalation policy enforced at the prompt level
- Full audit trail for every ticket decision
