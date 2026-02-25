import httpx
from typing import List, Optional
from src import config

async def list_repos() -> str:
    if not config.GITHUB_TOKEN or not config.GITHUB_USERNAME:
        return "Error: GitHub credentials not configured."
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"https://api.github.com/users/{config.GITHUB_USERNAME}/repos",
                headers={"Authorization": f"token {config.GITHUB_TOKEN}"}
            )
            response.raise_for_status()
            repos = response.json()
            
            if not repos:
                return "No repositories found."
            
            lines = ["Your repositories:"]
            for repo in repos[:10]:
                lines.append(f"- {repo['name']} ({repo['language'] or 'N/A'}) - ⭐ {repo['stargazers_count']}")
            
            return "\n".join(lines)
    except Exception as e:
        return f"Error: {str(e)}"

async def list_issues(repo: str) -> str:
    if not config.GITHUB_TOKEN:
        return "Error: GitHub token not configured."
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"https://api.github.com/repos/{config.GITHUB_USERNAME}/{repo}/issues",
                headers={"Authorization": f"token {config.GITHUB_TOKEN}"}
            )
            response.raise_for_status()
            issues = response.json()
            
            if not issues:
                return f"No open issues in {repo}."
            
            lines = [f"Open issues in {repo}:"]
            for issue in issues[:10]:
                lines.append(f"- #{issue['number']}: {issue['title']}")
            
            return "\n".join(lines)
    except Exception as e:
        return f"Error: {str(e)}"

async def create_issue(repo: str, title: str, body: str = "") -> str:
    if not config.GITHUB_TOKEN:
        return "Error: GitHub token not configured."
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"https://api.github.com/repos/{config.GITHUB_USERNAME}/{repo}/issues",
                headers={"Authorization": f"token {config.GITHUB_TOKEN}"},
                json={"title": title, "body": body}
            )
            response.raise_for_status()
            issue = response.json()
            return f"Issue created: {issue['html_url']}"
    except Exception as e:
        return f"Error: {str(e)}"

async def recent_commits(repo: str) -> str:
    if not config.GITHUB_TOKEN:
        return "Error: GitHub token not configured."
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"https://api.github.com/repos/{config.GITHUB_USERNAME}/{repo}/commits",
                headers={"Authorization": f"token {config.GITHUB_TOKEN}"}
            )
            response.raise_for_status()
            commits = response.json()
            
            if not commits:
                return f"No commits found in {repo}."
            
            lines = [f"Recent commits in {repo}:"]
            for commit in commits[:10]:
                msg = commit['commit']['message'].split('\n')[0]
                author = commit['commit']['author']['name']
                lines.append(f"- {msg[:50]}... by {author}")
            
            return "\n".join(lines)
    except Exception as e:
        return f"Error: {str(e)}"
