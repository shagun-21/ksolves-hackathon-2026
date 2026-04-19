import asyncio
import random
from typing import Any, Callable
from models import ToolResponse

# -------------------------

# CONFIG

# -------------------------

MAX_RETRIES = 3
BASE_DELAY = 0.5

# -------------------------

# HELPER: BACKOFF

# -------------------------

async def backoff_delay(attempt: int):
    delay = BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.2)
    await asyncio.sleep(delay)

# -------------------------

# VALIDATION

# -------------------------

def is_malformed(response: Any) -> bool:
# If tool returned raw dict instead of ToolResponse
    if isinstance(response, dict) and "success" not in response:
        return True
    return False

def normalize_response(response: Any) -> ToolResponse:
    if isinstance(response, ToolResponse):
        return response


    # malformed → convert to failure
    return ToolResponse(
        success=False,
        error="Malformed tool response"
    )


# -------------------------

# EXECUTOR

# -------------------------

async def execute_tool(
tool_fn: Callable,
*args,
tool_name: str = "",
**kwargs
) -> ToolResponse:


    for attempt in range(MAX_RETRIES):
        try:
            response = tool_fn(*args, **kwargs)

            # simulate async compatibility
            if asyncio.iscoroutine(response):
                response = await response

            # detect malformed
            if is_malformed(response):
                raise ValueError("Malformed response")

            return normalize_response(response)

        except Exception as e:
            print(f"[TOOL ERROR] {tool_name} attempt={attempt} error={str(e)}")

            if attempt == MAX_RETRIES - 1:
                return ToolResponse(
                    success=False,
                    error=f"Failed after retries: {str(e)}"
                )

            await backoff_delay(attempt)


# -------------------------

# SAFE EXECUTION WRAPPERS

# -------------------------

async def safe_get_customer(tool, email, customer_map):
    return await execute_tool(tool, email, customer_map, tool_name="get_customer")

async def safe_get_order(tool, order_id, order_map):
    return await execute_tool(tool, order_id, order_map, tool_name="get_order")

async def safe_get_product(tool, product_id, product_map):
    return await execute_tool(tool, product_id, product_map, tool_name="get_product")

async def safe_check_refund(tool, order, product, is_defect):
    return await execute_tool(
tool,
order,
product,
is_defect,
tool_name="check_refund_eligibility"
)

async def safe_issue_refund(tool, order, amount, eligibility):
    return await execute_tool(
tool,
order,
amount,
eligibility,
tool_name="issue_refund"
)

async def safe_send_reply(tool, ticket_id, message):
    return await execute_tool(
tool,
ticket_id,
message,
tool_name="send_reply"
)

async def safe_escalate(tool, ticket_id, summary, priority):
    return await execute_tool(
tool,
ticket_id,
summary,
priority,
tool_name="escalate"
)
