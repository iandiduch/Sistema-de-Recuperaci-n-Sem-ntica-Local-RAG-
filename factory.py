import os
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.embeddings import Embeddings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_anthropic import ChatAnthropic

from config import RAGConfig
from models import Provider, EmbeddingProvider


class LLMFactory:
    """Factoría declarativa para la instanciación de modelos de chat LangChain."""

    @staticmethod
    def create_model(config: RAGConfig) -> BaseChatModel:
        match config.provider:
            case Provider.OPENAI:
                api_key = config.openai_apikey.get_secret_value() if config.openai_apikey else os.getenv("OPENAI_API_KEY")
                if not api_key:
                    raise ValueError(
                        "Falta la clave API de OpenAI. Por favor define OPENAI_API_KEY en tu archivo .env o entorno."
                    )
                return ChatOpenAI(
                    model_name=config.model,
                    temperature=config.temperature,
                    api_key=api_key,  # type: ignore[arg-type]
                    base_url=str(config.base_url) if config.base_url else None,
                    request_timeout=config.timeout_seconds,
                )

            case Provider.ANTHROPIC:
                api_key = config.anthropic_apikey.get_secret_value() if config.anthropic_apikey else os.getenv("ANTHROPIC_API_KEY")
                if not api_key:
                    raise ValueError(
                        "Falta la clave API de Anthropic. Por favor define ANTHROPIC_API_KEY en tu archivo .env o entorno."
                    )
                return ChatAnthropic(
                    model_name=config.model,
                    temperature=config.temperature,
                    api_key=api_key,  # type: ignore[arg-type]
                    base_url=str(config.base_url) if config.base_url else None,
                    timeout=config.timeout_seconds,
                )

            case _:
                raise ValueError(f"Proveedor de LLM no soportado: {config.provider}")


class EmbeddingFactory:
    """Factoría para la instanciación de modelos de Embeddings LangChain."""

    @staticmethod
    def create_embeddings(config: RAGConfig) -> Embeddings:
        match config.embedding_provider:
            case EmbeddingProvider.OPENAI:
                api_key = config.openai_apikey.get_secret_value() if config.openai_apikey else os.getenv("OPENAI_API_KEY")
                if not api_key:
                    raise ValueError(
                        "Falta la clave API de OpenAI para los embeddings. Define OPENAI_API_KEY en tu .env"
                    )
                return OpenAIEmbeddings(
                    model=config.embedding_model,
                    api_key=api_key,  # type: ignore[arg-type]
                    base_url=str(config.base_url) if config.base_url else None,
                )

            case EmbeddingProvider.CHROMA_DEFAULT | EmbeddingProvider.HUGGINGFACE:
                try:
                    from langchain_community.embeddings import FastEmbedEmbeddings
                    return FastEmbedEmbeddings()
                except Exception:
                    try:
                        from langchain_huggingface import HuggingFaceEmbeddings
                        return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
                    except Exception:
                        from langchain_community.embeddings import HuggingFaceEmbeddings
                        return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

            case _:
                raise ValueError(f"Proveedor de Embeddings no soportado: {config.embedding_provider}")
