# Manual de Arquitectura de Microservicios y Comunicación Inter-Servicios

## 1. Principios Fundamentales del Ecosistema

La arquitectura orientada a microservicios adoptada por la organización se basa en el principio de responsabilidad única (*Single Responsibility Principle*) y el desacoplamiento de dominios delimitados (*Bounded Contexts*). Cada servicio es propietario exclusivo de su esquema de base de datos y no se permite el acceso directo entre bases de datos de diferentes microservicios (patrón *Database-per-Service*).

Toda comunicación externa hacia los microservicios debe pasar obligatoriamente a través del **API Gateway Central (Kong / Envoy)**. El API Gateway es responsable de la terminación TLS, la autenticación mediante tokens JWT, la limitación de tasa (*Rate Limiting*) configurada a un máximo de 1000 solicitudes por segundo por cliente, y el enrutamiento dinámico hacia los servicios aguas abajo.

## 2. Protocolos de Comunicación: Síncrona vs. Asíncrona

### 2.1 Comunicación Síncrona (gRPC y REST)
- **gRPC sobre HTTP/2**: Es el estándar obligatorio para toda la comunicación punto a punto entre microservicios dentro del clúster privado. Los contratos se definen estrictamente mediante archivos `.proto` versionados en un repositorio central de esquemas. El uso de buffers de protocolo (Protobuf) reduce la sobrecarga de serialización en un 60% comparado con JSON.
- **REST / JSON sobre HTTP/1.1**: Se reserva exclusivamente para APIs públicas orientadas a clientes web y aplicaciones móviles a través del API Gateway.

### 2.2 Comunicación Asíncrona y Event-Driven (Apache Kafka)
Para desacoplar flujos de trabajo de larga duración o difusión de eventos de dominio, se utiliza un clúster de **Apache Kafka**. 
- Todo evento publicado debe seguir el formato estándar CloudEvents v1.0.
- El tiempo de retención mínimo en los tópicos transaccionales es de 7 días.
- Se implementa el patrón **Transactional Outbox** junto con Debezium (CDC) en los servicios emisores para garantizar consistencia eventual sin requerir transacciones distribuidas 2PC (Two-Phase Commit).

## 3. Descubrimiento de Servicios y Service Mesh (Istio)

Dentro del clúster de Kubernetes, el descubrimiento de servicios y la observabilidad de red se gestionan mediante **Istio Service Mesh**. 
- Cada Pod inyecta automáticamente un proxy sidecar Envoy.
- Se impone la política de **mTLS estricto (Mutual TLS)** en todo el tráfico este-oeste (entre pods), garantizando cifrado en tránsito con certificados rotados cada 24 horas por Citadel.
- Los timeouts por defecto para llamadas gRPC inter-servicios se establecen en **2500 milisegundos**, con un límite estricto de desconexión si no se recibe respuesta de cabeceras.
