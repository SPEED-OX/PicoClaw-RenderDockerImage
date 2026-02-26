from typing import Dict, Any, Optional, List, Union
from src import brain, search, browser, db, config, providers

MAX_RESPONSE_CHARS = 4000

async def execute(chat_id: int, message: str, media: Optional[Dict[str, Any]] = None) -> Union[str, List[str]]:
    decision = await brain.decide(chat_id, message, media)
    
    action = decision.get("action", "answer_directly")
    confidence = decision.get("confidence", "high")
    search_query = decision.get("search_query")
    fetch_full_page = decision.get("fetch_full_page", False)
    specialist = decision.get("specialist")
    capability = decision.get("capability", "chat")
    reasoning = decision.get("reasoning", "")
    direct_response = decision.get("response")

    await db.log_command(chat_id, action, reasoning)

    if action == "answer_directly":
        if direct_response:
            response = direct_response
        else:
            response = await ask_brain_directly(chat_id, message)
        
        if confidence == "low":
            web_result = await quick_verify(message)
            if web_result:
                response += f"\n\n[Verified via web: {web_result[:200]}]"
        
        await db.add_message(chat_id, "user", message)
        await db.add_message(chat_id, "assistant", response)
        return truncate_response(response)

    elif action == "search_and_answer":
        if not search_query:
            search_query = message
        
        if fetch_full_page:
            search_results = await search.search_web(search_query, max_results=1)
            if search_results and "error" not in search_results.lower() and "no results" not in search_results.lower():
                top_url = await extract_top_url(search_query)
                if top_url:
                    full_content = await browser.browse_url(top_url)
                    response = await synthesize_with_context(chat_id, message, search_results, full_content)
                else:
                    response = await synthesize_with_context(chat_id, message, search_results, None)
            else:
                response = search_results
        else:
            search_results = await search.search_web(search_query)
            response = await synthesize_with_context(chat_id, message, search_results, None)
        
        return truncate_response(response)

    elif action == "search_only":
        if not search_query:
            search_query = message
        results = await search.search_web(search_query)
        return truncate_response(results)

    elif action == "specialist":
        if not specialist:
            specialist = "default"
        response = await call_specialist(chat_id, message, str(specialist))
        return truncate_response(response)

    elif action == "multi_step":
        if not search_query or not specialist:
            return truncate_response("Multi-step requires both search_query and specialist.")
        
        search_results = await search.search_web(search_query)
        if not specialist:
            specialist = "default"
        response = await call_specialist_with_context(chat_id, message, str(specialist), search_results)
        return truncate_response(response)

    elif action == "transcribe":
        if not media or media.get("type") != "voice":
            return "No voice file provided."
        file_data = media.get("file")
        if not file_data or not isinstance(file_data, bytes):
            return "No valid voice file provided."
        response = await transcribe_audio(file_data)
        return truncate_response(response)

    elif action == "vision":
        if not media or media.get("type") != "image":
            return "No image provided."
        file_data = media.get("file")
        if not file_data or not isinstance(file_data, bytes):
            return "No valid image file provided."
        response = await analyze_image(file_data, message)
        return truncate_response(response)

    elif action == "embeddings_search":
        response = await search_notes(chat_id, message)
        return truncate_response(response)

    elif action == "code_fim":
        response = await code_completion(chat_id, message)
        return truncate_response(response)

    else:
        if direct_response:
            return truncate_response(direct_response)
        return await ask_brain_directly(chat_id, message)

async def ask_brain_directly(chat_id: int, message: str) -> str:
    brain_config = config.BOT_CONFIG.get("brain", {})
    provider = brain_config.get("provider", "google")
    model = brain_config.get("model", "gemini-2.5-flash")
    fallback = brain_config.get("fallback", "groq/llama3-70b-8192")
    
    history = await db.get_conversation_history(chat_id)
    messages = [
        {"role": "system", "content": config.BOT_SETTINGS.get("personality", "You are PicoClaw.")},
    ]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": message})
    
    return await providers.call_with_fallback(f"{provider}/{model}", messages, fallback)

async def quick_verify(query: str) -> str:
    try:
        result = await search.search_web(query, max_results=1)
        return result[:300] if result else ""
    except Exception:
        return ""

async def extract_top_url(query: str) -> str:
    try:
        from duckduckgo_search import DDGS
        import asyncio
        ddgs = DDGS()
        results = await asyncio.to_thread(ddgs.text, query, max_results=1)
        if results and len(results) > 0:
            return results[0].get("href", "")
    except Exception:
        pass
    return ""

async def synthesize_with_context(chat_id: int, original_message: str, search_results: str, full_content: Optional[str]) -> str:
    session = await db.get_session(chat_id)
    
    if session.get("model_override"):
        provider_model = session.get("model_override")
    else:
        brain_config = config.BOT_CONFIG.get("brain", {})
        provider = brain_config.get("provider", "google")
        model = brain_config.get("model", "gemini-2.5-flash")
        provider_model = f"{provider}/{model}"
    
    fallback = brain_config.get("fallback", "groq/llama3-70b-8192")
    
    context_content = search_results
    if full_content:
        context_content += f"\n\nFull page content:\n{full_content[:3000]}"

    prompt = f"""Based on the user's question and web search results, provide a concise answer.

User question: {original_message}

Web search results:
{context_content}

Provide a direct, concise answer."""

    messages = [
        {"role": "system", "content": "You are PicoClaw. Answer concisely based on the provided search results."},
        {"role": "user", "content": prompt}
    ]

    try:
        response = await providers.call_with_fallback(provider_model, messages, fallback)
        await db.add_message(chat_id, "user", original_message)
        await db.add_message(chat_id, "assistant", response)
        return response
    except Exception as e:
        return f"Error synthesizing answer: {str(e)}"

