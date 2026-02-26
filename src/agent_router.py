# DEPRECATED: Use orchestrator.py for new code. Kept for backward compatibility.

import re
from typing import List, Dict, Any, Optional
from src import config, db, providers

async def route_task(message: str) -> str:
    message_lower = message.lower()
    routing_config = config.ROUTING
    keywords = routing_config.get("keywords", {})
    
    for agent_name, agent_keywords in keywords.items():
        for keyword in agent_keywords:
            if keyword in message_lower:
                return agent_name
    
    if routing_config.get("llm_classifier", False):
        return await classify_with_llm(message)
    
    return "default"

async def classify_with_llm(message: str) -> str:
    agent_names = list(config.AGENTS.keys())
    classifier_model = config.CLASSIFIER_MODEL
    
    if "/" in classifier_model:
        classifier_provider, classifier_model = classifier_model.split("/", 1)
    else:
        classifier_provider = config.DEFAULT_PROVIDER
    
    prompt = f"""Classify this message into one of these agents: {', '.join(agent_names)}. 
Reply with just the agent name. Message: {message}"""
    
    messages = [
        {"role": "system", "content": "You are a message classifier. Reply with only the agent name."},
        {"role": "user", "content": prompt}
    ]
    
    try:
        result = await providers.call_provider(classifier_provider, classifier_model, messages)
        result = result.strip().lower()
        
        for agent_name in agent_names:
            if agent_name in result:
                return agent_name
    except Exception as e:
        print(f"Classifier error: {e}")
    
    return "default"

async def execute(chat_id: int, message: str, force_agent: Optional[str] = None, force_model: Optional[str] = None) -> str:
    session = await db.get_session(chat_id)
    
    if force_agent:
        agent_name = force_agent
    elif session.get("agent_override"):
        agent_name = session.get("agent_override")
    else:
        agent_name = await route_task(message)
    
    agent_config = config.get_agent_config(agent_name)
    if not agent_config:
        agent_config = config.get_agent_config("default")
        agent_name = "default"
    
    if force_model:
        provider_model = force_model
    elif session.get("model_override"):
        provider_model = session.get("model_override")
    else:
        provider = agent_config.get("provider", config.DEFAULT_PROVIDER)
        model = agent_config.get("model", config.DEFAULT_MODEL)
        provider_model = f"{provider}/{model}"
    
    if "/" in provider_model:
        primary_provider, primary_model = provider_model.split("/", 1)
    else:
        primary_provider = config.DEFAULT_PROVIDER
        primary_model = provider_model
    
    fallback = agent_config.get("fallback")
    
    history = await db.get_conversation_history(chat_id)
    messages = [{"role": "system", "content": config.BOT_SETTINGS.get("personality", "You are a helpful assistant.")}]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": message})
    
    try:
        response = await providers.call_with_fallback(f"{primary_provider}/{primary_model}", messages, fallback)
        
        await db.add_message(chat_id, "user", message)
        await db.add_message(chat_id, "assistant", response)
        
        return response
    except Exception as e:
        return f"Error: {str(e)}"

async def summarize_with_llm(prompt: str) -> str:
    messages = [
        {"role": "system", "content": "You summarize content concisely. Be brief."},
        {"role": "user", "content": prompt}
    ]
    
    classifier_model = config.CLASSIFIER_MODEL
    if "/" in classifier_model:
        provider, model = classifier_model.split("/", 1)
    else:
        provider = config.DEFAULT_PROVIDER
        model = classifier_model
    
    try:
        return await providers.call_provider(provider, model, messages)
    except Exception as e:
        return f"Summary error: {str(e)}"
