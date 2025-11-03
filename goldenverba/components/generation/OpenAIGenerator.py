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
        if os.getenv("OPENAI_BASE_URL") is None:
            self.config["URL"] = InputConfig(
                type="text",
                value="https://api.openai.com/v1",
                description="You can change the Base URL here if needed",
                values=[],
            )

    async def generate_stream(
        self,
        config: dict,
        query: str,
        context: str,
        conversation: list[dict] = [],
    ):
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
        """Fetch available chat models from OpenAI API."""
        default_models = ["gpt-4o", "gpt-3.5-turbo"]
        try:
            if token is None:
                msg.info("No OpenAI API key provided, using default models")
                return default_models

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
                # 1. É modelo conhecido de chat (gpt-*, o1-*, etc) OU
                # 2. Tem permissão de chat E não é de tipo excluído
                is_known_chat = (
                    model_id.startswith("gpt-") or 
                    model_id.startswith("o1-") or
                    model_id.startswith("chatgpt-") or
                    "chat" in model_id
                )
                
                is_excluded_type = any(excluded in model_id for excluded in excluded_types)
                
                if (is_known_chat or (supports_chat and not is_excluded_type)):
                    chat_models.append(model["id"])
            
            # Ordenar: modelos mais recentes primeiro
            def sort_key(model_id):
                if model_id.startswith("gpt-4o"):
                    return (0, model_id)
                elif model_id.startswith("o1"):
                    return (1, model_id)
                elif model_id.startswith("gpt-4"):
                    return (2, model_id)
                elif model_id.startswith("gpt-3.5"):
                    return (3, model_id)
                else:
                    return (4, model_id)
            
            chat_models.sort(key=sort_key)
            
            if chat_models:
                msg.good(f"Fetched {len(chat_models)} OpenAI chat models from API")
                return chat_models
            else:
                msg.warn("No chat models found, using default models")
                return default_models
                
        except Exception as e:
            msg.warn(f"Failed to fetch OpenAI models: {str(e)}")
            return default_models
