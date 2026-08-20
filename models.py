from enum import Enum


class Provider(str, Enum):
    """Proveedores de Modelos de Lenguaje (LLM) soportados."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class EmbeddingProvider(str, Enum):
    """Proveedores de Embeddings soportados."""
    OPENAI = "openai"
    HUGGINGFACE = "huggingface"
    CHROMA_DEFAULT = "chroma_default"


class NivelConfianza(str, Enum):
    """Nivel de confianza en la respuesta generada según el contexto recuperado."""
    ALTA = "alta"
    MEDIA = "media"
    BAJA = "baja"
    NO_ENCONTRADO = "no_encontrado"
