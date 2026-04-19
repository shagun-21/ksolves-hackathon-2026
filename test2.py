import asyncio
import json
import os

from ingestion_pipeline import run_ingestion, load_all_data, build_maps
from processor import process_all_tickets

DATA_DIR = "data"
OUTPUT_DIR = "output"

async def main():


    print("🚀 Starting Agent System...\n")

    # -------------------------
    # INGESTION
    # -------------------------
    enriched_tickets, dlq = run_ingestion(DATA_DIR)

    print(f"[INGESTION] Valid: {len(enriched_tickets)} | DLQ: {len(dlq)}\n")

    # -------------------------
    # LOAD MAPS AGAIN (for tools)
    # -------------------------
    _, customers, orders, products = load_all_data(DATA_DIR)
    maps = build_maps(customers, orders, products)

    # -------------------------
    # LOAD KB
    # -------------------------
    with open(f"{DATA_DIR}/knowledge-base.md", "r") as f:
        kb_text = f.read()

    # -------------------------
    # PROCESS (CONCURRENT)
    # -------------------------
    results = await process_all_tickets(enriched_tickets, maps, kb_text)

    # -------------------------
    # SAVE OUTPUTS
    # -------------------------
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(f"{OUTPUT_DIR}/results.json", "w") as f:
        json.dump([r.model_dump() for r in results], f, indent=2)

    with open(f"{OUTPUT_DIR}/dlq.json", "w") as f:
        json.dump([d.model_dump() for d in dlq], f, indent=2)

    print("\n✅ Processing Complete!")
    print(f"Results saved in {OUTPUT_DIR}/")


if __name__ == "__main__":
    asyncio.run(main())
