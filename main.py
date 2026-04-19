import asyncio
import json
import os
import time
from dotenv import load_dotenv
load_dotenv()

from ingestion_pipeline import run_ingestion, load_all_data, build_maps
from processor import process_all_tickets
from summary import generate_summary

DATA_DIR = "data"
OUTPUT_DIR = "output"

async def main():
    print("\n🚀 ShopWave Autonomous Support Agent starting...\n")

    # Ingestion
    enriched_tickets, dlq = run_ingestion(DATA_DIR)
    print(f"[INGESTION] Valid: {len(enriched_tickets)} | DLQ: {len(dlq)}\n")

    # Load maps for tools
    _, customers, orders, products = load_all_data(DATA_DIR)
    maps = build_maps(customers, orders, products)

    # Load KB
    with open(f"{DATA_DIR}/knowledge-base.md", "r") as f:
        kb_text = f.read()

    # Process concurrently
    start = time.monotonic()
    results = await process_all_tickets(enriched_tickets, maps, kb_text)
    elapsed = time.monotonic() - start

    # Summary dashboard + save audit_log.json
    generate_summary(results, dlq, elapsed)

    # SAVE OUTPUT
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(f"{OUTPUT_DIR}/results.json", "w") as f:
        json.dump([r.model_dump() for r in results], f, indent=2)

    with open(f"{OUTPUT_DIR}/dlq.json", "w") as f:
        json.dump([d.model_dump() for d in dlq], f, indent=2)

    print("\n✅ Processing Complete!")
    print(f"Results saved in {OUTPUT_DIR}/")


if __name__ == "__main__":
    asyncio.run(main())
