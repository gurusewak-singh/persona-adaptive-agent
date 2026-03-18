import asyncio
import json
import re
from fastapi import FastAPI
from model_client import generate_chat_response, get_customer_sentiment, generate_chat_response_stream
from prompts import sentiment_prompt, prompts_map, default_prompt
from db import get_context, get_conversation_history, save_conversation_history

app = FastAPI()


def parse_json_block(raw_text: str):
    if not raw_text:
        return None
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw_text, re.S)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


@app.get("/")
def home():
    return {"message": "Server running!"}


@app.get("/chat/{session_id}")
async def chat(session_id: int, query: str):
    customer_sentiment_prompt = sentiment_prompt.format(customer_message=query)
    
    sentiment_raw, conversation_context, conversation_history = await asyncio.gather(
        get_customer_sentiment(customer_sentiment_prompt),
        asyncio.to_thread(get_context, query),
        asyncio.to_thread(get_conversation_history, session_id),
    )
    
    sentiment = parse_json_block(sentiment_raw) or {}

    persona = sentiment.get("persona")
    score = sentiment.get("sentiment_score", 0)

    save_conversation_history(
        session_id,
        role="customer",
        message=query,
        sentiment_score=score,
        escalation=False,
    )

    prompt_template = prompts_map.get(persona, default_prompt)

    prompt = prompt_template.format(
        conversation=conversation_history,
        customer_message=query,
        context=conversation_context,
    )
    
    response_raw = await generate_chat_response(prompt)
    response_json = parse_json_block(response_raw) or {"response": response_raw}
    agent_message = response_json.get("response", response_raw)
    severity = str(response_json.get("severity_level", "")).lower()
    severity_score = {"low": 0.2, "med": 0.5, "high": 0.8}.get(severity, 0.0)
    is_escalation_agent = str(response_json.get("requires_escalation", "false")).lower() == "true"

    save_conversation_history(
        session_id,
        role="agent",
        message=agent_message,
        sentiment_score=severity_score,
        escalation=is_escalation_agent,
    )

    if is_escalation_agent:
        return {
            "response": agent_message,
            "escalated": True,
            "summary": response_json.get("summary", ""),
            "severity_level": severity,
        }

    return response_json
