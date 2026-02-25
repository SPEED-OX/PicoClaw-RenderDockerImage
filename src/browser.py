import asyncio
import httpx
from bs4 import BeautifulSoup
from src import agent_router

async def browse_url(url: str) -> str:
    try:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type:
                return f"URL does not return HTML content. Content-Type: {content_type}"
            
            soup = BeautifulSoup(response.text, "lxml")
            
            for script in soup(["script", "style"]):
                script.decompose()
            
            text = soup.get_text(separator="\n", strip=True)
            
            lines = [line for line in text.split("\n") if line.strip()]
            clean_text = "\n".join(lines[:200])
            
            if len(clean_text) > 3000:
                clean_text = clean_text[:3000] + "\n...(truncated)"
            
            prompt = f"Summarize this webpage content concisely:\n\n{clean_text}"
            summary = await agent_router.summarize_with_llm(prompt)
            
            return summary
            
    except asyncio.TimeoutError:
        return "Error: Request timed out (30s limit)."
    except httpx.HTTPStatusError as e:
        return f"Error: HTTP {e.response.status_code}"
    except Exception as e:
        return f"Error: {str(e)}"
