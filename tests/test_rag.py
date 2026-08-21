import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import ValidationError, SecretStr
from langchain_core.documents import Document

from config import RAGConfig
from models import Provider, EmbeddingProvider, NivelConfianza
from schemas import RAGResponse, ReferenciaDocumento
from document_processor import DocumentProcessor
from factory import LLMFactory, EmbeddingFactory
from chain import (
    format_retrieved_documents,
    build_rag_prompt,
    get_rag_response,
)


# ==============================================================================
# 1. PRUEBAS UNITARIAS: PROCESADOR DE DOCUMENTOS Y CHUNKING CON TIKTOKEN
# ==============================================================================
@pytest.mark.unit
class TestDocumentProcessor:
    """Pruebas para DocumentProcessor: limpieza, conteo de tokens y fragmentación."""

    def test_clean_text_removes_control_chars_and_normalizes_spaces(self):
        processor = DocumentProcessor(chunk_size=500, chunk_overlap=50)
        dirty_text = "Texto con control\x00\x08 y puntos......\n\n\n\nEspacio   extra."
        cleaned = processor.clean_text(dirty_text)

        assert "\x00" not in cleaned
        assert "\x08" not in cleaned
        assert "......" not in cleaned
        assert "   " not in cleaned
        assert "\n\n\n\n" not in cleaned
        assert "Texto con control y puntos. \n\nEspacio extra." in cleaned or "Texto con control" in cleaned

    def test_calculate_tokens_accurate_with_tiktoken(self):
        processor = DocumentProcessor(model_encoding="cl100k_base")
        text = "Arquitectura de microservicios y resiliencia distribuida."
        tokens = processor.calculate_tokens(text)
        assert isinstance(tokens, int)
        assert tokens > 0

    def test_process_to_documents_generates_correct_chunks_and_metadata(self, sample_raw_markdown: str):
        chunk_size = 50
        chunk_overlap = 10
        processor = DocumentProcessor(
            model_encoding="cl100k_base",
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )

        docs = processor.process_to_documents(
            raw_text=sample_raw_markdown,
            source_name="02_politica_resiliencia_reintentos.md",
            extra_metadata={"category": "technical"}
        )

        assert len(docs) > 0
        for i, doc in enumerate(docs, start=1):
            assert isinstance(doc, Document)
            assert doc.metadata["source"] == "02_politica_resiliencia_reintentos.md"
            assert doc.metadata["chunk_id"] == f"02_politica_resiliencia_reintentos.md_chunk_{i}"
            assert doc.metadata["chunk_index"] == i
            assert doc.metadata["total_chunks"] == len(docs)
            assert doc.metadata["category"] == "technical"
            assert doc.metadata["tokens"] <= chunk_size + 15  # Tolerancia por división de palabras

    def test_split_text_with_empty_or_whitespace_input(self):
        processor = DocumentProcessor(chunk_size=500, chunk_overlap=50)
        assert processor.split_text("") == []
        assert processor.split_text("   \n\n   ") == []


# ==============================================================================
# 2. PRUEBAS UNITARIAS: ESQUEMAS PYDANTIC Y VALIDACIÓN TIPADA
# ==============================================================================
@pytest.mark.unit
class TestSchemas:
    """Validación del modelo de salida estructurada RAGResponse y ReferenciaDocumento."""

    def test_referencia_documento_valid(self):
        ref = ReferenciaDocumento(
            fuente="01_arquitectura_microservicios.md",
            chunk_id="chunk_1",
            fragmento_clave="API Gateway centraliza la autenticación."
        )
        assert ref.fuente == "01_arquitectura_microservicios.md"
        assert ref.chunk_id == "chunk_1"
        assert ref.fragmento_clave == "API Gateway centraliza la autenticación."

    def test_referencia_documento_empty_raises_validation_error(self):
        with pytest.raises(ValidationError):
            ReferenciaDocumento(
                fuente="test.md",
                chunk_id="chunk_1",
                fragmento_clave=""  # min_length=1 violado
            )

    def test_rag_response_valid_grounded(self, sample_grounded_response: RAGResponse):
        assert sample_grounded_response.encontrado_en_contexto is True
        assert len(sample_grounded_response.referencias) == 2
        assert sample_grounded_response.nivel_de_confianza == NivelConfianza.ALTA

        # Validar serialización JSON
        json_data = sample_grounded_response.model_dump()
        assert json_data["encontrado_en_contexto"] is True
        assert json_data["nivel_de_confianza"] == "alta"

    def test_rag_response_valid_trap(self, sample_trap_response: RAGResponse):
        assert sample_trap_response.encontrado_en_contexto is False
        assert len(sample_trap_response.referencias) == 0
        assert sample_trap_response.nivel_de_confianza == NivelConfianza.NO_ENCONTRADO


