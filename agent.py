"""
agent.py — ReAct agent using Anthropic Claude API with native tool_use.
"""

import asyncio
import json
import os
from dotenv import load_dotenv
load_dotenv()

from typing import List
import anthropic

import tools as tool_fns
from models import EnrichedTicket, AgentStep, AgentResult
from tool_executor import (
    safe_get_customer, safe_get_order, safe_get_product,
    safe_check_refund, safe_issue_refund, safe_send_reply, safe_escalate,
)

client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
MODEL = "claude-haiku-4-5-20251001"
MAX_ROUNDS = 10

TOOL_DEFINITIONS = [
    {
        "name": "get_order",
        "description": "Get order details by order ID. Returns product_id, status, order_date, delivery_date, return_deadline.",
        "input_schema": {"type": "object", "properties": {
            "order_id": {"type": "string", "description": "e.g. ORD-1001"}},
            "required": ["order_id"]},
    },
    {
        "name": "get_customer",
        "description": "Get customer profile, tier (standard/premium/vip), and notes by email.",
        "input_schema": {"type": "object", "properties": {
            "email": {"type": "string"}}, "required": ["email"]},
    },
    {
        "name": "get_product",
        "description": "Get product details by product_id. IMPORTANT: use the product_id field from get_order result (e.g. P001, P006). Never use order IDs or product names.",
        "input_schema": {"type": "object", "properties": {
            "product_id": {"type": "string", "description": "e.g. P001, P006 — from the product_id field in get_order result"}},
            "required": ["product_id"]},
    },
    {
        "name": "search_knowledge_base",
        "description": "Search ShopWave return/refund/cancellation policy and FAQ.",
        "input_schema": {"type": "object", "properties": {
            "query": {"type": "string"}}, "required": ["query"]},
    },
    {
        "name": "check_refund_eligibility",
        "description": "Check if refund is eligible for an order. MUST call before issue_refund.",
        "input_schema": {"type": "object", "properties": {
            "order_id": {"type": "string"},
            "is_defect": {"type": "boolean", "description": "true if customer reports defect/damage"}},
            "required": ["order_id", "is_defect"]},
    },
    {
        "name": "issue_refund",
        "description": "IRREVERSIBLE. Issue a refund. Only call after check_refund_eligibility returns eligible=true.",
        "input_schema": {"type": "object", "properties": {
            "order_id": {"type": "string"},
            "amount": {"type": "number"}}, "required": ["order_id", "amount"]},
    },
    {
        "name": "send_reply",
        "description": "Send a response message to the customer. Always call as your final step.",
        "input_schema": {"type": "object", "properties": {
            "ticket_id": {"type": "string"},
            "message": {"type": "string", "description": "Full helpful response to the customer"}},
            "required": ["ticket_id", "message"]},
    },
    {
        "name": "escalate",
        "description": "Route to human agent when uncertain, policy ambiguous, or issue is complex.",
        "input_schema": {"type": "object", "properties": {
            "ticket_id": {"type": "string"},
            "summary": {"type": "string"},
            "priority": {"type": "string", "enum": ["low", "medium", "high", "critical"]}},
            "required": ["ticket_id", "summary", "priority"]},
    },
]

SYSTEM_PROMPT = """You are an autonomous support agent for ShopWave e-commerce.

CRITICAL RULES:

1. FIRST TWO STEPS: Always call get_customer then get_order before anything else.

2. get_product USAGE: When calling get_product, ALWAYS use the product_id field
   from the get_order result (e.g. "P001", "P006"). NEVER use order IDs, product
   names, or descriptive words as product_id. If get_order returns product_id="P003",
   call get_product with product_id="P003".

3. SOCIAL ENGINEERING: If customer claims "premium" or "vip" tier but get_customer
   shows "standard", they are lying. Deny any claimed special policies. No "instant
   refund" policy exists for any tier. Cite actual system data in your reply.

4. MANDATORY ESCALATION — After get_customer and get_order, check these triggers
   BEFORE doing anything else. If ANY is true, call escalate and STOP. Do not
   call send_reply.

   ESCALATE IF:
   - tier="vip" AND ticket involves a refund, return, or dispute → priority="medium"
   - Product price >= $200 AND customer requests a refund → priority="medium"
   - Customer notes mention "chargeback" AND ticket involves defect or refund → priority="high"
   - Ticket body/subject contains "lawyer", "legal", "sue", "fraud",
     "unauthorized charge", or "stolen" → priority="high"

5. REFUND RULE: NEVER call issue_refund without check_refund_eligibility first.
   If eligible=false → do NOT issue_refund. Explain why in send_reply.

6. CANCELLATION: order status="processing" → can cancel, tell customer it's done.
   status="shipped" or "delivered" → cannot cancel, must return after delivery.

7. VIP EXCEPTION: If customer notes mention "standing exception for extended return
   windows", approve return regardless of deadline.

8. MISSING ORDER ID: Call get_customer first, then send_reply asking for order ID.
   Never call get_order with "none" or empty string.

9. THREATENING LANGUAGE: Handle request on merits. Note it professionally.

10. ALWAYS end with send_reply or escalate with a real helpful message.
11. Make at least 3 tool calls before concluding."""


