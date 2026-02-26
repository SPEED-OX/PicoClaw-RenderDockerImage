import json
import logging
from typing import Dict, Any, Optional, List
from src import config, providers, db

logger = logging.getLogger(__name__)

BRAIN_SYSTEM_PROMPT = """You are PicoClaw's brain — the central intelligence that decides how to handle every user message.

## Your Identity
You are a personal assistant named PicoClaw. Be sharp, concise, no fluff. You're capable, not chatty.

## Available Tools
- answer_directly: You know the answer confidently. Use this for facts, opinions, explanations you trust.
- search_and_answer: Fetch web results, then synthesize a final answer. Use for current events, unfamiliar topics, or when you need verification.
- search_only: Return raw summarized search results without synthesis. Use when user explicitly wants search results.
- specialist: Hand off to a specialist agent:
  - reason: For analytical, logical, comparative questions
  - creative: For writing, brainstorming, creative tasks
  - code: For code writing, debugging, refactoring
- multi_step: First search, then pass results to a specialist. Both search_query and specialist must be set.
- transcribe: Audio file needs transcription via Groq Whisper.
- vision: Image needs analysis via Google Vision.
- embeddings_search: Semantic search through user's notes.
- code_fim: Code completion using DeepSeek FIM endpoint.

## Decision Format
You MUST respond with ONLY valid JSON, no other text:

{
  "action": "answer_directly | search_and_answer | search_only | specialist | multi_step | transcribe | vision | embeddings_search | code_fim",
  "confidence": "high | medium | low",
  "search_query": "string or null",
  "fetch_full_page": false,
  "specialist": "reason | creative | code | null",
  "capability": "chat | transcribe | vision | embeddings | fim",
  "reasoning": "one line explaining this decision",
  "response": "direct answer string or null if tools needed"
}

## Telegram Formatting Rules
- Plain text only
- No markdown tables
- No HTML
- Maximum 4096 characters per message
- Use line breaks for readability

## Confidence Guidance
- If unsure about a fact, set confidence to "low" — the orchestrator will verify with a quick web search
- For current events, always use search regardless of confidence
- If the user explicitly asks to search, use search_only

## Examples
- "What's the weather?" -> search_and_answer, confidence: medium
- "Explain quantum physics" -> answer_directly (if you know), or specialist: reason
- "Write me a poem" -> specialist: creative
- "Fix this bug: [code]" -> specialist: code
- "What's latest news?" -> search_and_answer, confidence: high

Now analyze this message and respond with ONLY JSON."""

async def get_conversation_context(chat_id: int) -> str:
    history = await db.get_conversation_history(chat_id)
    context_lines = []
    for msg in history[-10:]:
        role = msg.get("role", "user")
        content = msg.get("content", "")[:200]
        context_lines.append(f"{role}: {content}")
    return "\n".join(context_lines)

def _is_simple_message(message: str) -> bool:
    if len(message) > 60:
        return False
    complex_indicators = [
        "?", "search", "find", "latest", "news", "write", "code",
        "debug", "fix", "explain", "why", "how", "what", "compare",
        "analyze", "calculate", "translate", "summarize", "generate"
    ]
    message_lower = message.lower()
    return not any(indicator in message_lower for indicator in complex_indicators)

async def decide(chat_id: int, message: str, media: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    brain_config = config.BOT_CONFIG.get("brain", {})

    if _is_simple_message(message) and not media:
        provider_name = "groq"
        model_name = "llama-3.3-70b-versatile"
        fallback = [
            "openrouter/mistralai/mistral-7b-instruct:free"
        ]
        logger.info(f"Brain (fast tier): provider={provider_name}, model={model_name}")
    else:
        provider_name = brain_config.get("provider", "google")
        model_name = brain_config.get("model", "gemini-2.5-flash")
        fallback = [
            "groq/llama-3.3-70b-versatile",
            "openrouter/mistralai/mistral-7b-instruct:free"
        ]
        logger.info(f"Brain (full tier): provider={provider_name}, model={model_name}")

    context = await get_conversation_context(chat_id)
    
    if media:
        media_desc = f"\n\nMedia attached: {media.get('type', 'unknown')}"
        if media.get("type") == "voice":
            message = f"[Voice message]{media_desc}\n\nUser message: {message}"
        elif media.get("type") == "image":
            message = f"[Image]{media_desc}\n\nUser caption: {message}"
    else:
        media_desc = ""

    prompt = f"""{BRAIN_SYSTEM_PROMPT}

Recent conversation context:
{context}

User message: {message}
"""

    messages = [
        {"role": "system", "content": "You are PicoClaw's brain. Always respond with valid JSON only."},
        {"role": "user", "content": prompt}
    ]

    try:
        if provider_name == "google":
            system_content = "You are PicoClaw's brain. Always respond with valid JSON only."
        else:
            system_content = (
                "You are PicoClaw's brain. Analyze the user message and respond with a JSON object only. "
                "No explanations, no markdown, just raw JSON matching this schema: "
                "{action, confidence, search_query, fetch_full_page, specialist, capability, reasoning, response}"
            )

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": prompt}
        ]

        response = await providers.call_with_fallback(
            f"{provider_name}/{model_name}",
            messages,
            fallback
        )

        decision = parse_brain_response(response)
        logger.info(f"Brain decision: action={decision.get('action')}, confidence={decision.get('confidence')}, reasoning={decision.get('reasoning')}")
        return decision

    except Exception as e:
        return {
            "action": "answer_directly",
            "confidence": "high",
            "search_query": None,
            "fetch_full_page": False,
            "specialist": None,
            "capability": "chat",
            "reasoning": f"Brain error: {str(e)[:50]}, defaulting to direct answer",
            "response": f"I encountered an issue processing your request. Please try again. Error: {str(e)[:100]}"
        }

def parse_brain_response(response: str) -> Dict[str, Any]:
    default_decision = {
        "action": "answer_directly",
        "confidence": "high",
        "search_query": None,
        "fetch_full_page": False,
        "specialist": None,
        "capability": "chat",
        "reasoning": "Failed to parse brain response, defaulting to direct answer",
        "response": None
    }

    try:
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        response = response.strip()

        parsed = json.loads(response)
        
        required_fields = ["action", "confidence", "reasoning"]
        for field in required_fields:
            if field not in parsed:
                parsed[field] = default_decision[field]

        if "search_query" not in parsed:
            parsed["search_query"] = None
        if "fetch_full_page" not in parsed:
            parsed["fetch_full_page"] = False
        if "specialist" not in parsed:
            parsed["specialist"] = None
        if "capability" not in parsed:
            parsed["capability"] = "chat"
        if "response" not in parsed:
            parsed["response"] = None

        return parsed

    except (json.JSONDecodeError, Exception) as e:
        return {
            **default_decision,
            "reasoning": f"Parse error: {str(e)[:40]}, defaulting to direct answer"
        }