async def call_specialist(chat_id: int, message: str, specialist: str) -> str:
    session = await db.get_session(chat_id)
    
    if session.get("model_override"):
        provider_model = session.get("model_override")
    else:
        agent_config = config.get_agent_config(specialist)
        if not agent_config:
            agent_config = config.get_agent_config("default")
        provider = agent_config.get("provider", config.DEFAULT_PROVIDER)
        model = agent_config.get("model", config.DEFAULT_MODEL)
        provider_model = f"{provider}/{model}"
    
    fallback = agent_config.get("fallback") if agent_config else None
    
    messages = [
        {"role": "system", "content": config.BOT_SETTINGS.get("personality", "You are PicoClaw.")},
        {"role": "user", "content": message}
    ]

    try:
        response = await providers.call_with_fallback(provider_model, messages, fallback)
        await db.add_message(chat_id, "user", message)
        await db.add_message(chat_id, "assistant", response)
        return response
    except Exception as e:
        return f"Error: {str(e)}"

async def call_specialist_with_context(chat_id: int, message: str, specialist: str, context: str) -> str:
    session = await db.get_session(chat_id)
    
    if session.get("model_override"):
        provider_model = session.get("model_override")
    else:
        agent_config = config.get_agent_config(specialist)
        if not agent_config:
            agent_config = config.get_agent_config("default")
        provider = agent_config.get("provider", config.DEFAULT_PROVIDER)
        model = agent_config.get("model", config.DEFAULT_MODEL)
        provider_model = f"{provider}/{model}"
    
    fallback = agent_config.get("fallback") if agent_config else None
    
    prompt = f"""Based on the user's request and search results, provide a response.

User request: {message}

Search results:
{context}
"""

    messages = [
        {"role": "system", "content": config.BOT_SETTINGS.get("personality", "You are PicoClaw.")},
        {"role": "user", "content": prompt}
    ]

    try:
        response = await providers.call_with_fallback(provider_model, messages, fallback)
        await db.add_message(chat_id, "user", message)
        await db.add_message(chat_id, "assistant", response)
        return response
    except Exception as e:
        return f"Error: {str(e)}"

async def transcribe_audio(audio_bytes: Optional[bytes]) -> str:
    if not audio_bytes:
        return "No audio data provided."
    try:
        messages = [
            {"role": "system", "content": "You transcribe audio to text. Return only the transcription."},
            {"role": "user", "content": "Transcribe this audio file."}
        ]
        response = await providers.call_with_fallback("groq/whisper-large-v3", messages, "groq/whisper-large-v3")
        return response
    except Exception as e:
        return f"Transcription error: {str(e)}"

async def analyze_image(image_bytes: Optional[bytes], prompt: str) -> str:
    if not image_bytes:
        return "No image data provided."
    try:
        messages = [
            {"role": "system", "content": "You analyze images and describe them. Be detailed but concise."},
            {"role": "user", "content": f"Describe this image. User context: {prompt}"}
        ]
        response = await providers.call_with_fallback("google/gemini-2.5-flash", messages, "groq/llama3-70b-8192")
        return response
    except Exception as e:
        return f"Image analysis error: {str(e)}"

async def search_notes(chat_id: int, query: str) -> str:
    try:
        notes = await db.get_notes(chat_id)
        if not notes:
            return "No notes found. Use /note to save notes."
        
        notes_text = "\n".join([f"- {n.get('content', '')}" for n in notes[:20]])
        
        messages = [
            {"role": "system", "content": "You search through user's notes to find relevant information."},
            {"role": "user", "content": f"Query: {query}\n\nUser's notes:\n{notes_text}\n\nProvide relevant notes."}
        ]
        
        response = await providers.call_with_fallback("openrouter/mistralai/mistral-7b-instruct:free", messages)
        return response
    except Exception as e:
        return f"Notes search error: {str(e)}"

async def code_completion(chat_id: int, prompt: str) -> str:
    try:
        messages = [
            {"role": "system", "content": "You are a code completion assistant. Provide code snippets."},
            {"role": "user", "content": prompt}
        ]
        response = await providers.call_with_fallback("deepseek/deepseek-chat", messages, "groq/llama3-70b-8192")
        return response
    except Exception as e:
        return f"Code completion error: {str(e)}"

def truncate_response(response: str) -> str:
    if not response:
        return "No response."
    
    settings = config.BOT_CONFIG.get("settings", {})
    max_chars = settings.get("max_response_chars", MAX_RESPONSE_CHARS)
    
    if len(response) <= max_chars:
        return response
    
    return response[:max_chars-100] + "\n\n[Truncated...]"
