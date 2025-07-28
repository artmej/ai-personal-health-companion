# AI Personal Health Companion - API Service
# FastAPI backend for processing food images and medical documents

from fastapi import FastAPI, HTTPException, UploadFile, File, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional
import os
import logging
from datetime import datetime
import asyncio

# Azure SDK imports
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from azure.cosmos import CosmosClient
from azure.keyvault.secrets import SecretClient
from azure.ai.vision.imageanalysis import ImageAnalysisClient
from azure.ai.vision.imageanalysis.models import VisualFeatures
from azure.core.credentials import AzureKeyCredential
from openai import AzureOpenAI

# Application insights
from opencensus.ext.azure.log_exporter import AzureLogHandler
from opencensus.ext.azure import trace_exporter
from opencensus.trace.tracer import Tracer
from opencensus.trace.samplers import ProbabilitySampler

# Configuration
app = FastAPI(
    title="AI Personal Health Companion API",
    description="Backend API for analyzing food images and medical documents",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# Environment variables
AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
COSMOS_DB_ENDPOINT = os.getenv("COSMOS_DB_ENDPOINT")
STORAGE_ACCOUNT_ENDPOINT = os.getenv("STORAGE_ACCOUNT_ENDPOINT")
KEY_VAULT_URL = os.getenv("KEY_VAULT_URL")
APPLICATIONINSIGHTS_CONNECTION_STRING = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")

# Initialize Azure services with Managed Identity
credential = DefaultAzureCredential(managed_identity_client_id=AZURE_CLIENT_ID)

# Initialize clients
blob_service_client = BlobServiceClient(
    account_url=STORAGE_ACCOUNT_ENDPOINT,
    credential=credential
)

cosmos_client = CosmosClient(
    url=COSMOS_DB_ENDPOINT,
    credential=credential
)

keyvault_client = SecretClient(
    vault_url=KEY_VAULT_URL,
    credential=credential
)

# Initialize AI clients (will be set up in startup)
openai_client = None
vision_client = None

# Logging configuration
if APPLICATIONINSIGHTS_CONNECTION_STRING:
    logger = logging.getLogger(__name__)
    logger.addHandler(AzureLogHandler(
        connection_string=APPLICATIONINSIGHTS_CONNECTION_STRING
    ))
    logger.setLevel(logging.INFO)
    
    # Initialize tracer
    tracer = Tracer(
        exporter=trace_exporter.AzureExporter(
            connection_string=APPLICATIONINSIGHTS_CONNECTION_STRING
        ),
        sampler=ProbabilitySampler(1.0)
    )
else:
    logger = logging.getLogger(__name__)
    tracer = None

# Pydantic models
class FoodAnalysisRequest(BaseModel):
    user_id: str
    image_url: Optional[str] = None
    notes: Optional[str] = None

class FoodAnalysisResponse(BaseModel):
    analysis_id: str
    food_items: List[dict]
    nutrition_info: dict
    recommendations: List[str]
    timestamp: datetime

class MedicalDocumentRequest(BaseModel):
    user_id: str
    document_url: str
    document_type: str

class MedicalDocumentResponse(BaseModel):
    document_id: str
    extracted_text: str
    key_findings: List[str]
    recommendations: List[str]
    timestamp: datetime

class HealthRecommendationRequest(BaseModel):
    user_id: str
    context: Optional[str] = None

class HealthRecommendationResponse(BaseModel):
    recommendations: List[str]
    rationale: str
    timestamp: datetime

# Database references
database = cosmos_client.get_database_client("HealthCompanion")
food_container = database.get_container_client("FoodHistory")
medical_container = database.get_container_client("MedicalRecords")
recommendations_container = database.get_container_client("Recommendations")

@app.on_event("startup")
async def startup_event():
    """Initialize AI services on startup"""
    global openai_client, vision_client
    
    try:
        # Get OpenAI API key from Key Vault
        openai_key_secret = await asyncio.to_thread(
            keyvault_client.get_secret, "openai-api-key"
        )
        
        # Initialize OpenAI client
        openai_client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=openai_key_secret.value,
            api_version="2024-02-01"
        )
        
        # Initialize Vision client
        vision_client = ImageAnalysisClient(
            endpoint=AZURE_OPENAI_ENDPOINT,
            credential=AzureKeyCredential(openai_key_secret.value)
        )
        
        logger.info("AI services initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize AI services: {str(e)}")
        raise

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Extract user information from JWT token"""
    # In production, implement proper JWT validation
    # For now, return a mock user
    return {"user_id": "user123", "email": "user@example.com"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow()}

@app.post("/api/analyze-food", response_model=FoodAnalysisResponse)
async def analyze_food_image(
    file: UploadFile = File(...),
    notes: str = "",
    current_user: dict = Depends(get_current_user)
):
    """Analyze uploaded food image and provide nutritional insights"""
    try:
        # Upload image to blob storage
        blob_name = f"food-images/{current_user['user_id']}/{datetime.utcnow().isoformat()}-{file.filename}"
        blob_client = blob_service_client.get_blob_client(
            container="food-images",
            blob=blob_name
        )
        
        # Upload file
        file_content = await file.read()
        blob_client.upload_blob(file_content, overwrite=True)
        image_url = blob_client.url
        
        # Analyze image with Azure AI Vision
        vision_result = vision_client.analyze(
            image_data=file_content,
            visual_features=[VisualFeatures.OBJECTS, VisualFeatures.TAGS, VisualFeatures.CAPTION]
        )
        
        # Generate nutritional analysis with OpenAI
        analysis_prompt = f"""
        Analyze this food image and provide:
        1. Identified food items
        2. Estimated nutritional information (calories, macros)
        3. Health recommendations
        
        Vision analysis results:
        Caption: {vision_result.caption.text if vision_result.caption else 'N/A'}
        Objects: {[obj.tags[0].name for obj in vision_result.objects] if vision_result.objects else []}
        Tags: {[tag.name for tag in vision_result.tags[:10]] if vision_result.tags else []}
        
        Additional notes: {notes}
        
        Provide response in JSON format with keys: food_items, nutrition_info, recommendations
        """
        
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a nutritionist AI assistant."},
                {"role": "user", "content": analysis_prompt}
            ],
            temperature=0.3
        )
        
        # Parse AI response (implement proper JSON parsing)
        ai_analysis = eval(response.choices[0].message.content)  # Use json.loads in production
        
        # Save to Cosmos DB
        analysis_record = {
            "id": f"{current_user['user_id']}-{datetime.utcnow().timestamp()}",
            "userId": current_user['user_id'],
            "imageUrl": image_url,
            "notes": notes,
            "foodItems": ai_analysis.get("food_items", []),
            "nutritionInfo": ai_analysis.get("nutrition_info", {}),
            "recommendations": ai_analysis.get("recommendations", []),
            "timestamp": datetime.utcnow().isoformat(),
            "type": "food_analysis"
        }
        
        food_container.create_item(analysis_record)
        
        logger.info(f"Food analysis completed for user {current_user['user_id']}")
        
        return FoodAnalysisResponse(
            analysis_id=analysis_record["id"],
            food_items=ai_analysis.get("food_items", []),
            nutrition_info=ai_analysis.get("nutrition_info", {}),
            recommendations=ai_analysis.get("recommendations", []),
            timestamp=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Food analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.post("/api/analyze-medical-document", response_model=MedicalDocumentResponse)
async def analyze_medical_document(
    file: UploadFile = File(...),
    document_type: str = "general",
    current_user: dict = Depends(get_current_user)
):
    """Analyze uploaded medical document and extract key information"""
    try:
        # Upload document to blob storage
        blob_name = f"medical-documents/{current_user['user_id']}/{datetime.utcnow().isoformat()}-{file.filename}"
        blob_client = blob_service_client.get_blob_client(
            container="medical-documents",
            blob=blob_name
        )
        
        # Upload file
        file_content = await file.read()
        blob_client.upload_blob(file_content, overwrite=True)
        document_url = blob_client.url
        
        # Extract text with Azure AI Vision (OCR)
        vision_result = vision_client.analyze(
            image_data=file_content,
            visual_features=[VisualFeatures.READ]
        )
        
        extracted_text = ""
        if vision_result.read:
            for page in vision_result.read.blocks:
                for line in page.lines:
                    extracted_text += line.text + "\n"
        
        # Analyze medical content with OpenAI
        analysis_prompt = f"""
        Analyze this medical document and provide:
        1. Key medical findings
        2. Health recommendations based on the findings
        3. Important values or metrics mentioned
        
        Document type: {document_type}
        Extracted text:
        {extracted_text}
        
        Provide response in JSON format with keys: key_findings, recommendations, important_metrics
        """
        
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a medical AI assistant. Provide analysis for informational purposes only."},
                {"role": "user", "content": analysis_prompt}
            ],
            temperature=0.2
        )
        
        # Parse AI response
        ai_analysis = eval(response.choices[0].message.content)  # Use json.loads in production
        
        # Save to Cosmos DB
        document_record = {
            "id": f"{current_user['user_id']}-doc-{datetime.utcnow().timestamp()}",
            "userId": current_user['user_id'],
            "documentUrl": document_url,
            "documentType": document_type,
            "extractedText": extracted_text,
            "keyFindings": ai_analysis.get("key_findings", []),
            "recommendations": ai_analysis.get("recommendations", []),
            "importantMetrics": ai_analysis.get("important_metrics", {}),
            "timestamp": datetime.utcnow().isoformat(),
            "type": "medical_document"
        }
        
        medical_container.create_item(document_record)
        
        logger.info(f"Medical document analysis completed for user {current_user['user_id']}")
        
        return MedicalDocumentResponse(
            document_id=document_record["id"],
            extracted_text=extracted_text,
            key_findings=ai_analysis.get("key_findings", []),
            recommendations=ai_analysis.get("recommendations", []),
            timestamp=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Medical document analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.post("/api/get-recommendations", response_model=HealthRecommendationResponse)
async def get_health_recommendations(
    request: HealthRecommendationRequest,
    current_user: dict = Depends(get_current_user)
):
    """Generate personalized health recommendations based on user history"""
    try:
        # Query user's food history
        food_history = list(food_container.query_items(
            query="SELECT * FROM c WHERE c.userId = @userId ORDER BY c.timestamp DESC OFFSET 0 LIMIT 10",
            parameters=[{"name": "@userId", "value": current_user['user_id']}],
            enable_cross_partition_query=True
        ))
        
        # Query user's medical records
        medical_history = list(medical_container.query_items(
            query="SELECT * FROM c WHERE c.userId = @userId ORDER BY c.timestamp DESC OFFSET 0 LIMIT 5",
            parameters=[{"name": "@userId", "value": current_user['user_id']}],
            enable_cross_partition_query=True
        ))
        
        # Generate personalized recommendations
        context_prompt = f"""
        Generate personalized health recommendations for this user based on their history:
        
        Recent Food History:
        {food_history[:5]}  # Last 5 food analyses
        
        Medical History:
        {medical_history[:3]}  # Last 3 medical documents
        
        Additional Context: {request.context or 'General health recommendations'}
        
        Provide specific, actionable recommendations with rationale.
        Response format: {{"recommendations": ["rec1", "rec2", ...], "rationale": "explanation"}}
        """
        
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a personalized health AI assistant."},
                {"role": "user", "content": context_prompt}
            ],
            temperature=0.4
        )
        
        # Parse AI response
        ai_recommendations = eval(response.choices[0].message.content)  # Use json.loads in production
        
        # Save recommendations
        recommendation_record = {
            "id": f"{current_user['user_id']}-rec-{datetime.utcnow().timestamp()}",
            "userId": current_user['user_id'],
            "recommendations": ai_recommendations.get("recommendations", []),
            "rationale": ai_recommendations.get("rationale", ""),
            "context": request.context,
            "timestamp": datetime.utcnow().isoformat(),
            "type": "health_recommendations"
        }
        
        recommendations_container.create_item(recommendation_record)
        
        logger.info(f"Health recommendations generated for user {current_user['user_id']}")
        
        return HealthRecommendationResponse(
            recommendations=ai_recommendations.get("recommendations", []),
            rationale=ai_recommendations.get("rationale", ""),
            timestamp=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Recommendation generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Recommendation generation failed: {str(e)}")

@app.get("/api/user-history")
async def get_user_history(
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """Get user's complete health history"""
    try:
        # Get food history
        food_history = list(food_container.query_items(
            query="SELECT * FROM c WHERE c.userId = @userId ORDER BY c.timestamp DESC OFFSET 0 LIMIT @limit",
            parameters=[
                {"name": "@userId", "value": current_user['user_id']},
                {"name": "@limit", "value": limit}
            ],
            enable_cross_partition_query=True
        ))
        
        # Get medical history
        medical_history = list(medical_container.query_items(
            query="SELECT * FROM c WHERE c.userId = @userId ORDER BY c.timestamp DESC OFFSET 0 LIMIT @limit",
            parameters=[
                {"name": "@userId", "value": current_user['user_id']},
                {"name": "@limit", "value": limit}
            ],
            enable_cross_partition_query=True
        ))
        
        # Get recommendations history
        recommendations_history = list(recommendations_container.query_items(
            query="SELECT * FROM c WHERE c.userId = @userId ORDER BY c.timestamp DESC OFFSET 0 LIMIT @limit",
            parameters=[
                {"name": "@userId", "value": current_user['user_id']},
                {"name": "@limit", "value": limit}
            ],
            enable_cross_partition_query=True
        ))
        
        return {
            "food_history": food_history,
            "medical_history": medical_history,
            "recommendations_history": recommendations_history
        }
        
    except Exception as e:
        logger.error(f"History retrieval failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"History retrieval failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
