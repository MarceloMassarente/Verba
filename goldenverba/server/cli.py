import click
import warnings
import os
from dotenv import load_dotenv

# Suppress websockets deprecation warnings from uvicorn
# This is a known issue: uvicorn uses websockets.legacy API which is deprecated
# The warning doesn't affect functionality and will be fixed in future uvicorn updates
warnings.filterwarnings("ignore", category=DeprecationWarning, module="websockets")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="uvicorn.protocols.websockets")
warnings.filterwarnings("ignore", message=".*websockets.legacy.*")
warnings.filterwarnings("ignore", message=".*remove second argument of ws_handler.*")
warnings.filterwarnings("ignore", message=".*WebSocketServerProtocol.*")
# Also suppress via environment variable for Railway
if "PYTHONWARNINGS" not in os.environ:
    os.environ["PYTHONWARNINGS"] = "ignore::DeprecationWarning:websockets"

import uvicorn

from goldenverba import verba_manager
from goldenverba.server.types import Credentials

load_dotenv()


@click.group()
def cli():
    """Main command group for verba."""
    pass


@cli.command()
@click.option(
    "--port",
    default=8000,
    help="FastAPI Port",
)
@click.option(
    "--host",
    default="localhost",
    help="FastAPI Host",
)
@click.option(
    "--prod/--no-prod",
    default=False,
    help="Run in production mode.",
)
@click.option(
    "--workers",
    default=4,
    help="Workers to run Verba",
)
def start(port, host, prod, workers):
    """
    Run the FastAPI application.
    """
    uvicorn.run(
        "goldenverba.server.api:app",
        host=host,
        port=port,
        reload=(not prod),
        workers=workers,
    )


@click.option(
    "--url",
    default=os.getenv("WEAVIATE_URL_VERBA"),
    help="Weaviate URL",
)
@click.option(
    "--api_key",
    default=os.getenv("WEAVIATE_API_KEY_VERBA"),
    help="Weaviate API Key",
)
@click.option(
    "--deployment",
    default="",
    help="Deployment (Local, Weaviate, Docker)",
)
@click.option(
    "--full_reset",
    default=False,
    help="Full reset (True, False)",
)
@cli.command()
def reset(url, api_key, deployment, full_reset):
    """
    Run the FastAPI application.
    """
    import asyncio

    manager = verba_manager.VerbaManager()

    async def async_reset():
        if url is not None and api_key is not None:
            if deployment == "" or deployment == "Weaviate":
                client = await manager.connect(
                    Credentials(deployment="Weaviate", url=url, key=api_key)
                )
            elif deployment == "Docker":
                client = await manager.connect(
                    Credentials(deployment="Docker", url=url, key=api_key)
                )
            else:
                raise ValueError("Invalid deployment")
        else:
            if deployment == "" or deployment == "Local":
                client = await manager.connect(
                    Credentials(deployment="Local", url="", key="")
                )
            else:
                raise ValueError("Invalid deployment")

        if not full_reset:
            await manager.reset_rag_config(client)
            await manager.reset_theme_config(client)
            await manager.reset_user_config(client)
        else:
            await manager.weaviate_manager.delete_all(client)

        await client.close()

    asyncio.run(async_reset())


if __name__ == "__main__":
    cli()