# ==============================================================================
# 3. PRUEBAS UNITARIAS: CONFIGURACIÓN CENTRALIZADA (RAGConfig)
# ==============================================================================
@pytest.mark.unit
class TestRAGConfig:
    """Validación de reglas de negocio en configuración Pydantic Settings."""

    def test_rag_config_default_values(self):
        cfg = RAGConfig(
            openai_apikey=SecretStr("sk-dummy"),
            anthropic_apikey=SecretStr("sk-dummy")
        )
        assert cfg.chunk_size == 500
        assert cfg.chunk_overlap == 50
        assert cfg.top_k == 4
        assert cfg.provider == Provider.OPENAI
        assert cfg.embedding_provider == EmbeddingProvider.OPENAI

    def test_rag_config_invalid_chunk_size_raises(self):
        with pytest.raises(ValidationError, match="chunk_size debe ser al menos de 100 tokens"):
            RAGConfig(chunk_size=50)

    def test_rag_config_overlap_greater_than_chunk_size_raises(self):
        with pytest.raises(ValidationError, match="chunk_overlap debe ser estrictamente menor que chunk_size"):
            RAGConfig(chunk_size=300, chunk_overlap=300)

    def test_rag_config_invalid_top_k_raises(self):
        with pytest.raises(ValidationError, match="top_k debe estar entre 1 y 10"):
            RAGConfig(top_k=0)

        with pytest.raises(ValidationError, match="top_k debe estar entre 1 y 10"):
            RAGConfig(top_k=15)

    def test_rag_config_invalid_timeout_raises(self):
        with pytest.raises(ValidationError, match="timeout_seconds debe ser > 0"):
            RAGConfig(timeout_seconds=0)


# ==============================================================================
# 4. PRUEBAS UNITARIAS: FORMATEO DE CONTEXTO Y PROMPTS
# ==============================================================================
@pytest.mark.unit
class TestContextAndPromptFormatting:
    """Validación de formateadores de documentos y templates de prompts."""

    def test_format_retrieved_documents_empty(self):
        res = format_retrieved_documents([])
        assert res == "[NO SE ENCONTRARON DOCUMENTOS RELEVANTES EN LA BASE DE CONOCIMIENTO]"

    def test_format_retrieved_documents_with_docs(self, sample_documents: list[Document]):
        res = format_retrieved_documents(sample_documents)
        assert "--- INICIO FRAGMENTO ---" in res
        assert "[FUENTE: 02_politica_resiliencia_reintentos.md | CHUNK ID: 02_politica_resiliencia_reintentos.md_chunk_1 | TOKENS: 42]" in res
        assert "Circuit Breaker" in res
        assert "--- FIN FRAGMENTO ---" in res

    def test_build_rag_prompt_structure(self):
        prompt = build_rag_prompt()
        messages = prompt.format_messages(
            contexto="Contexto de prueba",
            pregunta="¿Cuál es el timeout?",
            feedback_instruction=""
        )
        assert len(messages) == 2
        assert messages[0].type == "system"
        assert "FILTRO ANTI-ALUCINACIÓN" in messages[0].content
        assert "Contexto de prueba" in messages[0].content
        assert messages[1].type == "human"
        assert "¿Cuál es el timeout?" in messages[1].content


# ==============================================================================
# 5. PRUEBAS UNITARIAS: FACTORÍAS DE MODELOS Y EMBEDDINGS
# ==============================================================================
@pytest.mark.unit
class TestFactories:
    """Validación de la creación desacoplada de LLMs y Embeddings."""

    def test_llm_factory_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        cfg = RAGConfig(
            provider=Provider.OPENAI,
            openai_apikey=None
        )
        with pytest.raises(ValueError, match="Falta la clave API de OpenAI"):
            LLMFactory.create_model(cfg)

    def test_embedding_factory_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        cfg = RAGConfig(
            embedding_provider=EmbeddingProvider.OPENAI,
            openai_apikey=None
        )
        with pytest.raises(ValueError, match="Falta la clave API de OpenAI para los embeddings"):
            EmbeddingFactory.create_embeddings(cfg)

    def test_llm_factory_openai_instantiation(self, test_config: RAGConfig):
        model = LLMFactory.create_model(test_config)
        assert model is not None
        assert model.model_name == "gpt-4o-mini"
        assert model.temperature == 0.0


