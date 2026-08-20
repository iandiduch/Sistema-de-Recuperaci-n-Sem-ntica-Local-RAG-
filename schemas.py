from pydantic import BaseModel, Field
from models import NivelConfianza


class ReferenciaDocumento(BaseModel):
    """
    Representa una cita o referencia específica de un documento fuente recuperado.
    """
    fuente: str = Field(
        ...,
        description="Nombre del archivo o identificador del documento origen (ej. '02_politica_resiliencia_reintentos.md')."
    )
    chunk_id: str = Field(
        ...,
        description="Identificador del fragmento o chunk de donde se extrajo la información (ej. 'chunk_2')."
    )
    fragmento_clave: str = Field(
        ...,
        min_length=1,
        description="Cita textual breve o fragmento relevante del documento que sustenta la respuesta."
    )


class RAGResponse(BaseModel):
    """
    Esquema de salida estructurado y fuertemente tipado para el sistema RAG.
    Garantiza trazabilidad documental y prevención estricta de alucinaciones.
    """
    respuesta: str = Field(
        ...,
        min_length=1,
        description=(
            "Respuesta final generada y fundamentada exclusivamente en el contexto provisto. "
            "Si la información no está en el contexto, debe indicar explícitamente "
            "'No lo sé. La información solicitada no se encuentra en el contexto documental provisto.'"
        )
    )
    encontrado_en_contexto: bool = Field(
        ...,
        description=(
            "Indica True si la respuesta fue encontrada con certeza en los fragmentos del contexto. "
            "Indica False si la información no está disponible en los documentos recuperados."
        )
    )
    referencias: list[ReferenciaDocumento] = Field(
        default_factory=list,
        description="Lista de citas y fragmentos documentales utilizados como sustento factual."
    )
    nivel_de_confianza: NivelConfianza = Field(
        ...,
        description="Nivel de certeza de la respuesta basado exclusivamente en la evidencia documental."
    )
