# AI Personal Health Companion - Background Processor
# Handles batch processing, scheduled tasks, and automated analysis

import asyncio
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
import json

# Azure SDK imports
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from azure.cosmos import CosmosClient
from azure.keyvault.secrets import SecretClient
from azure.ai.vision.imageanalysis import ImageAnalysisClient
from azure.ai.vision.imageanalysis.models import VisualFeatures
from azure.core.credentials import AzureKeyCredential
from openai import AzureOpenAI
from azure.servicebus import ServiceBusClient, ServiceBusMessage

# Application insights
from opencensus.ext.azure.log_exporter import AzureLogHandler
from opencensus.ext.azure import trace_exporter
from opencensus.trace.tracer import Tracer

# Configuration
AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
COSMOS_DB_ENDPOINT = os.getenv("COSMOS_DB_ENDPOINT")
STORAGE_ACCOUNT_ENDPOINT = os.getenv("STORAGE_ACCOUNT_ENDPOINT")
KEY_VAULT_URL = os.getenv("KEY_VAULT_URL")
SERVICE_BUS_CONNECTION_STRING = os.getenv("SERVICE_BUS_CONNECTION_STRING")
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

# Service Bus client for message processing
if SERVICE_BUS_CONNECTION_STRING:
    servicebus_client = ServiceBusClient.from_connection_string(SERVICE_BUS_CONNECTION_STRING)
else:
    servicebus_client = None

# AI clients (will be initialized on startup)
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
        )
    )
else:
    logger = logging.getLogger(__name__)
    tracer = None

# Database references
database = cosmos_client.get_database_client("HealthCompanion")
food_container = database.get_container_client("FoodHistory")
medical_container = database.get_container_client("MedicalRecords")
recommendations_container = database.get_container_client("Recommendations")

