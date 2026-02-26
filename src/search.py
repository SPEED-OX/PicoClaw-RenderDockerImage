import asyncio
from duckduckgo_search import DDGS
from src import llm, browser

async def search_web(query: str, max_results: int = 3, fetch_full: bool = False) -> str:
    try:
        ddgs = DDGS()
        results = await asyncio.to_thread(ddgs.text, query, max_results=max_results)
        
        if not results:
            return "No results found."

        if fetch_full and results:
            top_url = results[0].get("href", "")
            if top_url:
                full_content = await browser.browse_url(top_url)
                
                formatted_results = []
                for i, r in enumerate(results, 1):
                    title = r.get("title", "No title")
                    href = r.get("href", "")
                    body = r.get("body", "")
                    formatted_results.append(f"{i}. {title}\n{body}\n{href}")

                search_summary = "\n\n".join(formatted_results)
                
                summary_prompt = f"""Summarize these web search results with full page content for the user:

Search Results:
{search_summary}

Full Page Content:
{full_content[:3000]}

Provide a comprehensive summary of the key findings."""

                summary = await llm.summarize_with_llm(summary_prompt)
                return summary

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
