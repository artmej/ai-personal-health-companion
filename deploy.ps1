# AI Personal Health Companion - Deployment Script
# PowerShell script for deploying the complete solution to Azure

param(
    [Parameter(Mandatory=$true)]
    [string]$EnvironmentName,
    
    [Parameter(Mandatory=$true)]
    [string]$Location = "eastus",
    
    [Parameter(Mandatory=$false)]
    [string]$SubscriptionId,
    
    [Parameter(Mandatory=$false)]
    [string]$ResourceGroupName
)

# Set error action preference
$ErrorActionPreference = "Stop"

Write-Host "🏥 AI Personal Health Companion - Deployment Started" -ForegroundColor Green
Write-Host "Environment: $EnvironmentName" -ForegroundColor Yellow
Write-Host "Location: $Location" -ForegroundColor Yellow

try {
    # Check if Azure Developer CLI is installed
    if (!(Get-Command "azd" -ErrorAction SilentlyContinue)) {
        Write-Error "Azure Developer CLI (azd) is not installed. Please install it first: https://aka.ms/azd-install"
        exit 1
    }

    # Check if user is logged in to Azure
    Write-Host "🔐 Checking Azure authentication..." -ForegroundColor Blue
    $authCheck = azd auth login --check-status 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Please login to Azure..." -ForegroundColor Yellow
        azd auth login
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to authenticate with Azure"
            exit 1
        }
    }

    # Initialize the project if not already done
    Write-Host "🚀 Initializing Azure Developer CLI project..." -ForegroundColor Blue
    if (!(Test-Path ".azure")) {
        azd init --environment $EnvironmentName --location $Location --subscription $SubscriptionId
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to initialize azd project"
            exit 1
        }
    }

    # Set environment variables
    Write-Host "⚙️ Setting environment variables..." -ForegroundColor Blue
    azd env set AZURE_LOCATION $Location
    azd env set AZURE_ENV_NAME $EnvironmentName
    
    if ($SubscriptionId) {
        azd env set AZURE_SUBSCRIPTION_ID $SubscriptionId
    }

    # Get current user for Key Vault access
    $currentUser = az account show --query user.name -o tsv
    if ($currentUser) {
        $principalId = az ad user show --id $currentUser --query id -o tsv
        azd env set AZURE_PRINCIPAL_ID $principalId
    }

    # Provision infrastructure
    Write-Host "🏗️ Provisioning Azure infrastructure..." -ForegroundColor Blue
    azd provision
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to provision infrastructure"
        exit 1
    }

    # Get provisioned resource information
    Write-Host "📋 Getting resource information..." -ForegroundColor Blue
    $outputs = azd env get-values --output json | ConvertFrom-Json
    
    # Store OpenAI API key in Key Vault (manual step notification)
    Write-Host "🔑 IMPORTANT: Please configure your OpenAI API key..." -ForegroundColor Red
    Write-Host "Run the following command to set your OpenAI API key:" -ForegroundColor Yellow
    Write-Host "az keyvault secret set --vault-name '$($outputs.KEY_VAULT_NAME)' --name 'openai-api-key' --value 'YOUR_OPENAI_API_KEY'" -ForegroundColor Cyan

    # Deploy application services
    Write-Host "📦 Deploying application services..." -ForegroundColor Blue
    azd deploy
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to deploy application services"
        exit 1
    }

    # Deploy Logic Apps workflows
    Write-Host "🔄 Deploying Logic Apps workflows..." -ForegroundColor Blue
    Deploy-LogicApps -ResourceGroupName $outputs.AZURE_RESOURCE_GROUP_NAME -Location $Location

    # Configure M365 Copilot Agents (manual step notification)
    Write-Host "🤖 MANUAL STEP: Configure M365 Copilot Agents..." -ForegroundColor Red
    Write-Host "1. Upload agent configurations from the 'agents' folder to M365 Admin Center" -ForegroundColor Yellow
    Write-Host "2. Configure API endpoints in agent settings:" -ForegroundColor Yellow
    Write-Host "   - API Endpoint: $($outputs.API_BASE_URL)" -ForegroundColor Cyan

    # Display deployment summary
    Write-Host "`n✅ Deployment completed successfully!" -ForegroundColor Green
    Write-Host "`n📊 Deployment Summary:" -ForegroundColor Blue
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Blue
    Write-Host "🌐 Web Application: $($outputs.WEB_BASE_URL)" -ForegroundColor Cyan
    Write-Host "🔗 API Endpoint: $($outputs.API_BASE_URL)" -ForegroundColor Cyan
    Write-Host "💾 Storage Account: $($outputs.STORAGE_ACCOUNT_NAME)" -ForegroundColor Cyan
    Write-Host "🗄️ Cosmos DB: $($outputs.COSMOS_DB_ACCOUNT_NAME)" -ForegroundColor Cyan
    Write-Host "🔑 Key Vault: $($outputs.KEY_VAULT_NAME)" -ForegroundColor Cyan
    Write-Host "🤖 AI Services: $($outputs.AI_SERVICES_NAME)" -ForegroundColor Cyan
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Blue

    Write-Host "`n🔧 Next Steps:" -ForegroundColor Blue
    Write-Host "1. Configure your OpenAI API key in Key Vault" -ForegroundColor Yellow
    Write-Host "2. Upload and configure M365 Copilot Agents from the 'agents' folder" -ForegroundColor Yellow
    Write-Host "3. Test the application by uploading a food image" -ForegroundColor Yellow
    Write-Host "4. Review and customize the Logic Apps workflows as needed" -ForegroundColor Yellow

    Write-Host "`n🎉 Your AI Personal Health Companion is ready!" -ForegroundColor Green

} catch {
    Write-Error "Deployment failed: $($_.Exception.Message)"
    Write-Host "💡 Troubleshooting tips:" -ForegroundColor Yellow
    Write-Host "1. Ensure you have the required Azure permissions" -ForegroundColor White
    Write-Host "2. Check Azure resource quotas in your subscription" -ForegroundColor White
    Write-Host "3. Verify the chosen location supports all required services" -ForegroundColor White
    Write-Host "4. Run 'azd logs' to see detailed error information" -ForegroundColor White
    exit 1
}

function Deploy-LogicApps {
    param(
        [string]$ResourceGroupName,
        [string]$Location
    )
    
    try {
        Write-Host "Deploying Logic Apps workflows..." -ForegroundColor Blue
        
        # Deploy food analysis automation workflow
        $foodWorkflowTemplate = Get-Content "workflows/food-analysis-automation.json" -Raw
        az deployment group create `
            --resource-group $ResourceGroupName `
            --template-file "workflows/food-analysis-automation.json" `
            --parameters workflowName="food-analysis-automation"
        
        # Deploy daily insights workflow
        $dailyWorkflowTemplate = Get-Content "workflows/daily-health-insights.json" -Raw
        az deployment group create `
            --resource-group $ResourceGroupName `
            --template-file "workflows/daily-health-insights.json" `
            --parameters workflowName="daily-health-insights"
        
        Write-Host "Logic Apps workflows deployed successfully" -ForegroundColor Green
        
    } catch {
        Write-Warning "Failed to deploy Logic Apps: $($_.Exception.Message)"
        Write-Host "You can deploy them manually from the Azure Portal" -ForegroundColor Yellow
    }
}
