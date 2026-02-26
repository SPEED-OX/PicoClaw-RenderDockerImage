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

    def _extract_model_id(self, model_entry: Any) -> str:
        if isinstance(model_entry, dict):
            return model_entry.get("id", "")
        return str(model_entry) if model_entry else ""

    def _is_model_free(self, provider_name: str, model: str) -> bool:
        provider_config = self.providers.get(provider_name, {})
        models_list = provider_config.get("models", [])
        
        for m in models_list:
            extracted_id = self._extract_model_id(m)
            if extracted_id == model:
                if isinstance(m, dict):
                    return m.get("free", ":free" in model)
                return ":free" in model
        
        return ":free" in model

    def _check_free_enforcement(self, provider_name: str, model: str):
        settings = config.BOT_CONFIG.get("settings", {})
        free_only = settings.get("free_only", False)
        
        if not free_only:
            return
        
        provider_config = self.providers.get(provider_name, {})
        models_list = provider_config.get("models", [])
        
        is_free = False
        for m in models_list:
            extracted_id = self._extract_model_id(m)
            if extracted_id == model:
                if isinstance(m, dict):
                    is_free = m.get("free", False)
                else:
                    is_free = ":free" in m
                break
        
        if not is_free and not model.endswith(":free"):
            raise ProviderError(f"Model {model} is not free")

    def _get_agent_params(self, agent_name: str) -> Dict[str, Any]:
        agent_config = config.get_agent_config(agent_name)
        if not agent_config:
            return {"temperature": 0.7, "max_tokens": 1024}
        return {
            "temperature": agent_config.get("temperature", 0.7),
            "max_tokens": agent_config.get("max_tokens", 1024)
        }

    async def _call_google_native(self, model: str, messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: int = 1024) -> str:
        provider = self.providers.get("google")
        if not provider:
            raise ProviderError("Google provider not found in config")
        
        api_key = self._get_api_key("google", provider)
        if not api_key:
            raise ProviderError("No API key for Google")
        
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        
        system_instruction = None
        contents = []
        
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                system_instruction = content
            elif role == "assistant":
                contents.append({"role": "model", "parts": [{"text": content}]})
            else:
                contents.append({"role": "user", "parts": [{"text": content}]})
        
        request_body: Dict[str, Any] = {
            "contents": contents
        }
        
        if system_instruction:
            request_body["systemInstruction"] = {
                "role": "user",
                "parts": [{"text": system_instruction}]
            }
        
        request_body["generationConfig"] = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    endpoint,
                    headers={
                        "x-goog-api-key": api_key,
                        "Content-Type": "application/json",
                    },
                    json=request_body,
                )
                response.raise_for_status()
                data = response.json()
                
                try:
                    candidates = data.get("candidates", [])
                    if not candidates:
                        return "Response blocked by safety filter"
                    
                    first_candidate = candidates[0]
                    content = first_candidate.get("content", {})
                    parts = content.get("parts", [])
                    
                    if not parts:
                        return "Response blocked by safety filter"
                    
                    return parts[0].get("text", "No response text")
                    
                except (KeyError, IndexError) as e:
                    return f"Response blocked by safety filter"
                    
        except httpx.HTTPStatusError as e:
            raise ProviderError(f"Google API error: {e.response.status_code}")
        except Exception as e:
            raise ProviderError(f"Google API call failed: {str(e)}")

    async def call_provider(self, provider_name: str, model: str, messages: List[Dict[str, str]], capability: str = "chat") -> str:
        if provider_name == "google":
            brain_config = config.BOT_CONFIG.get("brain", {})
            temperature = brain_config.get("temperature", 0.3)
            max_tokens = brain_config.get("max_tokens", 1024)
            return await self._call_google_native(model, messages, temperature, max_tokens)
        
        provider = self.providers.get(provider_name)
        if not provider:
            raise ProviderError(f"Provider '{provider_name}' not found in config")

        api_key = self._get_api_key(provider_name, provider)
        base_url = provider.get("base_url", "")
        
        if not api_key:
            raise ProviderError(f"No API key for provider '{provider_name}'")

        self._check_free_enforcement(provider_name, model)
        
        endpoint_path = self._get_endpoint(provider_name, capability)
        endpoint = f"{base_url.rstrip('/')}/{endpoint_path.lstrip('/')}"

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
