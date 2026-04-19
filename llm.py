import requests
import json

OLLAMA_URL = "http://localhost:11434/api/generate"

def call_ollama(prompt: str) -> dict:
    response = requests.post(
    OLLAMA_URL,
    json={
    "model": "llama3",
    "prompt": prompt,
    "stream": False
    }
    )


    text = response.json()["response"]

    try:
        return json.loads(text)
    except:
        return {
            "thought": "Failed to parse LLM output",
            "action": "escalate",
            "confidence": 0.3
        }

def build_prompt(context, enriched):
    return f"""
You are an autonomous support agent.

You must decide the NEXT BEST ACTION.

Previous steps:
{context}

Ticket:
{enriched.ticket.body}

Respond ONLY in JSON:

{{
  "thought": "your reasoning",
  "action": "one action",
  "input": {{}}
}}
"""