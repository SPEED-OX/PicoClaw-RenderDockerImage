from src import orchestrator, db

async def call_llm(chat_id: int, user_message: str) -> str:
    result = await orchestrator.execute(chat_id, user_message)
    if isinstance(result, list):
        return "\n\n".join(result)
    return result

async def summarize_with_llm(prompt: str) -> str:
    from src import config, providers
    
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
        return await providers.call_with_fallback(f"{provider}/{model}", messages)
    except Exception as e:
        return f"Summary error: {str(e)}"
