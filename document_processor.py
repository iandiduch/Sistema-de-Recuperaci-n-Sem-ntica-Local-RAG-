import re
from typing import List, Optional
import tiktoken
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


class DocumentProcessor:
    """
    Procesador de documentos encargado de la limpieza textual y fragmentación (chunking)
    estratégica basada en conteo de tokens mediante tiktoken y RecursiveCharacterTextSplitter.
    """

    def __init__(
        self,
        model_encoding: str = "cl100k_base",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # Inicializar el encoding de tiktoken
        try:
            self.tokenizer = tiktoken.get_encoding(model_encoding)
        except Exception:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")

        # Configurar RecursiveCharacterTextSplitter con función de conteo por tokens
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=self.calculate_tokens,
            separators=["\n## ", "\n### ", "\n\n", "\n", ". ", " ", ""]
        )

    def clean_text(self, text: str) -> str:
        """
        Limpia el texto eliminando caracteres de control, secuencias repetidas,
        espacios duplicados y normalizando saltos de línea.
        """
        # 1. Eliminar caracteres de control no imprimibles (ej. restos de OCR / PDF)
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

        # 2. Limpiar secuencias repetidas de puntos o guiones (ej. de tablas de contenido o índices)
        text = re.sub(r'(\.\s*){3,}', '. ', text)
        text = re.sub(r'(-{3,})', '---', text)

        # 3. Normalizar espacios y tabulaciones repetidas
        text = re.sub(r'[ \t]+', ' ', text)

        # 4. Normalizar saltos de línea múltiples conservando párrafos lógicos
        text = re.sub(r'\n\s*\n+', '\n\n', text)

        return text.strip()

    def calculate_tokens(self, text: str) -> int:
        """Calcula la cantidad de tokens exactos usando el tokenizer de tiktoken."""
        return len(self.tokenizer.encode(text))

    def split_text(self, raw_text: str) -> List[str]:
        """Pipeline básico: Limpieza -> Fragmentación en lista de strings."""
        cleaned = self.clean_text(raw_text)
        return self.splitter.split_text(cleaned)

    def process_to_documents(
        self,
        raw_text: str,
        source_name: str,
        extra_metadata: Optional[dict] = None
    ) -> List[Document]:
        """
        Limpia y fragmenta el texto, retornando una lista de objetos Document de LangChain
        con metadatos enriquecidos (source, chunk_id, token_count, etc.).
        """
        cleaned = self.clean_text(raw_text)
        chunks = self.splitter.split_text(cleaned)

        documents = []
        base_meta = extra_metadata or {}

        for index, chunk in enumerate(chunks, start=1):
            chunk_id = f"{source_name}_chunk_{index}"
            meta = {
                **base_meta,
                "source": source_name,
                "chunk_id": chunk_id,
                "chunk_index": index,
                "total_chunks": len(chunks),
                "tokens": self.calculate_tokens(chunk)
            }
            doc = Document(page_content=chunk, metadata=meta)
            documents.append(doc)

        return documents
