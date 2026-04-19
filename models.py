from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


# RAW DATA MODELS

class Ticket(BaseModel):
    ticket_id: str
    customer_email: str
    subject: str
    body: str
    expected_action: Optional[str] = None  # only for evaluation

class Customer(BaseModel):
    customer_id: str
    name: str
    email: str
    tier: str  # e.g., "regular", "vip"
    total_orders: int
    notes: Optional[str] = None

class Order(BaseModel):
    order_id: str
    customer_id: str
    product_id: str
    status: str  # delivered, shipped, etc.
    order_date: str
    delivery_date: Optional[str] = None
    return_deadline: Optional[str] = None
    refund_status: Optional[str] = None

class Product(BaseModel):
    product_id: str
    name: str
    category: str
    price: float
    return_window_days: int
    warranty_months: int
    returnable: bool

# ENRICHED DOMAIN MODEL

class EnrichedTicket(BaseModel):
    ticket: Ticket
    customer: Optional[Customer]
    order: Optional[Order]
    product: Optional[Product]
    extracted_order_id: Optional[str] = None
    intent: str
    is_defect: bool


# extracted signals
extracted_order_id: Optional[str] = None
intent: Optional[str] = None
is_defect: bool = False

# ingestion metadata
ingestion_errors: List[str] = []


# AGENT MODELS

class AgentStep(BaseModel):
    thought: str
    action: str
    tool_input: Dict[str, Any]
    observation: Optional[Any] = None
    confidence: float

class AgentResult(BaseModel):
    ticket_id: str
    steps: List[AgentStep]
    final_action: str
    confidence: float
    reasoning: str


# TOOL RESPONSE MODELS

class RefundEligibility(BaseModel):
    eligible: bool
    reason: str

class ToolResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None

# AUDIT LOG MODEL

class AuditLog(BaseModel):
    ticket_id: str
    classification: Optional[str]
    steps: List[AgentStep]
    final_decision: str
    confidence: float
    metadata: Dict[str, Any] = {}

# DEAD LETTER QUEUE MODEL

class DLQItem(BaseModel):
    ticket_id: Optional[str]
    reason: str
    raw_data: Dict[str, Any]
