# Estándar de Seguridad Corporativa: Gestión de Secretos y Criptografía

## 1. Almacenamiento Centralizado de Credenciales (HashiCorp Vault / AWS Secrets Manager)

Queda estrictamente prohibido el almacenamiento de credenciales en texto plano, contraseñas de bases de datos, llaves de API o certificados en repositorios de código fuente (Git), archivos de configuración estáticos o variables de entorno locales sin cifrar.

- Todos los secretos de aplicación deben residir en **HashiCorp Vault** o **AWS Secrets Manager**.
- Las aplicaciones deben autenticarse ante el almacén de secretos utilizando identidades de servicio de Kubernetes (*IAM Roles for Service Accounts - IRSA* o *Vault Kubernetes Auth Method*).
- Los secretos recuperados se inyectan en memoria del proceso en tiempo de ejecución o mediante volúmenes montados temporales en memoria (`tmpfs`) gestionados por *Secrets Store CSI Driver*.

## 2. Política Obligatoria de Rotación de Credenciales

Para reducir la ventana de exposición ante posibles fugas de información, se establecen los siguientes ciclos de rotación automática obligatoria:

- **Contraseñas de Bases de Datos Relacionales (PostgreSQL / MySQL)**: Rotación automática cada **60 días** mediante credenciales dinámicas de Vault (tiempo de vida TTL de 1 hora para conexiones de mantenimiento).
- **API Keys de Terceros (Stripe, OpenAI, AWS IAM Access Keys)**: Rotación periódica cada **90 días**.
- **Certificados TLS / mTLS de Servidores**: Rotación automatizada cada **24 horas** dentro del Service Mesh y cada **90 días** para certificados públicos emitidos por Let's Encrypt / DigiCert.

## 3. Criptografía y Protección de Datos en Tránsito y en Reposo

- **Cifrado en Reposo (*Encryption at Rest*)**: Todas las bases de datos transaccionales, volúmenes EBS y buckets de almacenamiento S3 deben cifrarse utilizando el estándar **AES-256-GCM** con claves maestras administradas en AWS KMS con rotación anual de clave habilitada.
- **Cifrado en Tránsito (*Encryption in Transit*)**: Todo canal de comunicación sobre redes públicas o entre centros de datos debe exigir **TLS versión 1.3** como estándar mínimo, deshabilitando suites de cifrado obsoletas o con soporte para algoritmos débiles (como SHA-1 o 3DES).