class HealthDataProcessor:
    """Main processor class for health data analysis"""
    
    def __init__(self):
        self.running = False
        
    async def initialize(self):
        """Initialize AI services"""
        global openai_client, vision_client
        
        try:
            # Get OpenAI API key from Key Vault
            openai_key_secret = keyvault_client.get_secret("openai-api-key")
            
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
            
            logger.info("Background processor initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize processor: {str(e)}")
            raise
    
    async def start(self):
        """Start the background processor"""
        await self.initialize()
        self.running = True
        logger.info("Background processor started")
        
        # Start background tasks
        tasks = [
            asyncio.create_task(self.process_pending_analyses()),
            asyncio.create_task(self.generate_daily_insights()),
            asyncio.create_task(self.cleanup_old_data()),
            asyncio.create_task(self.health_trend_analysis()),
        ]
        
        if servicebus_client:
            tasks.append(asyncio.create_task(self.process_service_bus_messages()))
        
        await asyncio.gather(*tasks)
    
    async def stop(self):
        """Stop the background processor"""
        self.running = False
        logger.info("Background processor stopped")
    
    async def process_pending_analyses(self):
        """Process any pending food or medical analyses"""
        while self.running:
            try:
                # Query for pending analyses
                pending_food = list(food_container.query_items(
                    query="SELECT * FROM c WHERE c.status = 'pending' ORDER BY c.timestamp ASC",
                    enable_cross_partition_query=True
                ))
                
                pending_medical = list(medical_container.query_items(
                    query="SELECT * FROM c WHERE c.status = 'pending' ORDER BY c.timestamp ASC",
                    enable_cross_partition_query=True
                ))
                
                # Process pending food analyses
                for item in pending_food:
                    await self.process_food_analysis(item)
                
                # Process pending medical analyses
                for item in pending_medical:
                    await self.process_medical_analysis(item)
                
                # Wait before next check
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error in process_pending_analyses: {str(e)}")
                await asyncio.sleep(60)
    
    async def process_food_analysis(self, item: Dict[str, Any]):
        """Process a single food analysis item"""
        try:
            # Download image from blob storage
            blob_client = blob_service_client.get_blob_client(
                container="food-images",
                blob=item.get('imagePath', '')
            )
            
            image_data = blob_client.download_blob().readall()
            
            # Analyze with Vision API
            vision_result = vision_client.analyze(
                image_data=image_data,
                visual_features=[VisualFeatures.OBJECTS, VisualFeatures.TAGS, VisualFeatures.CAPTION]
            )
            
            # Generate nutritional analysis with OpenAI
            analysis_prompt = f"""
            Analyze this food image and provide detailed nutritional information:
            
            Vision analysis:
            Caption: {vision_result.caption.text if vision_result.caption else 'N/A'}
            Objects: {[obj.tags[0].name for obj in vision_result.objects] if vision_result.objects else []}
            Tags: {[tag.name for tag in vision_result.tags[:10]] if vision_result.tags else []}
            
            Provide comprehensive analysis including:
            1. Detailed food identification
            2. Nutritional breakdown (calories, macros, micros)
            3. Health assessment
            4. Personalized recommendations
            
            Format as JSON with keys: food_items, nutrition_info, health_assessment, recommendations
            """
            
            response = openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert nutritionist and health analyst."},
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=0.2
            )
            
            # Parse and update the item
            analysis_result = json.loads(response.choices[0].message.content)
            
            # Update item with analysis results
            item.update({
                'status': 'completed',
                'foodItems': analysis_result.get('food_items', []),
                'nutritionInfo': analysis_result.get('nutrition_info', {}),
                'healthAssessment': analysis_result.get('health_assessment', {}),
                'recommendations': analysis_result.get('recommendations', []),
                'processedAt': datetime.utcnow().isoformat()
            })
            
            # Update in Cosmos DB
            food_container.upsert_item(item)
            
            logger.info(f"Processed food analysis for item {item['id']}")
            
        except Exception as e:
            logger.error(f"Error processing food analysis {item.get('id', 'unknown')}: {str(e)}")
            
            # Mark as failed
            item.update({
                'status': 'failed',
                'error': str(e),
                'processedAt': datetime.utcnow().isoformat()
            })
            food_container.upsert_item(item)
    
    async def process_medical_analysis(self, item: Dict[str, Any]):
        """Process a single medical document analysis"""
        try:
            # Download document from blob storage
            blob_client = blob_service_client.get_blob_client(
                container="medical-documents",
                blob=item.get('documentPath', '')
            )
            
            document_data = blob_client.download_blob().readall()
            
            # Extract text with Vision API (OCR)
            vision_result = vision_client.analyze(
                image_data=document_data,
                visual_features=[VisualFeatures.READ]
            )
            
            extracted_text = ""
            if vision_result.read:
                for page in vision_result.read.blocks:
                    for line in page.lines:
                        extracted_text += line.text + "\n"
            
            # Analyze medical content with OpenAI
            analysis_prompt = f"""
            Analyze this medical document and provide comprehensive medical insights:
            
            Document Type: {item.get('documentType', 'general')}
            Extracted Text:
            {extracted_text}
            
            Provide detailed analysis including:
            1. Key medical findings and abnormalities
            2. Important metrics and values
            3. Risk assessment
            4. Recommended follow-up actions
            5. Lifestyle recommendations
            
            Format as JSON with keys: key_findings, metrics, risk_assessment, follow_up_actions, lifestyle_recommendations
            """
            
            response = openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a medical AI assistant. Provide analysis for informational purposes only."},
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=0.1
            )
            
            # Parse and update the item
            analysis_result = json.loads(response.choices[0].message.content)
            
            # Update item with analysis results
            item.update({
                'status': 'completed',
                'extractedText': extracted_text,
                'keyFindings': analysis_result.get('key_findings', []),
                'metrics': analysis_result.get('metrics', {}),
                'riskAssessment': analysis_result.get('risk_assessment', {}),
                'followUpActions': analysis_result.get('follow_up_actions', []),
                'lifestyleRecommendations': analysis_result.get('lifestyle_recommendations', []),
                'processedAt': datetime.utcnow().isoformat()
            })
            
            # Update in Cosmos DB
            medical_container.upsert_item(item)
            
            logger.info(f"Processed medical analysis for item {item['id']}")
            
        except Exception as e:
            logger.error(f"Error processing medical analysis {item.get('id', 'unknown')}: {str(e)}")
            
            # Mark as failed
            item.update({
                'status': 'failed',
                'error': str(e),
                'processedAt': datetime.utcnow().isoformat()
            })
            medical_container.upsert_item(item)
    
    async def generate_daily_insights(self):
        """Generate daily health insights for all users"""
        while self.running:
            try:
                current_time = datetime.utcnow()
                
                # Run daily at 6 AM UTC
                if current_time.hour == 6 and current_time.minute == 0:
                    logger.info("Starting daily insights generation")
                    
                    # Get unique users from the last 30 days
                    cutoff_date = (current_time - timedelta(days=30)).isoformat()
                    
                    users_query = """
                    SELECT DISTINCT c.userId FROM c 
                    WHERE c.timestamp >= @cutoff_date
                    """
                    
                    users = set()
                    
                    # Get users from food history
                    for item in food_container.query_items(
                        query=users_query,
                        parameters=[{"name": "@cutoff_date", "value": cutoff_date}],
                        enable_cross_partition_query=True
                    ):
                        users.add(item['userId'])
                    
                    # Get users from medical history
                    for item in medical_container.query_items(
                        query=users_query,
                        parameters=[{"name": "@cutoff_date", "value": cutoff_date}],
                        enable_cross_partition_query=True
                    ):
                        users.add(item['userId'])
                    
                    # Generate insights for each user
                    for user_id in users:
                        await self.generate_user_daily_insights(user_id)
                    
                    logger.info(f"Daily insights generated for {len(users)} users")
                
                # Check every minute
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in generate_daily_insights: {str(e)}")
                await asyncio.sleep(60)
    
    async def generate_user_daily_insights(self, user_id: str):
        """Generate daily insights for a specific user"""
        try:
            # Get user's recent data
            recent_cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
            
            # Get recent food history
            recent_food = list(food_container.query_items(
                query="SELECT * FROM c WHERE c.userId = @userId AND c.timestamp >= @cutoff ORDER BY c.timestamp DESC",
                parameters=[
                    {"name": "@userId", "value": user_id},
                    {"name": "@cutoff", "value": recent_cutoff}
                ],
                enable_cross_partition_query=True
            ))
            
            # Get recent medical data
            recent_medical = list(medical_container.query_items(
                query="SELECT * FROM c WHERE c.userId = @userId AND c.timestamp >= @cutoff ORDER BY c.timestamp DESC",
                parameters=[
                    {"name": "@userId", "value": user_id},
                    {"name": "@cutoff", "value": recent_cutoff}
                ],
                enable_cross_partition_query=True
            ))
            
            if not recent_food and not recent_medical:
                return  # No recent data for this user
            
            # Generate comprehensive insights
            insights_prompt = f"""
            Generate comprehensive daily health insights for this user based on their recent activity:
            
            Recent Food History (last 7 days):
            {json.dumps(recent_food[:10], indent=2)}
            
            Recent Medical Data (last 7 days):
            {json.dumps(recent_medical[:5], indent=2)}
            
            Provide insights including:
            1. Nutritional trends and patterns
            2. Health improvements or concerns
            3. Personalized recommendations for today
            4. Long-term health goals suggestions
            5. Risk factors and preventive measures
            
            Format as JSON with keys: nutritional_trends, health_status, daily_recommendations, long_term_goals, risk_factors
            """
            
            response = openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a comprehensive health AI analyst providing personalized insights."},
                    {"role": "user", "content": insights_prompt}
                ],
                temperature=0.3
            )
            
            # Parse insights
            daily_insights = json.loads(response.choices[0].message.content)
            
            # Save insights
            insight_record = {
                "id": f"{user_id}-insights-{datetime.utcnow().date().isoformat()}",
                "userId": user_id,
                "type": "daily_insights",
                "nutritionalTrends": daily_insights.get("nutritional_trends", {}),
                "healthStatus": daily_insights.get("health_status", {}),
                "dailyRecommendations": daily_insights.get("daily_recommendations", []),
                "longTermGoals": daily_insights.get("long_term_goals", []),
                "riskFactors": daily_insights.get("risk_factors", []),
                "generatedAt": datetime.utcnow().isoformat(),
                "dataRange": {
                    "start": recent_cutoff,
                    "end": datetime.utcnow().isoformat()
                }
            }
            
            recommendations_container.upsert_item(insight_record)
            
            logger.info(f"Generated daily insights for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error generating daily insights for user {user_id}: {str(e)}")
    
    async def health_trend_analysis(self):
        """Analyze long-term health trends for users"""
        while self.running:
            try:
                # Run weekly trend analysis
                current_time = datetime.utcnow()
                
                if current_time.weekday() == 6 and current_time.hour == 8:  # Sunday at 8 AM UTC
                    logger.info("Starting weekly health trend analysis")
                    
                    # Get users who have been active in the last 30 days
                    cutoff_date = (current_time - timedelta(days=30)).isoformat()
                    
                    active_users = set()
                    
                    # Get active users
                    for container in [food_container, medical_container]:
                        for item in container.query_items(
                            query="SELECT DISTINCT c.userId FROM c WHERE c.timestamp >= @cutoff",
                            parameters=[{"name": "@cutoff", "value": cutoff_date}],
                            enable_cross_partition_query=True
                        ):
                            active_users.add(item['userId'])
                    
                    # Analyze trends for each user
                    for user_id in active_users:
                        await self.analyze_user_health_trends(user_id)
                    
                    logger.info(f"Health trend analysis completed for {len(active_users)} users")
                
                await asyncio.sleep(3600)  # Check every hour
                
            except Exception as e:
                logger.error(f"Error in health_trend_analysis: {str(e)}")
                await asyncio.sleep(3600)
    
    async def analyze_user_health_trends(self, user_id: str):
        """Analyze health trends for a specific user"""
        try:
            # Get user's data from the last 90 days
            trend_cutoff = (datetime.utcnow() - timedelta(days=90)).isoformat()
            
            # Get historical food data
            food_history = list(food_container.query_items(
                query="SELECT * FROM c WHERE c.userId = @userId AND c.timestamp >= @cutoff ORDER BY c.timestamp ASC",
                parameters=[
                    {"name": "@userId", "value": user_id},
                    {"name": "@cutoff", "value": trend_cutoff}
                ],
                enable_cross_partition_query=True
            ))
            
            # Get historical medical data
            medical_history = list(medical_container.query_items(
                query="SELECT * FROM c WHERE c.userId = @userId AND c.timestamp >= @cutoff ORDER BY c.timestamp ASC",
                parameters=[
                    {"name": "@userId", "value": user_id},
                    {"name": "@cutoff", "value": trend_cutoff}
                ],
                enable_cross_partition_query=True
            ))
            
            if len(food_history) < 5:  # Need minimum data for trend analysis
                return
            
            # Generate trend analysis
            trend_prompt = f"""
            Analyze long-term health trends for this user over the last 90 days:
            
            Food History Trend:
            {json.dumps(food_history, indent=2)}
            
            Medical History Trend:
            {json.dumps(medical_history, indent=2)}
            
            Provide comprehensive trend analysis including:
            1. Nutritional pattern changes over time
            2. Health metric improvements or deteriorations
            3. Behavioral pattern identification
            4. Risk trend assessment
            5. Long-term health trajectory prediction
            6. Personalized intervention recommendations
            
            Format as JSON with keys: nutritional_patterns, health_metrics_trend, behavioral_patterns, risk_trends, health_trajectory, interventions
            """
            
            response = openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert health trend analyst providing longitudinal health assessments."},
                    {"role": "user", "content": trend_prompt}
                ],
                temperature=0.2
            )
            
            # Parse trend analysis
            trend_analysis = json.loads(response.choices[0].message.content)
            
            # Save trend analysis
            trend_record = {
                "id": f"{user_id}-trends-{datetime.utcnow().date().isoformat()}",
                "userId": user_id,
                "type": "health_trends",
                "nutritionalPatterns": trend_analysis.get("nutritional_patterns", {}),
                "healthMetricsTrend": trend_analysis.get("health_metrics_trend", {}),
                "behavioralPatterns": trend_analysis.get("behavioral_patterns", {}),
                "riskTrends": trend_analysis.get("risk_trends", {}),
                "healthTrajectory": trend_analysis.get("health_trajectory", {}),
                "interventions": trend_analysis.get("interventions", []),
                "generatedAt": datetime.utcnow().isoformat(),
                "analysisRange": {
                    "start": trend_cutoff,
                    "end": datetime.utcnow().isoformat(),
                    "dataPoints": len(food_history) + len(medical_history)
                }
            }
            
            recommendations_container.upsert_item(trend_record)
            
            logger.info(f"Generated health trend analysis for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error analyzing health trends for user {user_id}: {str(e)}")
    
    async def cleanup_old_data(self):
        """Clean up old data to manage storage costs"""
        while self.running:
            try:
                # Run cleanup monthly
                current_time = datetime.utcnow()
                
                if current_time.day == 1 and current_time.hour == 2:  # First day of month at 2 AM UTC
                    logger.info("Starting monthly data cleanup")
                    
                    # Delete data older than 2 years
                    cleanup_cutoff = (current_time - timedelta(days=730)).isoformat()
                    
                    # Cleanup old food history (keep aggregated summaries)
                    old_food_items = list(food_container.query_items(
                        query="SELECT c.id, c.userId FROM c WHERE c.timestamp < @cutoff",
                        parameters=[{"name": "@cutoff", "value": cleanup_cutoff}],
                        enable_cross_partition_query=True
                    ))
                    
                    for item in old_food_items:
                        food_container.delete_item(item=item['id'], partition_key=item['userId'])
                    
                    # Cleanup old medical records (be more conservative)
                    old_medical_cutoff = (current_time - timedelta(days=1095)).isoformat()  # 3 years
                    old_medical_items = list(medical_container.query_items(
                        query="SELECT c.id, c.userId FROM c WHERE c.timestamp < @cutoff AND c.type != 'critical'",
                        parameters=[{"name": "@cutoff", "value": old_medical_cutoff}],
                        enable_cross_partition_query=True
                    ))
                    
                    for item in old_medical_items:
                        medical_container.delete_item(item=item['id'], partition_key=item['userId'])
                    
                    # Cleanup old blob storage files
                    await self.cleanup_old_blobs(cleanup_cutoff)
                    
                    logger.info(f"Cleanup completed: removed {len(old_food_items)} food items and {len(old_medical_items)} medical items")
                
                await asyncio.sleep(3600)  # Check every hour
                
            except Exception as e:
                logger.error(f"Error in cleanup_old_data: {str(e)}")
                await asyncio.sleep(3600)
    
    async def cleanup_old_blobs(self, cutoff_date: str):
        """Clean up old blob storage files"""
        try:
            cutoff_datetime = datetime.fromisoformat(cutoff_date.replace('Z', '+00:00'))
            
            for container_name in ['food-images', 'medical-documents']:
                container_client = blob_service_client.get_container_client(container_name)
                
                blobs_to_delete = []
                for blob in container_client.list_blobs():
                    if blob.last_modified < cutoff_datetime:
                        blobs_to_delete.append(blob.name)
                
                # Delete old blobs
                for blob_name in blobs_to_delete:
                    blob_client = container_client.get_blob_client(blob_name)
                    blob_client.delete_blob()
                
                logger.info(f"Deleted {len(blobs_to_delete)} old blobs from {container_name}")
                
        except Exception as e:
            logger.error(f"Error cleaning up old blobs: {str(e)}")
    
    async def process_service_bus_messages(self):
        """Process messages from Service Bus for real-time notifications"""
        if not servicebus_client:
            return
        
        while self.running:
            try:
                with servicebus_client.get_queue_receiver(queue_name="health-notifications") as receiver:
                    for msg in receiver:
                        try:
                            message_data = json.loads(str(msg))
                            await self.handle_notification_message(message_data)
                            receiver.complete_message(msg)
                            
                        except Exception as e:
                            logger.error(f"Error processing Service Bus message: {str(e)}")
                            receiver.abandon_message(msg)
                
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.error(f"Error in process_service_bus_messages: {str(e)}")
                await asyncio.sleep(30)
    
    async def handle_notification_message(self, message_data: Dict[str, Any]):
        """Handle notification messages"""
        try:
            message_type = message_data.get('type')
            user_id = message_data.get('userId')
            
            if message_type == 'urgent_health_alert':
                await self.process_urgent_health_alert(user_id, message_data)
            elif message_type == 'daily_reminder':
                await self.process_daily_reminder(user_id, message_data)
            elif message_type == 'analysis_request':
                await self.process_analysis_request(user_id, message_data)
            
            logger.info(f"Processed notification message type: {message_type} for user: {user_id}")
            
        except Exception as e:
            logger.error(f"Error handling notification message: {str(e)}")
    
    async def process_urgent_health_alert(self, user_id: str, message_data: Dict[str, Any]):
        """Process urgent health alerts"""
        # Implement urgent health alert processing
        pass
    
    async def process_daily_reminder(self, user_id: str, message_data: Dict[str, Any]):
        """Process daily reminder messages"""
        # Implement daily reminder processing
        pass
    
    async def process_analysis_request(self, user_id: str, message_data: Dict[str, Any]):
        """Process analysis request messages"""
        # Implement analysis request processing
        pass

# Main entry point
async def main():
    """Main entry point for the background processor"""
    processor = HealthDataProcessor()
    
    try:
        logger.info("Starting AI Personal Health Companion Background Processor")
        await processor.start()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.error(f"Processor failed: {str(e)}")
        raise
    finally:
        await processor.stop()

if __name__ == "__main__":
    asyncio.run(main())