# ==============================================================================
# 6. PRUEBAS ASÍNCRONAS DE CADENA LCEL (RAG PIPELINE END-TO-END SIMULADO)
# ==============================================================================
@pytest.mark.unit
class TestRAGChainAsync:
    """Pruebas de la función asíncrona get_rag_response con mocks de recuperación y LLM."""

    @pytest.mark.asyncio
    async def test_get_rag_response_grounded_query(
        self,
        test_config: RAGConfig,
        mock_vectorstore,
        sample_grounded_response: RAGResponse
    ):
        """Valida consulta técnica grounded que extrae hechos y citas documentales."""
        query = "¿Cuáles son los 3 estados del Circuit Breaker y qué política de reintentos se aplica?"

        # Mock de la cadena LCEL para retornar la respuesta estructurada esperada
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=sample_grounded_response)

        with patch("chain.build_rag_pipeline", return_value=mock_chain):
            resultado = await get_rag_response(
                query=query,
                config=test_config,
                vectorstore=mock_vectorstore
            )

        # Aserciones de negocio y tipado
        assert isinstance(resultado, RAGResponse)
        assert resultado.encontrado_en_contexto is True
        assert resultado.nivel_de_confianza == NivelConfianza.ALTA
        assert len(resultado.referencias) >= 1
        assert "Circuit Breaker" in resultado.respuesta
        assert resultado.referencias[0].fuente == "02_politica_resiliencia_reintentos.md"

        # Verificar que el retriever fue llamado de forma asíncrona con el query
        mock_vectorstore.as_retriever().ainvoke.assert_awaited_once_with(query)

    @pytest.mark.asyncio
    async def test_get_rag_response_trap_anti_hallucination(
        self,
        test_config: RAGConfig,
        mock_vectorstore,
        sample_trap_response: RAGResponse
    ):
        """Valida que una consulta trampa/fuera de dominio active el filtro anti-alucinación."""
        query = "¿Cuál es la receta de una salsa pomodoro con albahaca?"

        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=sample_trap_response)

        with patch("chain.build_rag_pipeline", return_value=mock_chain):
            resultado = await get_rag_response(
                query=query,
                config=test_config,
                vectorstore=mock_vectorstore
            )

        # Aserciones del filtro anti-alucinación
        assert isinstance(resultado, RAGResponse)
        assert resultado.encontrado_en_contexto is False
        assert resultado.nivel_de_confianza == NivelConfianza.NO_ENCONTRADO
        assert len(resultado.referencias) == 0
        assert "No lo sé" in resultado.respuesta

    @pytest.mark.asyncio
    async def test_get_rag_response_resilience_retry_on_initial_failure(
        self,
        test_config: RAGConfig,
        mock_vectorstore,
        sample_grounded_response: RAGResponse
    ):
        """Valida que el bucle de resiliencia reintente y agregue feedback si el primer intento falla."""
        query = "¿Pregunta que falla transitoriamente?"

        mock_chain = MagicMock()
        # Primer intento lanza excepción de parsing Pydantic, segundo intento retorna éxito
        mock_chain.ainvoke = AsyncMock(
            side_effect=[
                ValidationError.from_exception_data("MockParsingError", []),
                sample_grounded_response
            ]
        )

        with patch("chain.build_rag_pipeline", return_value=mock_chain):
            resultado = await get_rag_response(
                query=query,
                config=test_config,
                vectorstore=mock_vectorstore
            )

        assert resultado.encontrado_en_contexto is True
        assert mock_chain.ainvoke.await_count == 2

    @pytest.mark.asyncio
    async def test_get_rag_response_exceeds_max_retries_raises_exception(
        self,
        test_config: RAGConfig,
        mock_vectorstore
    ):
        """Valida que si se superan los max_retries configurados, se propague la excepción final."""
        query = "¿Pregunta que falla continuamente?"

        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(side_effect=RuntimeError("API Gateway Timeout simulado"))

        with patch("chain.build_rag_pipeline", return_value=mock_chain):
            with pytest.raises(RuntimeError, match="API Gateway Timeout simulado"):
                await get_rag_response(
                    query=query,
                    config=test_config,
                    vectorstore=mock_vectorstore
                )

        assert mock_chain.ainvoke.await_count == test_config.max_retries


# ==============================================================================
# 7. PRUEBAS DE INTEGRACIÓN EN VIVO (OPCIONALES CON API KEY REAL)
# ==============================================================================
@pytest.mark.integration
class TestLiveIntegration:
    """
    Pruebas de integración contra ChromaDB y proveedores de LLM reales.
    Se omiten automáticamente si no se detecta una OPENAI_API_KEY válida.
    """

    @pytest.fixture(autouse=True)
    def check_api_key(self):
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key or api_key.startswith("sk-tu-") or api_key == "sk-...":
            pytest.skip("Omitiendo prueba de integración: OPENAI_API_KEY no configurada o de marcador de posición.")

    @pytest.mark.asyncio
    async def test_live_rag_grounded_query(self):
        """Ejecuta una consulta real contra ChromaDB y el LLM configurado."""
        cfg = RAGConfig()
        query = "¿Cuáles son los 3 estados del Circuit Breaker según la norma?"

        resultado = await get_rag_response(query=query, config=cfg)

        assert isinstance(resultado, RAGResponse)
        assert resultado.encontrado_en_contexto is True
        assert len(resultado.referencias) >= 1
        assert "02_politica_resiliencia_reintentos.md" in [r.fuente for r in resultado.referencias]
