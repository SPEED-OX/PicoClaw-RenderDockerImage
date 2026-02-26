import httpx
from typing import List, Dict, Any, Optional
from src import config

PROVIDER_ENDPOINTS = {
    "groq": {
        "chat": "/openai/v1/chat/completions",
        "transcribe": "/openai/v1/audio/transcriptions",
        "translate": "/openai/v1/audio/translations"
    },
    "google": {
        "chat": "/v1beta/openai/chat/completions",
        "embeddings": "/v1beta/openai/embeddings",
        "vision": "/v1beta/openai/chat/completions"
    },
    "openrouter": {
        "chat": "/api/v1/chat/completions",
        "embeddings": "/api/v1/embeddings"
    },
    "deepseek": {
        "chat": "/v1/chat/completions",
        "fim": "/v1/fim/completions"
    }
}

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

    def _get_endpoint(self, provider_name: str, capability: str = "chat") -> str:
        provider_endpoints = PROVIDER_ENDPOINTS.get(provider_name, {})
        endpoint = provider_endpoints.get(capability)
        if endpoint:
            return endpoint
        return "/chat/completions"

    def _is_model_free(self, provider_name: str, model: str) -> bool:
        provider_config = self.providers.get(provider_name, {})
        models_list = provider_config.get("models", [])
        
        for m in models_list:
            if isinstance(m, dict):
                if m.get("id") == model:
                    return m.get("free", False)
            elif isinstance(m, str) and m == model:
                return ":free" in m
        
        return ":free" in model

    def _check_free_enforcement(self, provider_name: str, model: str):
        settings = config.BOT_CONFIG.get("settings", {})
        free_only = settings.get("free_only", False)
        
        if not free_only:
            return
        
        provider_config = self.providers.get(provider_name, {})
        models_list = provider_config.get("models", [])
        
        for m in models_list:
            if isinstance(m, dict):
                if m.get("id") == model and not m.get("free", True):
                    raise ProviderError(f"Model {model} is not free")
            elif isinstance(m, str) and m == model:
                if not m.endswith(":free"):
                    raise ProviderError(f"Model {model} is not free")
        
        if not model.endswith(":free"):
            raise ProviderError(f"Model {model} is not free")

    async def call_provider(self, provider_name: str, model: str, messages: List[Dict[str, str]], capability: str = "chat") -> str:
        provider = self.providers.get(provider_name)
        if not provider:
            raise ProviderError(f"Provider '{provider_name}' not found in config")

        api_key = self._get_api_key(provider_name, provider)
        base_url = provider.get("base_url", "")
        
        if not api_key:
            raise ProviderError(f"No API key for provider '{provider_name}'")

        self._check_free_enforcement(provider_name, model)
        
        endpoint_path = self._get_endpoint(provider_name, capability)
        endpoint = f"{base_url}{endpoint_path}"

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
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(f"Provider call failed: {str(e)}")

    async def call_with_fallback(self, provider_model: str, messages: List[Dict[str, str]], fallback: Optional[str] = None, capability: str = "chat") -> str:
        if "/" in provider_model:
            primary_provider, primary_model = provider_model.split("/", 1)
        else:
            primary_provider = config.DEFAULT_PROVIDER
            primary_model = provider_model

        try:
            return await self.call_provider(primary_provider, primary_model, messages, capability)
        except ProviderError as e:
            if fallback:
                if "/" in fallback:
                    fallback_provider, fallback_model = fallback.split("/", 1)
                else:
                    fallback_provider = config.DEFAULT_PROVIDER
                    fallback_model = fallback
                
                try:
                    return await self.call_provider(fallback_provider, fallback_model, messages, capability)
                except ProviderError:
                    raise ProviderError(f"Primary failed: {e}, Fallback also failed")
            raise

provider_manager = ProviderManager()

async def call_provider(provider_name: str, model: str, messages: List[Dict[str, str]], capability: str = "chat") -> str:
    return await provider_manager.call_provider(provider_name, model, messages, capability)

async def call_with_fallback(provider_model: str, messages: List[Dict[str, str]], fallback: Optional[str] = None, capability: str = "chat") -> str:
    return await provider_manager.call_with_fallback(provider_model, messages, fallback, capability)
