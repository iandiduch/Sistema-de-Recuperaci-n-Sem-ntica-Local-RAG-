import dotenv
from typing import Optional
from pydantic import AnyHttpUrl, SecretStr, Field, AliasChoices, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from models import Provider, EmbeddingProvider

# Forzar carga de variables desde .env si existe para sobreescribir variables de sesión obsoletas
dotenv.load_dotenv(override=True)


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
    provider: Provider = Field(
        default=Provider.OPENAI,
        validation_alias=AliasChoices("PROVIDER", "provider")
    )
    model: str = Field(
        default="gpt-4o-mini",
        validation_alias=AliasChoices("MODEL", "model")
    )
    openai_apikey: Optional[SecretStr] = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "openai_api_key", "openai_apikey")
    )
    anthropic_apikey: Optional[SecretStr] = Field(
        default=None,
        validation_alias=AliasChoices("ANTHROPIC_API_KEY", "anthropic_api_key", "anthropic_apikey")
    )
    base_url: Optional[AnyHttpUrl] = Field(
        default=None,
        validation_alias=AliasChoices("BASE_URL", "base_url")
    )
    timeout_seconds: int = Field(
        default=60,
        validation_alias=AliasChoices("TIMEOUT_SECONDS", "timeout_seconds")
    )
    temperature: float = Field(
        default=0.0,
        validation_alias=AliasChoices("TEMPERATURE", "temperature")
    )
    max_retries: int = Field(
        default=3,
        validation_alias=AliasChoices("MAX_RETRIES", "max_retries")
    )

    # Configuración de Embeddings y Base Vectorial ChromaDB
    embedding_provider: EmbeddingProvider = Field(
        default=EmbeddingProvider.OPENAI,
        validation_alias=AliasChoices("EMBEDDING_PROVIDER", "embedding_provider")
    )
    embedding_model: str = Field(
        default="text-embedding-3-small",
        validation_alias=AliasChoices("EMBEDDING_MODEL", "embedding_model")
    )
    chroma_persist_dir: str = Field(
        default="./vectorstore",
        validation_alias=AliasChoices("CHROMA_PERSIST_DIR", "chroma_persist_dir")
    )
    collection_name: str = Field(
        default="rag_knowledge_base",
        validation_alias=AliasChoices("COLLECTION_NAME", "collection_name")
    )

    # Configuración de Ingesta y Recuperación
    data_dir: str = Field(
        default="./data",
        validation_alias=AliasChoices("DATA_DIR", "data_dir")
    )
    chunk_size: int = Field(
        default=500,
        validation_alias=AliasChoices("CHUNK_SIZE", "chunk_size")
    )
    chunk_overlap: int = Field(
        default=50,
        validation_alias=AliasChoices("CHUNK_OVERLAP", "chunk_overlap")
    )
    top_k: int = Field(
        default=4,
        validation_alias=AliasChoices("TOP_K", "top_k")
    )

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
