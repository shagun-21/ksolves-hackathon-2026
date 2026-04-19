import random
import time
from typing import Dict, Any
from models import ToolResponse, RefundEligibility
import os
# -------------------------

# FAILURE SIMULATION

# -------------------------

def maybe_fail():
    # Failure injection disabled for demo run
    # Architecture supports: TimeoutError (7%) and malformed response (3%)
    # Enable by setting INJECT_FAILURES=true in environment
    if os.environ.get("INJECT_FAILURES") == "true":
        r = random.random()
        if r < 0.07:
            raise TimeoutError("Service timeout")
        if r < 0.10:
            return {"malformed": True}
    return None


# -------------------------

# READ TOOLS

# -------------------------

def get_customer(email: str, customer_map: Dict):
    maybe = maybe_fail()
    if maybe:
        return maybe


    customer = customer_map.get(email)
    if not customer:
        return ToolResponse(success=False, error="Customer not found")

    return ToolResponse(success=True, data=customer.dict())


def get_order(order_id: str, order_map: Dict):
    maybe = maybe_fail()
    if maybe:
        return maybe


    order = order_map.get(order_id)
    if not order:
        return ToolResponse(success=False, error="Order not found")

    return ToolResponse(success=True, data=order.dict())


def get_product(product_id: str, product_map: Dict):
    maybe = maybe_fail()
    if maybe:
        return maybe


    product = product_map.get(product_id)
    if not product:
        return ToolResponse(success=False, error="Product not found")

    return ToolResponse(success=True, data=product.dict())


def search_knowledge_base(query: str, kb_text: str):
    maybe = maybe_fail()
    if maybe:
        return maybe


# very simple search
    results = []
    for line in kb_text.split("\n"):
        if query.lower() in line.lower():
            results.append(line)

    return ToolResponse(success=True, data=results[:3])


# -------------------------

# LOGIC TOOL

# -------------------------

def check_refund_eligibility(order: Dict, product: Dict, is_defect: bool):
    maybe = maybe_fail()
    if maybe:
        return maybe


    if not order or not product:
        return ToolResponse(success=False, error="Missing data")

    if product["returnable"] and order["return_deadline"]:
        return ToolResponse(
            success=True,
            data=RefundEligibility(
                eligible=True,
                reason="Within return window"
            ).dict()
        )

    if is_defect and product["warranty_months"] > 0:
        return ToolResponse(
            success=True,
            data=RefundEligibility(
                eligible=True,
                reason="Defective under warranty"
            ).dict()
        )

    return ToolResponse(
        success=True,
        data=RefundEligibility(
            eligible=False,
            reason="Not eligible"
        ).dict()
    )


# -------------------------

# ACTION TOOLS

# -------------------------

def issue_refund(order: Dict, amount: float, eligibility: Dict):
    # maybe = maybe_fail()
    # if maybe:
    #     return maybe


    if not eligibility.get("eligible"):
        return ToolResponse(success=False, error="Refund not allowed")

    # simulate irreversible action
    order["refund_status"] = "processed"

    return ToolResponse(
        success=True,
        data={"message": "Refund issued", "amount": amount}
    )


def send_reply(ticket_id: str, message: str):
    # maybe = maybe_fail()
    # if maybe:
    #     return maybe


    return ToolResponse(
        success=True,
        data={"ticket_id": ticket_id, "message": message}
    )


def escalate(ticket_id: str, summary: str, priority: str):
    # No maybe_fail() — terminal actions must always succeed
    return ToolResponse(
        success=True,
        data={
            "ticket_id": ticket_id,
            "summary": summary,
            "priority": priority,
            "status": "escalated"
        }
    )

