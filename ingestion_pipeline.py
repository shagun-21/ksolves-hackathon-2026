import json
import re
from typing import List, Tuple, Dict
from models import (
Ticket, Customer, Order, Product,
EnrichedTicket, DLQItem
)




# LOAD DATA

def load_json(path: str):
    with open(path, "r") as f:
        return json.load(f)

def load_all_data(data_dir: str):
    tickets = load_json(f"{data_dir}/tickets.json")
    customers = load_json(f"{data_dir}/customers.json")
    orders = load_json(f"{data_dir}/orders.json")
    products = load_json(f"{data_dir}/products.json")


    return tickets, customers, orders, products



# BUILD MAPS

def build_maps(customers, orders, products):
    customer_map = {c["email"]: Customer(**c) for c in customers}
    order_map = {o["order_id"]: Order(**o) for o in orders}
    product_map = {p["product_id"]: Product(**p) for p in products}


    return customer_map, order_map, product_map



# FEATURE EXTRACTION

def extract_order_id(text: str) -> str | None:
    match = re.search(r"ORD-\d+", text)
    return match.group(0) if match else None

def detect_defect(text: str) -> bool:
    keywords = ["not working", "defective", "broken", "stopped working"]
    text = text.lower()
    return any(k in text for k in keywords)

def detect_intent(text: str) -> str:
    text = text.lower()


    if "refund" in text:
        return "refund_request"
    if "return" in text:
        return "return_request"
    if "cancel" in text:
        return "cancellation"
    return "general_query"

# ENRICHMENT LOGIC

def enrich_ticket(
    raw_ticket: dict,
    customer_map: Dict,
    order_map: Dict,
    product_map: Dict
    ) -> Tuple[EnrichedTicket, List[str]]:


    errors = []

    try:
        ticket = Ticket(**raw_ticket)
    except Exception as e:
        return None, [f"Invalid ticket schema: {str(e)}"]

    # Extract signals
    order_id = extract_order_id(ticket.body)
    intent = detect_intent(ticket.body)
    is_defect = detect_defect(ticket.body)

    # Lookup entities
    customer = customer_map.get(ticket.customer_email)
    if not customer:
        errors.append("Customer not found")

    order = order_map.get(order_id) if order_id else None
    if not order:
        errors.append("Order not found")

    product = None
    if order:
        product = product_map.get(order.product_id)
        if not product:
            errors.append("Product not found")

    enriched = EnrichedTicket(
        ticket=ticket,
        customer=customer,
        order=order,
        product=product,
        extracted_order_id=order_id,
        intent=intent,
        is_defect=is_defect,
        ingestion_errors=errors
    )

    return enriched, errors

# INGESTION PIPELINE

def run_ingestion(data_dir: str):
        tickets_raw, customers_raw, orders_raw, products_raw = load_all_data(data_dir)


        customer_map, order_map, product_map = build_maps(
            customers_raw, orders_raw, products_raw
        )

        enriched_tickets: List[EnrichedTicket] = []
        dlq: List[DLQItem] = []

        for raw_ticket in tickets_raw:
            enriched, errors = enrich_ticket(
                raw_ticket,
                customer_map,
                order_map,
                product_map
            )

            if enriched is None:
                dlq.append(DLQItem(
                    ticket_id=raw_ticket.get("ticket_id"),
                    reason="Invalid schema",
                    raw_data=raw_ticket
                ))
                continue

            # Route to DLQ if critical errors
            if "Customer not found" in errors:
                dlq.append(DLQItem(
                    ticket_id=enriched.ticket.ticket_id,
                    reason="Customer missing",
                    raw_data=raw_ticket
                ))
                continue
            
            enriched_tickets.append(enriched)

        return enriched_tickets, dlq

tickets, dlq = run_ingestion("data/")
