import logging
from typing import List, Optional

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_chroma import Chroma

from config import RAGConfig
from factory import LLMFactory
from ingestion import get_vectorstore
from schemas import RAGResponse

# Configuración básica del sistema de logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("RAGChain")


def format_retrieved_documents(docs: List[Document]) -> str:
    """
    Formatea la lista de fragmentos recuperados en un bloque de contexto legible
    con metadatos explícitos para trazabilidad de citas.
    """
    if not docs:
        return "[NO SE ENCONTRARON DOCUMENTOS RELEVANTES EN LA BASE DE CONOCIMIENTO]"

    formatted_chunks = []
    for doc in docs:
        source = doc.metadata.get("source", "desconocido")
        chunk_id = doc.metadata.get("chunk_id", "sin_id")
        tokens = doc.metadata.get("tokens", "N/A")
        content = doc.page_content.strip()

        block = (
            f"--- INICIO FRAGMENTO ---\n"
            f"[FUENTE: {source} | CHUNK ID: {chunk_id} | TOKENS: {tokens}]\n"
            f"{content}\n"
            f"--- FIN FRAGMENTO ---"
        )
        formatted_chunks.append(block)

    return "\n\n".join(formatted_chunks)


def build_rag_prompt() -> ChatPromptTemplate:
    """
    Construye el ChatPromptTemplate con directiva estricta de veracidad y anti-alucinación.
    """
    system_template = (
        "Eres un asistente técnico de Inteligencia Artificial de alta precisión especializado "
        "en arquitectura de software, resiliencia, seguridad y gestión de operaciones.\n\n"
        "Tu única fuente de conocimiento y verdad para responder la pregunta del usuario es "
        "el CONTEXTO DOCUMENTAL proporcionado a continuación.\n\n"
        "=== CONTEXTO DOCUMENTAL ===\n"
        "{contexto}\n"
        "===========================\n\n"
        "REGLAS ESTRICTAS DE RESPUESTA Y VERACIDAD (FILTRO ANTI-ALUCINACIÓN):\n"
        "1. GROUNDING ABSOLUTO: Responde ÚNICAMENTE utilizando hechos e información explícita "
        "contenida en el CONTEXTO DOCUMENTAL.\n"
        "2. MANEJO DE INFORMACIÓN NO DISPONIBLE: Si la pregunta NO se responde con el contexto provisto, "
        "o el contexto no contiene datos suficientes:\n"
        "   - En el campo 'respuesta': Debes responder textualmente 'No lo sé. La información solicitada no se encuentra en el contexto documental provisto.'\n"
        "   - En el campo 'encontrado_en_contexto': Asigna estrictamente 'false'.\n"
        "   - En el campo 'nivel_de_confianza': Asigna 'no_encontrado'.\n"
        "   - En el campo 'referencias': Deja la lista vacía ([]).\n"
        "3. SI LA INFORMACIÓN SÍ EXISTE EN EL CONTEXTO:\n"
        "   - Redacta una respuesta técnica, clara y fundamentada.\n"
        "   - En el campo 'encontrado_en_contexto': Asigna 'true'.\n"
        "   - En el campo 'nivel_de_confianza': Asigna 'alta' o 'media'.\n"
        "   - En el campo 'referencias': Extrae cada fragmento documental utilizado indicando 'fuente', 'chunk_id' y 'fragmento_clave'.\n"
        "4. PROHIBICIÓN: Queda estrictamente prohibido utilizar conocimiento previo no respaldado por el contexto.{feedback_instruction}"
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_template),
        ("human", "Pregunta del usuario: {pregunta}")
    ])
    return prompt


def build_rag_pipeline(config: Optional[RAGConfig] = None, vectorstore: Optional[Chroma] = None):
    """
    Construye la cadena LCEL RAG declarativa con salida estructurada Pydantic y resiliencia.

    Flujo LCEL:
      Input (dict: {"pregunta", "contexto", "feedback_instruction"})
        -> ChatPromptTemplate
        -> BaseChatModel.with_structured_output(RAGResponse).with_retry()
        -> RAGResponse
    """
    if config is None:
        config = RAGConfig()

    logger.info(f"Configurando cadena RAG con modelo {config.model} ({config.provider.value})")

    # 1. Instanciación del modelo LLM
    base_model = LLMFactory.create_model(config)

    # 2. Configuración de salida estructurada Pydantic + Resiliencia
    structured_model = base_model.with_structured_output(RAGResponse)
    resilient_model = structured_model.with_retry(
        stop_after_attempt=config.max_retries
    )

    # 3. Prompt de sistema con soporte para realimentación de errores
    prompt = build_rag_prompt()

    # 4. Composición declarativa LCEL
    chain = prompt | resilient_model
    return chain


async def get_rag_response(
    query: str,
    config: Optional[RAGConfig] = None,
    vectorstore: Optional[Chroma] = None
) -> RAGResponse:
    """
    Función asíncrona principal del sistema RAG:
    a. Realiza una búsqueda de similitud semántica en ChromaDB recuperando los top_k chunks.
    b. Formatea los documentos recuperados como contexto para el prompt.
    c. Invoca la cadena LCEL de forma asíncrona (.ainvoke).
    d. Valida y retorna el objeto Pydantic RAGResponse garantizando referencias y ausencia de alucinaciones.
    """
    if config is None:
        config = RAGConfig()

    if vectorstore is None:
        vectorstore = get_vectorstore(config)

    logger.info(f"1. Realizando búsqueda semántica en ChromaDB para: '{query}' (top_k={config.top_k})...")
    
    # Capa de Recuperación (Retriever asíncrono o sincrónico de Chroma)
    retriever = vectorstore.as_retriever(
        search_kwargs={"k": config.top_k}
    )
    
    retrieved_docs: List[Document] = await retriever.ainvoke(query)
    logger.info(f"2. Se recuperaron {len(retrieved_docs)} fragmentos relevantes.")

    context_str = format_retrieved_documents(retrieved_docs)

    chain = build_rag_pipeline(config=config, vectorstore=vectorstore)

    last_error: Optional[Exception] = None
    feedback_instruction = ""

    for intento in range(1, config.max_retries + 1):
        try:
            logger.info(f"3. Ejecutando llamada asíncrona al LLM (.ainvoke) - Intento {intento}/{config.max_retries}...")
            
            resultado: RAGResponse = await chain.ainvoke({
                "pregunta": query,
                "contexto": context_str,
                "feedback_instruction": feedback_instruction
            })

            logger.info("4. Respuesta generada y validada con Pydantic exitosamente.")
            logger.info(f"   - Encontrado en contexto: {resultado.encontrado_en_contexto}")
            logger.info(f"   - Nivel de confianza: {resultado.nivel_de_confianza.value}")
            logger.info(f"   - Referencias citadas: {len(resultado.referencias)}")
            return resultado

        except Exception as err:
            last_error = err
            logger.warning(
                f"[Fallo en intento {intento}/{config.max_retries}]: {err}. "
                f"Reintentando con feedback de error en prompt..."
            )
            feedback_instruction = (
                f"\n\nNOTA DE AUTOCORRECCIÓN (Error en intento previo):\n"
                f"El formato o validación Pydantic arrojó el siguiente error: \"{err}\".\n"
                f"Por favor corrige rigurosamente este formato en tu respuesta JSON."
            )

    logger.error(f"Se superaron los {config.max_retries} reintentos sin obtener una respuesta válida.")
    raise last_error
