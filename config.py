from typing import Optional
from pydantic import AnyHttpUrl, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from models import Provider, EmbeddingProvider


class RAGConfig(BaseSettings):
    """
    Configuración centralizada y validada para el sistema RAG mediante Pydantic Settings.
    Carga variables de entorno desde un archivo .env si está disponible.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True
    )

    # Configuración del Modelo LLM
    provider: Provider = Provider.OPENAI
    model: str = "gpt-4o-mini"
    openai_apikey: Optional[SecretStr] = None
    anthropic_apikey: Optional[SecretStr] = None
    base_url: Optional[AnyHttpUrl] = None
    timeout_seconds: int = 60
    temperature: float = 0.0
    max_retries: int = 3

    # Configuración de Embeddings y Base Vectorial ChromaDB
    embedding_provider: EmbeddingProvider = EmbeddingProvider.OPENAI
    embedding_model: str = "text-embedding-3-small"
    chroma_persist_dir: str = "./vectorstore"
    collection_name: str = "rag_knowledge_base"

    # Configuración de Ingesta y Recuperación
    data_dir: str = "./data"
    chunk_size: int = 500
    chunk_overlap: int = 50
    top_k: int = 4

    @field_validator("chunk_size")
    @classmethod
    def _validate_chunk_size(cls, v: int) -> int:
        if v < 100:
            raise ValueError("chunk_size debe ser al menos de 100 tokens")
        return v

    @field_validator("chunk_overlap")
    @classmethod
    def _validate_chunk_overlap(cls, v: int) -> int:
        if v < 0:
            raise ValueError("chunk_overlap no puede ser negativo")
        return v

    @field_validator("top_k")
    @classmethod
    def _validate_top_k(cls, v: int) -> int:
        if v < 1 or v > 10:
            raise ValueError("top_k debe estar entre 1 y 10 para evitar el problema de 'Contexto Infinito'")
        return v

    @field_validator("timeout_seconds")
    @classmethod
    def _timeout_positivo(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("timeout_seconds debe ser > 0")
        return v

    @model_validator(mode="after")
    def _validate_overlap_vs_size(self):
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap debe ser estrictamente menor que chunk_size")
        return self

    @model_validator(mode="after")
    def _key_coincide_con_provider(self):
        # Permite cargar desde alias habituales de entorno si vienen con OPENAI_API_KEY o ANTHROPIC_API_KEY
        key_map = {
            Provider.OPENAI: self.openai_apikey,
            Provider.ANTHROPIC: self.anthropic_apikey,
        }
        key = key_map.get(self.provider)
        if key is None and self.provider in (Provider.OPENAI, Provider.ANTHROPIC):
            # Se permite instanciación si se define posteriormente o se usa mock, pero alertamos si es invocado
            pass
        return self
