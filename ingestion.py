import os
import glob
import logging
from typing import List, Optional
from langchain_core.documents import Document
from langchain_chroma import Chroma

from config import RAGConfig
from factory import EmbeddingFactory
from document_processor import DocumentProcessor

# Configuración del sistema de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("RAGIngestion")


def load_raw_files_from_data(data_dir: str) -> List[tuple[str, str]]:
    """
    Carga todos los archivos .txt y .md del directorio especificado.
    Retorna una lista de tuplas (nombre_archivo, contenido_texto).
    """
    if not os.path.exists(data_dir):
        raise FileNotFoundError(f"El directorio de datos '{data_dir}' no existe.")

    supported_extensions = ["*.md", "*.txt"]
    file_paths = []
    for ext in supported_extensions:
        pattern = os.path.join(data_dir, "**", ext)
        file_paths.extend(glob.glob(pattern, recursive=True))

    if not file_paths:
        logger.warning(f"No se encontraron archivos .md o .txt en {data_dir}")
        return []

    documents_raw = []
    for path in sorted(file_paths):
        filename = os.path.basename(path)
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            documents_raw.append((filename, content))
            logger.info(f"Cargado documento fuente: {filename} ({len(content)} caracteres)")
        except Exception as e:
            logger.error(f"Error al leer el archivo {path}: {e}")

    return documents_raw


def get_vectorstore(config: Optional[RAGConfig] = None) -> Chroma:
    """
    Inicializa o conecta con la base de datos vectorial persistente ChromaDB
    utilizando el modelo de embeddings configurado.
    """
    if config is None:
        config = RAGConfig()

    embeddings = EmbeddingFactory.create_embeddings(config)

    vectorstore = Chroma(
        collection_name=config.collection_name,
        embedding_function=embeddings,
        persist_directory=config.chroma_persist_dir,
    )
    return vectorstore


def ingest_knowledge_base(
    config: Optional[RAGConfig] = None,
    force_reindex: bool = False
) -> Chroma:
    """
    Módulo principal de ingesta:
    1. Verifica si la base de datos vectorial ya existe y contiene documentos (persistencia).
    2. Si ya está poblada y force_reindex=False, reutiliza la base evitando reindexación innecesaria.
    3. Si está vacía o force_reindex=True, procesa los documentos con DocumentProcessor (chunking con tiktoken)
       y los persiste en ChromaDB.
    """
    if config is None:
        config = RAGConfig()

    logger.info("Iniciando verificación del almacén vectorial ChromaDB...")
    vectorstore = get_vectorstore(config)

    # Verificar si la colección ya contiene documentos indexados
    try:
        existing_count = vectorstore._collection.count()
    except Exception:
        existing_count = 0

    if existing_count > 0 and not force_reindex:
        logger.info(
            f"Base vectorial persistente encontrada en '{config.chroma_persist_dir}' "
            f"con {existing_count} fragmentos indexados. Se omite re-indexación (Persistencia activa)."
        )
        return vectorstore

    if force_reindex and existing_count > 0:
        logger.warning(
            f"Flag 'force_reindex=True' detectado. Purgando {existing_count} registros antiguos..."
        )
        try:
            # Eliminar todos los IDs existentes
            all_ids = vectorstore.get()["ids"]
            if all_ids:
                vectorstore.delete(ids=all_ids)
            logger.info("Colección anterior purgada correctamente.")
        except Exception as e:
            logger.warning(f"No se pudo purgar la colección anterior: {e}")

    # 1. Cargar documentos crudos desde /data
    raw_files = load_raw_files_from_data(config.data_dir)
    if not raw_files:
        logger.warning("No hay documentos para indexar.")
        return vectorstore

    # 2. Procesar y fragmentar documentos (Chunking con tiktoken y RecursiveCharacterTextSplitter)
    processor = DocumentProcessor(
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap
    )

    all_processed_docs: List[Document] = []
    total_tokens = 0

    for filename, text in raw_files:
        docs = processor.process_to_documents(
            raw_text=text,
            source_name=filename,
            extra_metadata={"category": "technical_docs"}
        )
        all_processed_docs.extend(docs)
        file_tokens = sum(doc.metadata.get("tokens", 0) for doc in docs)
        total_tokens += file_tokens
        logger.info(
            f"-> Documento '{filename}': {len(docs)} chunks generados ({file_tokens} tokens totales)."
        )

    logger.info(
        f"Total de chunks preparados para indexación: {len(all_processed_docs)} "
        f"(~{total_tokens} tokens)."
    )

    # 3. Indexar y persistir en ChromaDB
    try:
        # Extraer IDs únicos para cada chunk
        chunk_ids = [doc.metadata["chunk_id"] for doc in all_processed_docs]
        vectorstore.add_documents(documents=all_processed_docs, ids=chunk_ids)
        logger.info(
            f"✅ Ingesta completada exitosamente. {len(all_processed_docs)} chunks persistidos "
            f"en '{config.chroma_persist_dir}' (Colección: '{config.collection_name}')."
        )
    except Exception as e:
        logger.error(f"Error durante la persistencia en ChromaDB: {e}")
        raise e

    return vectorstore


if __name__ == "__main__":
    print("=================================================================")
    print("      MÓDULO DE INGESTA Y CHUNKING RAG - CHROMADB PERSISTENTE    ")
    print("=================================================================\n")

    cfg = RAGConfig()
    ingest_knowledge_base(config=cfg, force_reindex=False)
