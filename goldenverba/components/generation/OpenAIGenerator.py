import os
from dotenv import load_dotenv
from goldenverba.components.interfaces import Generator
from goldenverba.components.types import InputConfig
from goldenverba.components.util import get_environment, get_token
from typing import List
import httpx
import json
from wasabi import msg

load_dotenv()


class OpenAIGenerator(Generator):
    """
    OpenAI Generator.
    """

    def __init__(self):
        super().__init__()
        self.name = "OpenAI"
        self.description = "Using OpenAI LLM models to generate answers to queries"
        self.context_window = 10000
        self._last_api_key = None  # Para detectar mudanças na API key

        api_key = get_token("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        models = self.get_models(api_key, base_url)
        default_model = os.getenv("OPENAI_MODEL", models[0])

        self.config["Model"] = InputConfig(
            type="dropdown",
            value=default_model,
            description="Select an OpenAI Model",
            values=models,
        )

        if get_token("OPENAI_API_KEY") is None:
            self.config["API Key"] = InputConfig(
                type="password",
                value="",
                description="You can set your OpenAI API Key here or set it as environment variable `OPENAI_API_KEY`",
                values=[],
            )
        else:
            self._last_api_key = api_key
            
        if os.getenv("OPENAI_BASE_URL") is None:
            self.config["URL"] = InputConfig(
                type="text",
                value="https://api.openai.com/v1",
                description="You can change the Base URL here if needed",
                values=[],
            )

    def update_models_if_needed(self, config: dict):
        """
        Atualiza a lista de modelos se detectar que a API key foi configurada.
        Chamado antes de generate_stream para garantir modelos atualizados.
        """
        # Obter API key atual do config ou environment
        current_api_key = get_environment(
            config, "API Key", "OPENAI_API_KEY", None
        )
        
        # Se há uma API key agora que não havia antes, atualizar modelos
        if current_api_key and current_api_key != self._last_api_key:
            msg.info("OpenAI API key detected - updating available models...")
            base_url = get_environment(
                config, "URL", "OPENAI_BASE_URL", "https://api.openai.com/v1"
            )
            new_models = self.get_models(current_api_key, base_url)
            
            if new_models and len(new_models) > 0:
                # Atualizar lista de modelos no config
                self.config["Model"].values = new_models
                
                # Se o modelo atual não está na nova lista, usar o primeiro disponível
                current_model = self.config["Model"].value
                if current_model not in new_models:
                    self.config["Model"].value = new_models[0]
                    msg.info(f"Model updated to: {new_models[0]}")
                
                msg.good(f"Updated models list: {len(new_models)} models available")
                self._last_api_key = current_api_key
            else:
                msg.warn("Could not fetch models, keeping current list")

    async def generate_stream(
        self,
        config: dict,
        query: str,
        context: str,
        conversation: list[dict] = [],
    ):
        # Atualizar modelos se necessário (quando API key for configurada)
        self.update_models_if_needed(config)
        
        system_message = config.get("System Message").value
        model = config.get("Model", {"value": "gpt-3.5-turbo"}).value
        openai_key = get_environment(
            config, "API Key", "OPENAI_API_KEY", "No OpenAI API Key found"
        )
        openai_url = get_environment(
            config, "URL", "OPENAI_BASE_URL", "https://api.openai.com/v1"
        )

        messages = self.prepare_messages(query, context, conversation, system_message)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {openai_key}",
        }
        data = {
            "messages": messages,
            "model": model,
            "stream": True,
        }

        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{openai_url}/chat/completions",
                json=data,
                headers=headers,
                timeout=None,
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        if line.strip() == "data: [DONE]":
                            break
                        json_line = json.loads(line[6:])
                        choice = json_line["choices"][0]
                        if "delta" in choice and "content" in choice["delta"]:
                            yield {
                                "message": choice["delta"]["content"],
                                "finish_reason": choice.get("finish_reason"),
                            }
                        elif "finish_reason" in choice:
                            yield {
                                "message": "",
                                "finish_reason": choice["finish_reason"],
                            }

    def prepare_messages(
        self, query: str, context: str, conversation: list[dict], system_message: str
    ) -> list[dict]:
        messages = [
            {
                "role": "system",
                "content": system_message,
            }
        ]

        for message in conversation:
            messages.append({"role": message.type, "content": message.content})

        messages.append(
            {
                "role": "user",
                "content": f"Answer this query: '{query}' with this provided context: {context}",
            }
        )

        return messages

    def get_models(self, token: str, url: str) -> List[str]:
        """
        Fetch available chat models from OpenAI API.
        
        Tenta buscar modelos da API. Se não conseguir (sem token ou erro),
        retorna lista mínima genérica sem hardcode de modelos específicos.
        """
        # Modelos padrão atualizados (usados quando não consegue buscar da API)
        fallback_models = ["gpt-4o", "gpt-4o-mini", "gpt-5-mini", "gpt-4", "gpt-3.5-turbo"]
        # Nota: gpt-5-mini será incluído automaticamente quando disponível via API
        
        # Tentar buscar da API mesmo se token for None (pode ter sido configurado depois)
        if token is None:
            msg.warn("No OpenAI API key provided - cannot fetch latest models from API")
            msg.warn("Please configure OPENAI_API_KEY to get the latest available models")
            return fallback_models

        try:
            import requests

            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(f"{url}/models", headers=headers, timeout=10)
            response.raise_for_status()
            
            all_models = response.json()["data"]
            
            # Filtrar modelos que suportam chat completions
            # Excluir: embeddings, whisper (audio), dall-e (imagem), tts (text-to-speech)
            chat_models = []
            excluded_types = ["embedding", "whisper", "dall-e", "tts", "moderation", "text-search"]
            
            for model in all_models:
                model_id = model.get("id", "").lower()
                
                # Verificar se modelo tem permissão para chat/completions
                permissions = model.get("permission", [])
                supports_chat = any(
                    perm.get("allow_create_engine", False) or 
                    perm.get("allow_sampling", False)
                    for perm in permissions if isinstance(perm, dict)
                )
                
                # Incluir se:
                # 1. É modelo conhecido de chat (gpt-*, o1-*, o2-*, o3-*, etc) OU
                # 2. Tem permissão de chat E não é de tipo excluído
                is_known_chat = (
                    model_id.startswith("gpt-") or 
                    model_id.startswith("o1-") or
                    model_id.startswith("o2-") or
                    model_id.startswith("o3-") or
                    model_id.startswith("chatgpt-") or
                    "chat" in model_id
                )
                
                is_excluded_type = any(excluded in model_id for excluded in excluded_types)
                
                if (is_known_chat or (supports_chat and not is_excluded_type)):
                    chat_models.append(model["id"])
            
            # Ordenar: modelos mais recentes primeiro (dinâmico)
            def sort_key(model_id):
                model_lower = model_id.lower()
                # Priorizar modelos mais recentes dinamicamente
                if model_lower.startswith("gpt-5"):
                    return (0, model_id)  # GPT-5 series (mais recente)
                elif model_lower.startswith("gpt-4o") or model_lower.startswith("o3"):
                    return (1, model_id)  # GPT-4o e O3 series
                elif model_lower.startswith("o1") or model_lower.startswith("o2"):
                    return (2, model_id)  # O1/O2 series
                elif model_lower.startswith("gpt-4"):
                    return (3, model_id)  # GPT-4 series
                elif model_lower.startswith("gpt-3.5"):
                    return (4, model_id)  # GPT-3.5 series
                else:
                    return (5, model_id)  # Outros
            
            chat_models.sort(key=sort_key)
            
            if chat_models:
                msg.good(f"Fetched {len(chat_models)} OpenAI chat models from API")
                return chat_models
            else:
                msg.warn("No chat models found in API response, using fallback models")
                return fallback_models
                
        except requests.exceptions.RequestException as e:
            msg.warn(f"Failed to fetch OpenAI models from API: {str(e)}")
            msg.warn("Using fallback models. Check your API key and network connection.")
            return fallback_models
        except Exception as e:
            msg.warn(f"Unexpected error fetching OpenAI models: {str(e)}")
            return fallback_models
