import asyncio
from duckduckgo_search import AsyncDDGS
from src import llm

ddgs = AsyncDDGS()

async def search_web(query: str, max_results: int = 3) -> str:
    try:
        results = await ddgs.atext(query, max_results=max_results)
        
        if not results:
            return "No results found."

        formatted_results = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "No title")
            href = r.get("href", "")
            body = r.get("body", "")
            formatted_results.append(f"{i}. {title}\n{body}\n{href}")

        search_summary = "\n\n".join(formatted_results)

        summary_prompt = f"""Summarize these web search results for the user. Be concise:

{search_summary}

Provide a brief summary of the key findings."""

        summary = await llm.summarize_with_llm(summary_prompt)
        return summary

    except Exception as e:
        return f"Search error: {str(e)}"
