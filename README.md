# AI Personal Health Companion

¡Bienvenido al AI Personal Health Companion! Una solución integral de salud personalizada que utiliza inteligencia artificial para analizar fotos de comida y documentos médicos, generando recomendaciones personalizadas y proporcionando seguimiento a largo plazo.

## 🎯 Características Principales

### 📸 Análisis Inteligente de Alimentos
- Subida de imágenes desde aplicación web o móvil
- Procesamiento con Azure AI Vision para extracción de texto y clasificación
- Análisis nutricional automatizado con Azure OpenAI

### 🏥 Procesamiento de Documentos Médicos
- Análisis de estudios médicos y resultados de laboratorio
- Extracción inteligente de información clave
- Recomendaciones basadas en hallazgos médicos

### 💾 Almacenamiento Seguro
- Azure Cosmos DB para historial de comidas, estudios y recomendaciones
- Azure Blob Storage para almacenamiento seguro de imágenes
- Cumplimiento con estándares de privacidad médica

### 🤖 Agentes Conversacionales M365
- **Health Analyst Agent**: Análisis de datos de salud y tendencias
- **Health Researcher Agent**: Información basada en evidencia científica
- **Health Coach Agent**: Motivación y establecimiento de objetivos

### 🔄 Automatización Inteligente
- Azure Logic Apps para análisis automático y notificaciones
- Procesamiento en segundo plano para insights diarios
- Pipelines de CI/CD con Azure DevOps

### 🔒 Seguridad Empresarial
- Azure Key Vault para gestión segura de secretos
- Workload Identity para autenticación sin contraseñas
- Encriptación de datos en tránsito y reposo

## 🏗️ Arquitectura

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Frontend  │    │   API Backend   │    │   Processor     │
│   (Streamlit)   │────│   (FastAPI)     │────│   (Background)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Azure AI      │    │   Cosmos DB     │    │   Blob Storage  │
│   Services      │    │   (Database)    │    │   (Images)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Logic Apps    │    │   Key Vault     │    │   M365 Copilot  │
│   (Workflows)   │    │   (Secrets)     │    │   (Agents)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🚀 Inicio Rápido

### Prerrequisitos

- Azure CLI
- Azure Developer CLI (azd)
- PowerShell 7.0+
- Suscripción de Azure con permisos de contribuidor
- Cuenta de Azure OpenAI

### Despliegue Automático

1. **Clona el repositorio**
   ```powershell
   git clone https://github.com/artmej/ai-personal-health-companion.git
   cd ai-personal-health-companion
   ```

2. **Ejecuta el script de despliegue**
   ```powershell
   .\deploy.ps1 -EnvironmentName "mi-health-companion" -Location "eastus"
   ```

3. **Configura la clave de OpenAI**
   ```bash
   az keyvault secret set --vault-name "tu-keyvault" --name "openai-api-key" --value "tu-clave-openai"
   ```

4. **Accede a la aplicación**
   - Aplicación Web: `https://tu-app-web.azurecontainerapps.io`
   - API: `https://tu-api.azurecontainerapps.io`

### Despliegue Manual

Si prefieres un control más granular:

```bash
# Inicializar el proyecto
azd init --environment phealth-companion

# Provisionar infraestructura
azd provision

# Desplegar aplicaciones
azd deploy
```

## 📱 Uso de la Aplicación

### 1. Análisis de Alimentos
1. Accede a la sección "📸 Análisis de Comida"
2. Sube una foto clara de tu comida
3. Agrega notas opcionales sobre la comida
4. Obtén análisis nutricional y recomendaciones instantáneas

### 2. Documentos Médicos
1. Ve a "📋 Análisis Médico"
2. Selecciona el tipo de documento
3. Sube tu estudio médico o resultado de laboratorio
4. Recibe interpretación y recomendaciones de seguimiento

### 3. Recomendaciones Personalizadas
1. Visita "💡 Recomendaciones"
2. Proporciona contexto adicional si es necesario
3. Obtén consejos personalizados basados en tu historial

### 4. Historial de Salud
1. Explora "📊 Historial" para ver tu progreso
2. Revisa tendencias y patrones en tus datos
3. Exporta reportes para compartir con tu médico

## 🤖 Agentes M365 Copilot

### Configuración de Agentes

1. **Sube las configuraciones de agentes**
   - Navega a M365 Admin Center
   - Importa los archivos JSON desde la carpeta `agents/`

2. **Configura endpoints de API**
   - Health Analyst Agent: `https://tu-api.azurecontainerapps.io/api`
   - Configura autenticación con Managed Identity

3. **Comandos de ejemplo**
   ```
   @HealthAnalyst analiza mi ingesta de alimentos de la última semana
   @HealthResearcher qué dice la ciencia sobre el ayuno intermitente
   @HealthCoach ayúdame a crear un plan de alimentación saludable
   ```

