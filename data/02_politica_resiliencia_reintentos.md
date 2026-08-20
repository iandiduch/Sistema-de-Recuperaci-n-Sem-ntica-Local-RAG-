# Norma de Resiliencia, Circuit Breakers y Políticas de Reintento

## 1. Arquitectura de Resiliencia de Sistemas Distribuidos

En un sistema distribuido de alta concurrencia, las fallas transitorias de red o la sobrecarga de servicios dependientes son inevitables. Para evitar fallas en cascada y la saturación de los recursos de cómputo (hilos de ejecución, conexiones de socket y memoria), todo microservicio cliente debe incorporar patrones de diseño de resiliencia obligatorios.

## 2. Implementación del Patrón Circuit Breaker

El Circuit Breaker previene que un servicio siga realizando llamadas remotas a una dependencia que está degradada o inactiva. Funciona como una máquina de estados finita con tres estados:

1. **Estado Cerrado (Closed)**: 
   - Las solicitudes fluyen normalmente hacia el servicio aguas abajo.
   - Si la tasa de errores (respuestas 5xx o timeouts) supera el **50% en una ventana deslizante de 20 solicitudes**, el circuito cambia automáticamente al estado **Abierto (Open)**.
2. **Estado Abierto (Open)**:
   - Todas las llamadas entrantes son rechazadas de inmediato mediante un error de tipo *Fast-Fail* (HTTP 503 o excepción gRPC Unavailable) sin saturar la red.
   - El circuito permanece en estado Abierto durante un período de enfriamiento obligatorio de **30 segundos** (*Sleep Window*).
3. **Estado Semi-Abierto (Half-Open)**:
   - Transcurridos los 30 segundos, el circuito permite el paso de una cantidad limitada de solicitudes de sondeo (máximo 5 solicitudes concurrentes).
   - Si todas las solicitudes de prueba resultan exitosas, el circuito se restablece a **Cerrado**. Si al menos una falla, vuelve a **Abierto** por otros 30 segundos.

## 3. Políticas de Reintentos con Backoff Exponencial y Jitter

No todas las fallas deben reintentarse. Los reintentos sin control causan el fenómeno de la "tormenta de reintentos" (*Retry Storm*), que termina por derribar definitivamente a un servicio en recuperación.

### Reglas Estrictas de Reintento:
- **Operaciones Idempotentes Únicamente**: Solo está permitido reintentar llamadas de lectura (HTTP GET / consultas gRPC de solo lectura) o mutaciones que incluyan un encabezado de idempotencia único `X-Idempotency-Key` (UUIDv4).
- **Límite Máximo de Intentos**: El número máximo de reintentos permitidos es de **3 intentos adicionales** (4 intentos en total).
- **Algoritmo de Backoff Exponencial**:
  $$\text{Intervalo}(n) = \text{Min}(\text{Intervalo\_Maximo}, \text{Intervalo\_Base} \times 2^n) + \text{Jitter}$$
  - $\text{Intervalo\_Base} = 100\text{ ms}$
  - $\text{Intervalo\_Maximo} = 3000\text{ ms}$
  - **Full Jitter**: Se debe añadir una variación aleatoria entre 0 y el valor calculado del intervalo para desincronizar los reintentos de múltiples clientes.
- **Códigos de Error Reintentables**: Únicamente los códigos HTTP 429 (Too Many Requests con respeto del header Retry-After), HTTP 502, 503, 504 y errores de timeout de conexión. Queda terminantemente prohibido reintentar códigos 400, 401, 403 o 404.