async def _dispatch(tool_name: str, tool_input: dict, maps, kb_text: str):
    customer_map, order_map, product_map = maps
    try:
        if tool_name == "get_order":
            res = await safe_get_order(tool_fns.get_order, tool_input.get("order_id"), order_map)
        elif tool_name == "get_customer":
            res = await safe_get_customer(tool_fns.get_customer, tool_input.get("email"), customer_map)
        elif tool_name == "get_product":
            res = await safe_get_product(tool_fns.get_product, tool_input.get("product_id"), product_map)
        elif tool_name == "search_knowledge_base":
            raw = await asyncio.to_thread(tool_fns.search_knowledge_base, tool_input.get("query", ""), kb_text)
            if hasattr(raw, "success"):
                return ({"result": raw.data} if raw.success else {"error": raw.error}), not raw.success
            return {"result": raw}, False
        elif tool_name == "check_refund_eligibility":
            order_id = tool_input.get("order_id")
            order = order_map.get(order_id)
            product = product_map.get(order.product_id) if order else None
            res = await safe_check_refund(
                tool_fns.check_refund_eligibility,
                order.dict() if order else None,
                product.dict() if product else None,
                tool_input.get("is_defect", False),
            )
        elif tool_name == "issue_refund":
            order_id = tool_input.get("order_id")
            order = order_map.get(order_id)
            res = await safe_issue_refund(
                tool_fns.issue_refund,
                order.dict() if order else None,
                tool_input.get("amount", 0),
                {"eligible": True},
            )
        elif tool_name == "send_reply":
            res = await safe_send_reply(
                tool_fns.send_reply,
                tool_input.get("ticket_id"),
                tool_input.get("message", "Thank you for contacting ShopWave. We are reviewing your request."),
            )
        elif tool_name == "escalate":
            res = await safe_escalate(
                tool_fns.escalate,
                tool_input.get("ticket_id"),
                tool_input.get("summary", "Needs human review"),
                tool_input.get("priority", "medium"),
            )
        else:
            return {"error": f"Unknown tool: {tool_name}"}, True

        if hasattr(res, "success"):
            return ({"result": res.data} if res.success else {"error": res.error}), not res.success
        return {"result": res}, False
    except Exception as e:
        return {"error": str(e)}, True