## 🔄 Workflows y Automatización

### Logic Apps Incluidas

1. **food-analysis-automation.json**
   - Se activa cuando se sube una nueva imagen
   - Procesa automáticamente la imagen
   - Envía notificaciones si hay alertas de salud

2. **daily-health-insights.json**
   - Ejecuta diariamente a las 8:00 AM UTC
   - Genera insights personalizados para cada usuario
   - Envía resúmenes por email

### Personalización de Workflows

Puedes modificar los workflows para:
- Cambiar horarios de ejecución
- Agregar nuevos tipos de notificaciones
- Integrar con otros servicios de Microsoft 365
- Crear flujos personalizados para casos específicos

## 🔒 Seguridad y Cumplimiento

### Características de Seguridad

- **Managed Identity**: Autenticación sin contraseñas entre servicios
- **Key Vault**: Gestión centralizada de secretos y claves
- **RBAC**: Control de acceso basado en roles
- **Encriptación**: Datos encriptados en tránsito y reposo
- **Auditoría**: Logging completo de todas las operaciones

### Cumplimiento

- **HIPAA**: Configuración compatible con HIPAA
- **GDPR**: Cumple con regulaciones de privacidad europeas
- **Azure Security**: Implementa mejores prácticas de seguridad de Azure

## 🛠️ Desarrollo y Personalización

### Estructura del Proyecto

```
PHealthCompa/
├── src/
│   ├── api/           # Backend API (FastAPI)
│   ├── web/           # Frontend web (Streamlit)
│   └── processor/     # Procesamiento en segundo plano
├── infra/             # Infraestructura como código (Bicep)
├── agents/            # Configuraciones de agentes M365
├── workflows/         # Logic Apps workflows
└── deploy.ps1         # Script de despliegue
```

### Configuración de Desarrollo

1. **Configura el entorno local**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # o
   venv\Scripts\Activate.ps1  # Windows
   ```

2. **Instala dependencias**
   ```bash
   cd src/api && pip install -r requirements.txt
   cd ../web && pip install -r requirements.txt
   cd ../processor && pip install -r requirements.txt
   ```

3. **Configura variables de entorno**
   ```bash
   export AZURE_OPENAI_ENDPOINT="tu-endpoint"
   export COSMOS_DB_ENDPOINT="tu-cosmos-endpoint"
   export STORAGE_ACCOUNT_ENDPOINT="tu-storage-endpoint"
   export KEY_VAULT_URL="tu-keyvault-url"
   ```

### Personalización

#### Agregar Nuevos Tipos de Análisis

1. Modifica `src/api/main.py` para agregar nuevos endpoints
2. Actualiza `src/web/app.py` para la interfaz de usuario
3. Extiende `src/processor/processor.py` para procesamiento automático

#### Crear Nuevos Agentes

1. Crea un nuevo archivo JSON en `agents/`
2. Define las capacidades y acciones del agente
3. Configura los endpoints de API correspondientes

#### Personalizar Workflows

1. Modifica los archivos JSON en `workflows/`
2. Ajusta triggers, acciones y condiciones
3. Redespliega usando el script de despliegue

## 📊 Monitoreo y Observabilidad

### Application Insights

- **Métricas**: Rendimiento de API, tiempo de respuesta, errores
- **Logs**: Logs estructurados de todas las operaciones
- **Alertas**: Configuración automática de alertas para errores críticos

### Dashboards

- **Azure Monitor**: Métricas de infraestructura y aplicación
- **Cosmos DB Insights**: Rendimiento de base de datos
- **Storage Analytics**: Uso y rendimiento de almacenamiento

## 🤝 Contribuir

¡Las contribuciones son bienvenidas! Por favor:

1. Fork el repositorio
2. Crea una rama para tu feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit tus cambios (`git commit -m 'Agregar nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Abre un Pull Request

## 📝 Licencia

Este proyecto está licenciado bajo la Licencia MIT - ve el archivo [LICENSE](LICENSE) para detalles.

## 📞 Soporte

- **Issues**: [GitHub Issues](https://github.com/artmej/ai-personal-health-companion/issues)
- **Documentación**: [Wiki del Proyecto](https://github.com/artmej/ai-personal-health-companion/wiki)
- **Email**: soporte@phealth-companion.com

## 🙏 Agradecimientos

- Azure AI Services por las capacidades de procesamiento inteligente
- Microsoft 365 Copilot por la plataforma de agentes conversacionales
- OpenAI por los modelos de lenguaje avanzados
- La comunidad de código abierto por las herramientas y bibliotecas utilizadas

---

**⚠️ Descargo de Responsabilidad**: Esta aplicación es solo para fines informativos y educativos. No reemplaza el consejo médico profesional, diagnóstico o tratamiento. Siempre consulta con profesionales de la salud calificados para decisiones médicas importantes.
