from src import agent_router, db

async def call_llm(chat_id: int, user_message: str) -> str:
    return await agent_router.execute(chat_id, user_message)

async def summarize_with_llm(prompt: str) -> str:
    return await agent_router.summarize_with_llm(prompt)
