import os
import json
from typing import List
import io

import aiohttp
from wasabi import msg

from goldenverba.components.interfaces import Embedding
from goldenverba.components.types import InputConfig
from goldenverba.components.util import get_environment


class VoyageAIEmbedder(Embedding):
    """VoyageAIEmbedder for Verba."""

    def __init__(self):
        super().__init__()
        self.name = "VoyageAI"
        self.description = "Vectorizes documents and queries using VoyageAI"

        # Fetch available models
        api_key = os.getenv("VOYAGE_API_KEY")
        base_url = os.getenv("VOYAGE_BASE_URL", "https://api.voyageai.com/v1")
        models = self.get_models(api_key, base_url)

        # Set up configuration
        self.config = {
            "Model": InputConfig(
                type="dropdown",
                value=models[0],
                description="Select a VoyageAI Embedding Model",
                values=models,
            )
        }

        # Add API Key and URL configs if not set in environment
        if api_key is None:
            self.config["API Key"] = InputConfig(
                type="password",
                value="",
                description="OpenAI API Key (or set OPENAI_API_KEY env var)",
                values=[],
            )
        if os.getenv("VOYAGE_BASE_URL") is None:
            self.config["URL"] = InputConfig(
                type="text",
                value=base_url,
                description="OpenAI API Base URL (if different from default)",
                values=[],
            )

    async def vectorize(self, config: dict, content: List[str]) -> List[List[float]]:
        """Vectorize the input content using VoyageAI's API."""
        model_config = config.get("Model")
        model = model_config.value if hasattr(model_config, 'value') else (model_config.get('value', 'voyage-2') if isinstance(model_config, dict) else model_config)
        api_key = get_environment(
            config, "API Key", "VOYAGE_API_KEY", "No VoyageAI API Key found"
        )
        base_url = get_environment(
            config, "URL", "VOYAGE_BASE_URL", "No VoyageAI URL found"
        )

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        payload = {"input": content, "model": model}

        async with aiohttp.ClientSession() as session:
            from verba_extensions.utils.retry import retry_with_backoff
            
            # Função interna para fazer requisição com retry
            async def make_request():
                async with session.post(
                    f"{base_url}/embeddings",
                    headers=headers,
                    json=payload,  # Use json parameter instead of data
                    timeout=30,
                ) as response:
                    if response.status == 400:
                        error_body = await response.text()
                        raise ValueError(f"Bad Request: {error_body}")
                    response.raise_for_status()
                    data = await response.json()

                    if "data" not in data:
                        raise ValueError(f"Unexpected API response: {data}")

                    embeddings = [item["embedding"] for item in data["data"]]
                    if len(embeddings) != len(content):
                        raise ValueError(
                            f"Mismatch in embedding count: got {len(embeddings)}, expected {len(content)}"
                        )

                    return embeddings
            
            # Executa com retry (base_delay maior para rate limits mais restritivos)
            try:
                return await retry_with_backoff(
                    make_request,
                    max_retries=3,
                    base_delay=2.0,
                    retryable_status_codes=[429, 500, 502, 503, 504],
                    operation_name="VoyageAI Embeddings API"
                )
            except Exception as e:
                msg.fail(f"Unexpected error: {type(e).__name__} - {str(e)}")
                raise

    @staticmethod
    def get_models(token: str, url: str) -> List[str]:
        """Fetch available embedding models from VoyageAI API."""
        return [
            "voyage-2",
            "voyage-large-2",
            "voyage-finance-2",
            "voyage-multilingual-2",
            "voyage-law-2",
            "voyage-code-2",
        ]
