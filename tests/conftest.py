import pytest
from unittest.mock import AsyncMock, MagicMock
from langchain_core.documents import Document
from pydantic import SecretStr

from config import RAGConfig
from models import Provider, EmbeddingProvider, NivelConfianza
from schemas import RAGResponse, ReferenciaDocumento


@pytest.fixture
def test_config() -> RAGConfig:
    """Configuración de prueba controlada."""
    return RAGConfig(
        provider=Provider.OPENAI,
        model="gpt-4o-mini",
        openai_apikey=SecretStr("sk-test-key-1234567890abcdef"),
        embedding_provider=EmbeddingProvider.OPENAI,
        embedding_model="text-embedding-3-small",
        chroma_persist_dir="./test_vectorstore",
        collection_name="test_collection",
        data_dir="./data",
        chunk_size=500,
        chunk_overlap=50,
        top_k=4,
        max_retries=2,
        temperature=0.0,
        timeout_seconds=30,
    )


@pytest.fixture
def sample_raw_markdown() -> str:
    """Texto Markdown sintético con impurezas para pruebas de procesamiento y limpieza."""
    return """
# Política de Resiliencia y Reintentos\x00\x08

Esta política define las directrices obligatorias...... de tolerancia a fallos.

## 1. Patrón Circuit Breaker
El Circuit Breaker previene que un servicio siga realizando llamadas remotas a una dependencia degradada.
Posee 3 estados:
- Cerrado (Closed): Las solicitudes fluyen normalmente.
- Abierto (Open): Falla inmediata tras umbral de error (50% en ventana de 20 solicitudes).
- Semi-Abierto (Half-Open): Permite 5 solicitudes de prueba tras 30 segundos.

-------------------
## 2. Política de Reintentos (Backoff Exponencial)
Solo aplica a operaciones idempotentes con header X-Idempotency-Key.
Máximo 3 reintentos con Full Jitter (base 100ms, cap 3000ms).
"""


@pytest.fixture
def sample_documents() -> list[Document]:
    """Lista de fragmentos Document simulando la salida de ChromaDB."""
    return [
        Document(
            page_content=(
                "El Circuit Breaker funciona con tres estados: Cerrado (Closed), "
                "Abierto (Open) y Semi-Abierto (Half-Open). Si la tasa de fallas supera "
                "el 50% en 20 solicitudes, pasa a Abierto durante 30 segundos."
            ),
            metadata={
                "source": "02_politica_resiliencia_reintentos.md",
                "chunk_id": "02_politica_resiliencia_reintentos.md_chunk_1",
                "tokens": 42,
            }
        ),
        Document(
            page_content=(
                "Los reintentos solo aplican a operaciones idempotentes. "
                "Se permite un máximo de 3 reintentos con backoff exponencial y Full Jitter."
            ),
            metadata={
                "source": "02_politica_resiliencia_reintentos.md",
                "chunk_id": "02_politica_resiliencia_reintentos.md_chunk_2",
                "tokens": 30,
            }
        ),
    ]


@pytest.fixture
def sample_grounded_response() -> RAGResponse:
    """Respuesta RAG estructurada esperada para caso grounded."""
    return RAGResponse(
        respuesta=(
            "Los 3 estados del Circuit Breaker son Cerrado, Abierto y Semi-Abierto. "
            "La política de reintentos permite máximo 3 intentos con backoff exponencial y Full Jitter."
        ),
        encontrado_en_contexto=True,
        referencias=[
            ReferenciaDocumento(
                fuente="02_politica_resiliencia_reintentos.md",
                chunk_id="02_politica_resiliencia_reintentos.md_chunk_1",
                fragmento_clave="El Circuit Breaker funciona con tres estados: Cerrado, Abierto y Semi-Abierto.",
            ),
            ReferenciaDocumento(
                fuente="02_politica_resiliencia_reintentos.md",
                chunk_id="02_politica_resiliencia_reintentos.md_chunk_2",
                fragmento_clave="Se permite un máximo de 3 reintentos con backoff exponencial.",
            )
        ],
        nivel_de_confianza=NivelConfianza.ALTA,
    )


@pytest.fixture
def sample_trap_response() -> RAGResponse:
    """Respuesta RAG estructurada esperada para caso trampa / fuera de contexto."""
    return RAGResponse(
        respuesta="No lo sé. La información solicitada no se encuentra en el contexto documental provisto.",
        encontrado_en_contexto=False,
        referencias=[],
        nivel_de_confianza=NivelConfianza.NO_ENCONTRADO,
    )


@pytest.fixture
def mock_vectorstore(sample_documents: list[Document]):
    """Vectorstore simulado con retriever asíncrono."""
    vectorstore = MagicMock()
    retriever = MagicMock()
    retriever.ainvoke = AsyncMock(return_value=sample_documents)
    vectorstore.as_retriever.return_value = retriever
    return vectorstore
