import httpx
from typing import List, Dict, Any, Optional
from src import config

class ProviderError(Exception):
    pass

class ProviderManager:
    def __init__(self):
        self.providers = config.PROVIDERS
        self.key_indices: Dict[str, int] = {}

    def _get_provider_key_index(self, provider_name: str) -> int:
        if provider_name not in self.key_indices:
            self.key_indices[provider_name] = 0
        return self.key_indices[provider_name]

    def _rotate_key_index(self, provider_name: str, key_count: int):
        if key_count > 1:
            self.key_indices[provider_name] = (self._get_provider_key_index(provider_name) + 1) % key_count

    def _get_api_key(self, provider_name: str, provider_config: Dict[str, Any]) -> str:
        api_key = provider_config.get("api_key", "")
        if isinstance(api_key, list) and len(api_key) > 1:
            idx = self._get_provider_key_index(provider_name)
            if idx < len(api_key):
                key = api_key[idx]
                self._rotate_key_index(provider_name, len(api_key))
                return key
            return api_key[0] if api_key else ""
        return api_key if isinstance(api_key, str) else ""

    async def call_provider(self, provider_name: str, model: str, messages: List[Dict[str, str]]) -> str:
        provider = self.providers.get(provider_name)
        if not provider:
            raise ProviderError(f"Provider '{provider_name}' not found in config")

        api_key = self._get_api_key(provider_name, provider)
        base_url = provider.get("base_url", "")
        
        if not api_key:
            raise ProviderError(f"No API key for provider '{provider_name}'")

        endpoint = f"{base_url}/chat/completions"

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    endpoint,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": messages,
                    },
                )
                response.raise_for_status()
                data = response.json()
                
                try:
                    return data["choices"][0]["message"]["content"]
                except (KeyError, IndexError):
                    raise ProviderError("No response content from provider")
        except httpx.HTTPStatusError as e:
            raise ProviderError(f"Provider API error: {e.response.status_code}")
        except Exception as e:
            raise ProviderError(f"Provider call failed: {str(e)}")

    async def call_with_fallback(self, provider_model: str, messages: List[Dict[str, str]], fallback: Optional[str] = None) -> str:
        if "/" in provider_model:
            primary_provider, primary_model = provider_model.split("/", 1)
        else:
            primary_provider = config.DEFAULT_PROVIDER
            primary_model = provider_model

        try:
            return await self.call_provider(primary_provider, primary_model, messages)
        except ProviderError as e:
            if fallback:
                if "/" in fallback:
                    fallback_provider, fallback_model = fallback.split("/", 1)
                else:
                    fallback_provider = config.DEFAULT_PROVIDER
                    fallback_model = fallback
                
                try:
                    return await self.call_provider(fallback_provider, fallback_model, messages)
                except ProviderError:
                    raise ProviderError(f"Primary failed: {e}, Fallback also failed")
            raise

provider_manager = ProviderManager()

async def call_provider(provider_name: str, model: str, messages: List[Dict[str, str]]) -> str:
    return await provider_manager.call_provider(provider_name, model, messages)

async def call_with_fallback(provider_model: str, messages: List[Dict[str, str]], fallback: Optional[str] = None) -> str:
    return await provider_manager.call_with_fallback(provider_model, messages, fallback)
