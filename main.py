import asyncio
import json
import logging
import time

from config import RAGConfig
from ingestion import ingest_knowledge_base
from chain import get_rag_response

# Configuración del logger principal
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("RAGMain")


async def main():
    print("=" * 80)
    print("   SISTEMA DE RECUPERACIÓN SEMÁNTICA LOCAL (RAG) - PRE-ENTREGA 3   ")
    print("        LangChain LCEL Asíncrono + ChromaDB + Validación Pydantic   ")
    print("=" * 80 + "\n")

    # 1. Carga y validación de configuración
    try:
        config = RAGConfig()
        print(f"[CONFIGURACIÓN ACTIVA]")
        print(f" - Proveedor LLM:       {config.provider.value.upper()} ({config.model})")
        print(f" - Proveedor Embedding: {config.embedding_provider.value}")
        print(f" - Directorio Vectorial: {config.chroma_persist_dir}")
        print(f" - Chunk Size / Overlap: {config.chunk_size} tokens / {config.chunk_overlap} tokens")
        print(f" - Top K Recuperación:  {config.top_k} fragmentos\n")
    except Exception as e:
        print(f"[ERROR DE CONFIGURACIÓN]: {e}")
        print("Asegúrate de definir tus variables de entorno en el archivo .env (ver .env.example).\n")
        return

    # 2. Paso de Ingesta y Verificación de Persistencia
    print("-----------------------------------------------------------------")
    print("PASO 1: VERIFICACIÓN / INGESTA EN CHROMADB PERSISTENTE")
    print("-----------------------------------------------------------------")
    try:
        vectorstore = ingest_knowledge_base(config=config, force_reindex=False)
    except Exception as err:
        print(f"[Error durante la ingesta vectorial]: {err}")
        return

    # 3. Casos de Prueba (Preguntas Grounded vs. Preguntas Trampa / Anti-Alucinación)
    casos_de_prueba = [
        (
            "Caso 1: Consulta Técnica Grounded (Circuit Breaker & Reintentos)",
            "¿Cuáles son los 3 estados del Circuit Breaker y qué política de reintentos con backoff exponencial se debe aplicar según la norma?",
            True
        ),
        (
            "Caso 2: Consulta Técnica Grounded (Gestión de Incidentes Críticos)",
            "¿Cuál es el tiempo objetivo de respuesta para un incidente SEV-1 y quién debe liderar el postmortem blameless?",
            True
        ),
        (
            "Caso 3: Pregunta Trampa / Fuera de Dominio (Receta Culinaria)",
            "¿Cuál es la receta tradicional para preparar una auténtica salsa pomodoro italiana con albahaca?",
            False
        ),
        (
            "Caso 4: Pregunta Trampa Técnica (Concepto Inexistente / Alucinación Cero)",
            "¿Cómo se configura el driver cuántico Q-Kube v4.9 con aceleradores taquiónicos en el clúster de Kubernetes?",
            False
        )
    ]

    print("\n-----------------------------------------------------------------")
    print("PASO 2: EJECUCIÓN DE CONSULTAS ASÍNCRONAS CON LCEL (.ainvoke)")
    print("-----------------------------------------------------------------\n")

    for i, (titulo, query, esperado_grounded) in enumerate(casos_de_prueba, 1):
        print(f"=================================================================")
        print(f"PRUEBA #{i}: {titulo}")
        print(f"Esperado en contexto: {'SÍ' if esperado_grounded else 'NO (Debe responder No lo sé)'}")
        print(f"Consulta: \"{query}\"")
        print(f"=================================================================")

        start_time = time.time()
        try:
            resultado = await get_rag_response(
                query=query,
                config=config,
                vectorstore=vectorstore
            )
            elapsed = time.time() - start_time

            print(f"\n[TIEMPO DE RESPUESTA: {elapsed:.2f}s]")
            print("\nSalida Pydantic Validada (JSON):")
            print(json.dumps(resultado.model_dump(), indent=2, ensure_ascii=False))

            # Verificación del comportamiento del filtro de veracidad
            if esperado_grounded and resultado.encontrado_en_contexto:
                print("\nRESULTADO CORRECTO: Información extraída con éxito de las fuentes documentales.")
            elif not esperado_grounded and not resultado.encontrado_en_contexto:
                print("\nRESULTADO CORRECTO: Filtro Anti-Alucinación activado exitosamente. El modelo no inventó datos.")
            else:
                print(f"\nATENCIÓN: El resultado difiere de la expectativa teórica (Encontrado: {resultado.encontrado_en_contexto}).")

            print("-----------------------------------------------------------------\n")

        except Exception as err:
            print(f"[Error en la ejecución del caso #{i}]: {err}\n")

    print("=================================================================")
    print("  SUITE AUTOMATIZADA FORMAL DISPONIBLE CON PYTEST")
    print("  Para ejecutar todos los tests unitarios y de integración:")
    print("  pytest tests/test_rag.py -v")
    print("=================================================================\n")


if __name__ == "__main__":
    asyncio.run(main())
