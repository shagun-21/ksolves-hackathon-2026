import asyncio
from typing import List

from agent import run_agent
from models import EnrichedTicket, AgentResult

# limit concurrency (important for scoring)

SEM = asyncio.Semaphore(2)

async def process_single_ticket(enriched: EnrichedTicket, maps, kb_text: str):
    async with SEM:
        print(f"[PROCESSING] {enriched.ticket.ticket_id}")
    result = await run_agent(enriched, maps, kb_text)
    print(f"[DONE] {enriched.ticket.ticket_id} → {result.final_action}")
    return result

async def process_all_tickets(
    enriched_tickets: List[EnrichedTicket],
    maps,
    kb_text: str
    ):
    tasks = [
    process_single_ticket(ticket, maps, kb_text)
    for ticket in enriched_tickets
    ]


    results: List[AgentResult] = await asyncio.gather(*tasks)

    return results

