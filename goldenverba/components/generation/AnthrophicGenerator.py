import os
from dotenv import load_dotenv
from goldenverba.components.interfaces import Generator
from goldenverba.components.types import InputConfig
from goldenverba.components.util import get_environment, get_token
from typing import List
from wasabi import msg
import aiohttp
import json

load_dotenv()


class AnthropicGenerator(Generator):
    """
    Anthropic Generator.
    """

    def __init__(self):
        super().__init__()
        self.name = "Anthropic"
        self.description = "Using Anthropic LLM models to generate answers to queries"
        self.context_window = 10000
        self.url = "https://api.anthropic.com/v1/messages"

        api_key = get_token("ANTHROPIC_API_KEY")
        models = self.get_models(api_key)
        default_model = os.getenv("ANTHROPIC_MODEL", models[0] if models else "claude-3-5-sonnet-20240620")

        self.config["Model"] = InputConfig(
            type="dropdown",
            value=default_model,
            description="Select an Anthropic Model",
            values=models,
        )

        if get_token("ANTHROPIC_API_KEY") is None:
            self.config["API Key"] = InputConfig(
                type="password",
                value="",
                description="You can set your Anthropic API Key here or set it as environment variable `ANTHROPIC_API_KEY`",
                values=[],
            )

    def get_models(self, api_key: str = None) -> List[str]:
        """Fetch available Anthropic models."""
        default_models = [
            "claude-3-5-sonnet-20240620",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
        ]
        
        try:
            if api_key is None:
                api_key = os.getenv("ANTHROPIC_API_KEY")
            
            if not api_key:
                msg.info("No Anthropic API key provided, using default models")
                return default_models

            # Anthropic não tem endpoint público de modelos, mas podemos tentar
            # usar a lista conhecida de modelos disponíveis
            # Ou fazer uma requisição de teste para verificar quais funcionam
            try:
                import requests
                headers = {
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                }
                # Testa modelos conhecidos para ver quais estão disponíveis
                available_models = []
                known_models = [
                    "claude-3-5-sonnet-20240620",
                    "claude-3-opus-20240229",
                    "claude-3-sonnet-20240229",
                    "claude-3-haiku-20240307",
                    "claude-3-5-haiku-20241022",
                    "claude-3-5-opus-20241022",
                ]
                
                # Por enquanto, retorna todos os modelos conhecidos
                # Anthropic não fornece endpoint de listagem como OpenAI
                msg.info(f"Using Anthropic models list (API doesn't provide model listing)")
                return known_models
                
            except Exception as e:
                msg.warn(f"Could not verify Anthropic models: {str(e)}")
                return default_models
                
        except Exception as e:
            msg.warn(f"Failed to fetch Anthropic models: {str(e)}")
            return default_models

    async def generate_stream(
        self,
        config: dict,
        query: str,
        context: str,
        conversation: list[dict] = [],
    ):
        model = config.get("Model").value
        system_message = config.get("System Message").value
        antr_key = get_environment(
            config, "API Key", "ANTHROPIC_API_KEY", "No Anthropic API Key found"
        )

        messages = self.prepare_messages(query, context, conversation)

        headers = {
            "Content-Type": "application/json",
            "x-api-key": antr_key,
            "anthropic-version": "2023-06-01",
        }

        data = {
            "messages": messages,
            "model": model,
            "stream": True,
            "system": system_message,
            "max_tokens": 4096,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.url,
                json=data,
                headers=headers,
            ) as response:
                if response.status != 200:
                    error_json = await response.json()
                    error_message = error_json.get("error", {}).get(
                        "message", "Unknown error occurred"
                    )
                    yield {
                        "message": f"Error: {error_message}",
                        "finish_reason": "stop",
                    }
                    return

                async for line in response.content:
                    line = line.decode("utf-8").strip()
                    if line.startswith("data: "):
                        if line == "data: [DONE]":
                            break
                        json_line = json.loads(line[6:])
                        if json_line["type"] == "content_block_delta":
                            delta = json_line.get("delta", {})
                            if delta.get("type") == "text_delta":
                                text = delta.get("text", "")
                                yield {
                                    "message": text,
                                    "finish_reason": None,
                                }
                        elif json_line.get("type") == "message_stop":
                            yield {
                                "message": "",
                                "finish_reason": json_line.get("stop_reason", "stop"),
                            }

    def prepare_messages(
        self, query: str, context: str, conversation: list[dict]
    ) -> list[dict]:
        messages = []

        for message in conversation:
            messages.append(
                {
                    "role": "assistant" if message.type == "system" else message.type,
                    "content": message.content,
                }
            )

        messages.append(
            {
                "role": "user",
                "content": f"Answer this query: '{query}' with this provided context: {context}",
            }
        )

        return messages
