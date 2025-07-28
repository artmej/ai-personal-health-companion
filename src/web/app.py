# AI Personal Health Companion - Web Frontend
# Streamlit web application for user interface

import streamlit as st
import requests
import os
from datetime import datetime
import pandas as pd
from PIL import Image
import io
import json
import base64

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
APPLICATIONINSIGHTS_CONNECTION_STRING = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")

# Page configuration
st.set_page_config(
    page_title="AI Personal Health Companion",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .upload-section {
        border: 2px dashed #cccccc;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
        margin: 20px 0;
    }
    .analysis-result {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 20px;
        margin: 20px 0;
    }
    .recommendation-card {
        background-color: #e8f4fd;
        border-left: 4px solid #1f77b4;
        border-radius: 5px;
        padding: 15px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# Helper functions
def call_api(endpoint, method="GET", data=None, files=None):
    """Make API calls with error handling"""
    try:
        url = f"{API_BASE_URL}{endpoint}"
        headers = {"Authorization": f"Bearer {st.session_state.get('auth_token', 'mock-token')}"}
        
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            if files:
                response = requests.post(url, headers=headers, data=data, files=files)
            else:
                headers["Content-Type"] = "application/json"
                response = requests.post(url, headers=headers, json=data)
        
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API Error: {str(e)}")
        return None

def display_food_analysis_results(results):
    """Display food analysis results in a formatted way"""
    if not results:
        return
    
    st.markdown("### 🍽️ Análisis de Alimentos")
    
    # Food items
    if results.get('food_items'):
        st.markdown("#### Alimentos Identificados:")
        for item in results['food_items']:
            st.markdown(f"- **{item.get('name', 'Unknown')}**: {item.get('description', 'N/A')}")
    
    # Nutrition info
    if results.get('nutrition_info'):
        st.markdown("#### Información Nutricional:")
        nutrition = results['nutrition_info']
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Calorías", nutrition.get('calories', 'N/A'))
        with col2:
            st.metric("Proteínas (g)", nutrition.get('protein', 'N/A'))
        with col3:
            st.metric("Carbohidratos (g)", nutrition.get('carbs', 'N/A'))
        with col4:
            st.metric("Grasas (g)", nutrition.get('fat', 'N/A'))
    
    # Recommendations
    if results.get('recommendations'):
        st.markdown("#### Recomendaciones:")
        for rec in results['recommendations']:
            st.markdown(f'<div class="recommendation-card">💡 {rec}</div>', unsafe_allow_html=True)

def display_medical_analysis_results(results):
    """Display medical document analysis results"""
    if not results:
        return
    
    st.markdown("### 📋 Análisis de Documento Médico")
    
    # Key findings
    if results.get('key_findings'):
        st.markdown("#### Hallazgos Principales:")
        for finding in results['key_findings']:
            st.markdown(f"- {finding}")
    
    # Recommendations
    if results.get('recommendations'):
        st.markdown("#### Recomendaciones Médicas:")
        for rec in results['recommendations']:
            st.markdown(f'<div class="recommendation-card">🏥 {rec}</div>', unsafe_allow_html=True)
    
    # Extracted text (expandable)
    if results.get('extracted_text'):
        with st.expander("Ver Texto Extraído"):
            st.text_area("Texto del documento:", results['extracted_text'], height=200, disabled=True)

# Main application
def main():
    # Header
    st.markdown('<h1 class="main-header">🏥 AI Personal Health Companion</h1>', unsafe_allow_html=True)
    
    # Initialize session state
    if 'user_history' not in st.session_state:
        st.session_state.user_history = []
    
    # Sidebar navigation
    with st.sidebar:
        st.markdown("### 🎯 Navegación")
        page = st.selectbox(
            "Selecciona una opción:",
            ["📸 Análisis de Comida", "📋 Análisis Médico", "💡 Recomendaciones", "📊 Historial", "⚙️ Configuración"]
        )
        
        st.markdown("---")
        st.markdown("### 👤 Usuario")
        st.write("Usuario: Demo User")
        st.write("Estado: Conectado")
    
    # Main content based on selected page
    if page == "📸 Análisis de Comida":
        food_analysis_page()
    elif page == "📋 Análisis Médico":
        medical_analysis_page()
    elif page == "💡 Recomendaciones":
        recommendations_page()
    elif page == "📊 Historial":
        history_page()
    elif page == "⚙️ Configuración":
        settings_page()

def food_analysis_page():
    """Food analysis page"""
    st.markdown("## 📸 Análisis de Alimentos")
    st.markdown("Sube una foto de tu comida para obtener análisis nutricional y recomendaciones personalizadas.")
    
    # File upload section
    st.markdown('<div class="upload-section">', unsafe_allow_html=True)
    uploaded_file = st.file_uploader(
        "Selecciona una imagen de comida",
        type=['png', 'jpg', 'jpeg'],
        help="Sube una foto clara de tu comida para mejores resultados"
    )
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Notes section
    notes = st.text_area(
        "Notas adicionales (opcional)",
        placeholder="Ej: Desayuno, almuerzo, cena, ingredientes especiales, etc.",
        height=100
    )
    
    if uploaded_file is not None:
        # Display uploaded image
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Vista Previa")
            image = Image.open(uploaded_file)
            st.image(image, caption="Imagen subida", use_column_width=True)
        
        with col2:
            st.markdown("### Análisis")
            if st.button("🔍 Analizar Comida", type="primary"):
                with st.spinner("Analizando imagen..."):
                    # Prepare file for API call
                    uploaded_file.seek(0)
                    files = {"file": (uploaded_file.name, uploaded_file, uploaded_file.type)}
                    data = {"notes": notes}
                    
                    # Call API
                    results = call_api("/api/analyze-food", method="POST", data=data, files=files)
                    
                    if results:
                        st.success("¡Análisis completado!")
                        display_food_analysis_results(results)
                        
                        # Save to session state
                        st.session_state.user_history.append({
                            "type": "food_analysis",
                            "timestamp": datetime.now().isoformat(),
                            "results": results
                        })

def medical_analysis_page():
    """Medical document analysis page"""
    st.markdown("## 📋 Análisis de Documentos Médicos")
    st.markdown("Sube estudios médicos, análisis de laboratorio o recetas para extraer información clave.")
    
    # Document type selection
    doc_type = st.selectbox(
        "Tipo de documento:",
        ["Análisis de Laboratorio", "Receta Médica", "Estudio de Imagen", "Reporte Médico", "Otro"]
    )
    
    # File upload section
    st.markdown('<div class="upload-section">', unsafe_allow_html=True)
    uploaded_file = st.file_uploader(
        "Selecciona un documento médico",
        type=['png', 'jpg', 'jpeg', 'pdf'],
        help="Formatos soportados: PNG, JPG, JPEG, PDF"
    )
    st.markdown('</div>', unsafe_allow_html=True)
    
    if uploaded_file is not None:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Vista Previa")
            if uploaded_file.type == "application/pdf":
                st.info("📄 Archivo PDF cargado correctamente")
            else:
                image = Image.open(uploaded_file)
                st.image(image, caption="Documento subido", use_column_width=True)
        
        with col2:
            st.markdown("### Análisis")
            if st.button("🔍 Analizar Documento", type="primary"):
                with st.spinner("Procesando documento médico..."):
                    # Prepare file for API call
                    uploaded_file.seek(0)
                    files = {"file": (uploaded_file.name, uploaded_file, uploaded_file.type)}
                    data = {"document_type": doc_type.lower()}
                    
                    # Call API
                    results = call_api("/api/analyze-medical-document", method="POST", data=data, files=files)
                    
                    if results:
                        st.success("¡Análisis completado!")
                        display_medical_analysis_results(results)
                        
                        # Save to session state
                        st.session_state.user_history.append({
                            "type": "medical_analysis",
                            "timestamp": datetime.now().isoformat(),
                            "results": results
                        })

def recommendations_page():
    """Health recommendations page"""
    st.markdown("## 💡 Recomendaciones Personalizadas")
    st.markdown("Obtén recomendaciones de salud basadas en tu historial y contexto actual.")
    
    # Context input
    context = st.text_area(
        "Contexto adicional (opcional)",
        placeholder="Ej: Me siento cansado últimamente, quiero mejorar mi dieta, tengo diabetes, etc.",
        height=100
    )
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        if st.button("🎯 Generar Recomendaciones", type="primary"):
            with st.spinner("Generando recomendaciones personalizadas..."):
                data = {
                    "user_id": "demo_user",
                    "context": context
                }
                
                results = call_api("/api/get-recommendations", method="POST", data=data)
                
                if results:
                    st.session_state.latest_recommendations = results
    
    # Display recommendations
    if hasattr(st.session_state, 'latest_recommendations'):
        results = st.session_state.latest_recommendations
        
        st.markdown("### 🎯 Tus Recomendaciones Personalizadas")
        
        if results.get('recommendations'):
            for i, rec in enumerate(results['recommendations'], 1):
                st.markdown(f'<div class="recommendation-card"><strong>{i}.</strong> {rec}</div>', unsafe_allow_html=True)
        
        if results.get('rationale'):
            with st.expander("Ver Explicación Detallada"):
                st.markdown(results['rationale'])

def history_page():
    """User history page"""
    st.markdown("## 📊 Historial de Salud")
    st.markdown("Revisa tu historial completo de análisis y recomendaciones.")
    
    # Fetch user history from API
    if st.button("🔄 Actualizar Historial"):
        with st.spinner("Cargando historial..."):
            history_data = call_api("/api/user-history")
            if history_data:
                st.session_state.api_history = history_data
    
    # Display tabs for different types of history
    tab1, tab2, tab3 = st.tabs(["🍽️ Comidas", "📋 Documentos Médicos", "💡 Recomendaciones"])
    
    with tab1:
        st.markdown("### Historial de Análisis de Comidas")
        # Display food history from session state or API
        food_history = []
        if hasattr(st.session_state, 'api_history'):
            food_history = st.session_state.api_history.get('food_history', [])
        
        # Also include session history
        session_food = [h for h in st.session_state.user_history if h['type'] == 'food_analysis']
        
        if food_history or session_food:
            for entry in (food_history + session_food):
                with st.expander(f"📸 Análisis - {entry.get('timestamp', 'Unknown time')}"):
                    if 'results' in entry:
                        display_food_analysis_results(entry['results'])
                    else:
                        st.json(entry)
        else:
            st.info("No hay análisis de comida en el historial.")
    
    with tab2:
        st.markdown("### Historial de Documentos Médicos")
        medical_history = []
        if hasattr(st.session_state, 'api_history'):
            medical_history = st.session_state.api_history.get('medical_history', [])
        
        session_medical = [h for h in st.session_state.user_history if h['type'] == 'medical_analysis']
        
        if medical_history or session_medical:
            for entry in (medical_history + session_medical):
                with st.expander(f"📋 Documento - {entry.get('timestamp', 'Unknown time')}"):
                    if 'results' in entry:
                        display_medical_analysis_results(entry['results'])
                    else:
                        st.json(entry)
        else:
            st.info("No hay documentos médicos en el historial.")
    
    with tab3:
        st.markdown("### Historial de Recomendaciones")
        recommendations_history = []
        if hasattr(st.session_state, 'api_history'):
            recommendations_history = st.session_state.api_history.get('recommendations_history', [])
        
        if recommendations_history:
            for entry in recommendations_history:
                with st.expander(f"💡 Recomendaciones - {entry.get('timestamp', 'Unknown time')}"):
                    if entry.get('recommendations'):
                        for rec in entry['recommendations']:
                            st.markdown(f"- {rec}")
                    if entry.get('rationale'):
                        st.markdown(f"**Explicación:** {entry['rationale']}")
        else:
            st.info("No hay recomendaciones en el historial.")

def settings_page():
    """Settings and configuration page"""
    st.markdown("## ⚙️ Configuración")
    
    # API Configuration
    st.markdown("### 🔗 Configuración de API")
    api_url = st.text_input("URL de la API", value=API_BASE_URL)
    
    if st.button("Probar Conexión"):
        try:
            response = requests.get(f"{api_url}/health")
            if response.status_code == 200:
                st.success("✅ Conexión exitosa con la API")
            else:
                st.error("❌ Error de conexión con la API")
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
    
    # User Preferences
    st.markdown("### 👤 Preferencias de Usuario")
    
    col1, col2 = st.columns(2)
    with col1:
        language = st.selectbox("Idioma", ["Español", "English"])
        units = st.selectbox("Unidades", ["Métricas", "Imperiales"])
    
    with col2:
        notifications = st.checkbox("Notificaciones", value=True)
        dark_mode = st.checkbox("Modo Oscuro", value=False)
    
    # Health Profile
    st.markdown("### 🏥 Perfil de Salud")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        age = st.number_input("Edad", min_value=1, max_value=120, value=30)
        weight = st.number_input("Peso (kg)", min_value=1.0, max_value=300.0, value=70.0)
    
    with col2:
        height = st.number_input("Altura (cm)", min_value=50, max_value=250, value=170)
        activity_level = st.selectbox("Nivel de Actividad", 
                                    ["Sedentario", "Ligeramente Activo", "Moderadamente Activo", "Muy Activo"])
    
    with col3:
        dietary_restrictions = st.multiselect("Restricciones Dietéticas",
                                            ["Vegetariano", "Vegano", "Sin Gluten", "Sin Lactosa", "Diabetes", "Hipertensión"])
    
    if st.button("💾 Guardar Configuración"):
        st.success("Configuración guardada correctamente")
    
    # System Information
    st.markdown("### ℹ️ Información del Sistema")
    st.info(f"""
    **Versión de la App:** 1.0.0  
    **API Endpoint:** {API_BASE_URL}  
    **Estado:** Conectado  
    **Última Actualización:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """)

if __name__ == "__main__":
    main()