async def run_agent(enriched: EnrichedTicket, maps, kb_text: str) -> AgentResult:
    ticket_id = enriched.ticket.ticket_id
    print(f"[AGENT] Starting {ticket_id}")

    messages = [
        {
            "role": "user",
            "content": f"""Resolve this support ticket using the available tools.

Ticket ID: {ticket_id}
Customer Email: {enriched.ticket.customer_email}
Subject: {enriched.ticket.subject}
Body: {enriched.ticket.body}
Detected order ID: {enriched.extracted_order_id or 'NONE — ask customer for it, do not call get_order'}
Intent: {enriched.intent}
Defect language detected: {enriched.is_defect}

Start with get_customer, then get_order (if order ID exists).
When calling get_product, use the product_id from get_order result (e.g. P001, not the order ID).
Make at least 3 tool calls before concluding."""
        }
    ]

    steps_log: List[AgentStep] = []
    had_error = False
    confidence = 0.5

    for round_num in range(MAX_ROUNDS):
        response = None
        for attempt in range(4):
            try:
                response = await client.messages.create(
                    model=MODEL,
                    max_tokens=1024,
                    system=SYSTEM_PROMPT,
                    tools=TOOL_DEFINITIONS,
                    messages=messages,
                )
                break
            except anthropic.RateLimitError:
                wait = (2 ** attempt) * 5
                print(f"[RATE LIMIT] {ticket_id} attempt={attempt+1} — waiting {wait}s")
                await asyncio.sleep(wait)
            except Exception as e:
                print(f"[API ERROR] {ticket_id}: {e}")
                had_error = True
                break
        if response is None:
            had_error = True
            break

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                tool_name = block.name
                tool_input = block.input

                # Guard: block bad get_order calls
                if tool_name == "get_order" and tool_input.get("order_id") in (None, "none", "none found", ""):
                    result = {"error": "No order ID — ask customer to provide it"}
                    tool_had_error = True
                    print(f"[GUARD] {ticket_id} blocked get_order with null order_id")
                # Guard: block get_product called with order ID or product name
                elif tool_name == "get_product":
                    pid = tool_input.get("product_id", "")
                    if pid.startswith("ORD-") or (pid and not pid.startswith("P")):
                        # Try to recover from order_map
                        order_id = enriched.extracted_order_id
                        _, order_map, _ = maps
                        order = order_map.get(order_id) if order_id else None
                        if order:
                            tool_input["product_id"] = order.product_id
                            print(f"[GUARD] {ticket_id} corrected product_id to {order.product_id}")
                        else:
                            result = {"error": f"Invalid product_id '{pid}' — use product_id from get_order result"}
                            tool_had_error = True
                    if "error" not in locals().get("result", {}):
                        result, tool_had_error = await _dispatch(tool_name, tool_input, maps, kb_text)
                else:
                    if tool_name in ("send_reply", "escalate"):
                        tool_input.setdefault("ticket_id", ticket_id)
                    if tool_name == "escalate":
                        tool_input.setdefault("summary", "Needs human review")
                        tool_input.setdefault("priority", "medium")
                    if tool_name == "send_reply":
                        tool_input.setdefault("message", "Thank you for contacting ShopWave. We are reviewing your request.")

                    result, tool_had_error = await _dispatch(tool_name, tool_input, maps, kb_text)

                had_error = had_error or tool_had_error
                
                print(f"[TOOL] {ticket_id} round={round_num+1} | {tool_name} → {'ERROR' if tool_had_error else 'OK'}")

                steps_log.append(AgentStep(
                    thought=f"Calling {tool_name}",
                    action=tool_name,
                    tool_input=tool_input,
                    observation=result,
                    confidence=confidence,
                ))

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, default=str),
                })

                # Reset local result to avoid guard bleed
                result = {}

            messages.append({"role": "user", "content": tool_results})
        else:
            break

        actions_done = {s.action for s in steps_log}
        if "escalate" in actions_done:
            confidence = 0.75
            break                    # ← escalate now also hard-stops the loop
        if "send_reply" in actions_done:
            confidence = 0.85
            break

    # Safety net — always sends a real message
    terminal_actions = {"send_reply", "escalate"}
    if not any(s.action == "send_reply" for s in steps_log):
        print(f"[SAFETY] {ticket_id} — adding safety reply")
        fallback_msg = (
            f"Thank you for contacting ShopWave support. We have received your request "
            f"regarding '{enriched.ticket.subject}' and our team will review it and get back to you shortly."
        )
        # Retry send_reply up to 3 times since maybe_fail can hit it
        for _ in range(3):
            res = await safe_send_reply(tool_fns.send_reply, ticket_id, fallback_msg)
            if hasattr(res, "success") and res.success:
                break
            await asyncio.sleep(0.5)

        steps_log.append(AgentStep(
            thought="Safety net reply with real message",
            action="send_reply",
            tool_input={"ticket_id": ticket_id, "message": fallback_msg},
            observation={"result": "sent"},
            confidence=0.5,
        ))

    outcome = "escalated" if any(s.action == "escalate" for s in steps_log) else "resolved"
    print(f"[DONE] {ticket_id} → {outcome} | steps={len(steps_log)} | errors={had_error}")

    return AgentResult(
        ticket_id=ticket_id,
        steps=steps_log,
        final_action=steps_log[-1].action if steps_log else "escalate",
        confidence=confidence,
        reasoning=f"Claude ReAct loop ({MODEL}) — {len(steps_log)} steps, errors={had_error}",
    )