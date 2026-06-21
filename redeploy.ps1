# ============================================================================
# Redeploy CustomerSetu Backend to Southeast Asia (Singapore)
# ============================================================================
# This script deletes your old East Asia deployment and redeploys to Singapore
# where OpenAI API is supported.
#
# Usage:
#   1. Update the variables below with your actual values
#   2. Run in PowerShell: .\redeploy.ps1
# ============================================================================

$ErrorActionPreference = "Stop"

# ============================================================================
# CONFIGURATION - UPDATE THESE VALUES
# ============================================================================

# Old deployment (to delete)
$OLD_RESOURCE_GROUP = "YOUR_OLD_RESOURCE_GROUP_NAME"  # e.g., "customersetu-eastasia-rg"

# New deployment
$NEW_RESOURCE_GROUP = "customersetu-backend-rg"
$LOCATION = "southeastasia"  # Singapore
$CONTAINER_NAME = "customersetu-backend"
$IMAGE_NAME = "customersetu-backend"
$ACR_NAME = "customersetuacr"  # Must be globally unique, lowercase, no hyphens
$DNS_LABEL = "customersetu-backend"  # Will create: customersetu-backend.southeastasia.azurecontainer.io

# Environment variables (UPDATE WITH YOUR ACTUAL VALUES)
$OPENAI_API_KEY = "YOUR_OPENAI_API_KEY_HERE"
$SUPABASE_KEY = "YOUR_SUPABASE_KEY_HERE"
$API_KEY = "YOUR_API_KEY_HERE"
$SMTP_PASSWORD = "YOUR_SMTP_PASSWORD_HERE"
$DB_PASSWORD = "YOUR_DB_PASSWORD_HERE"
$TWILIO_ACCOUNT_SID = "YOUR_TWILIO_SID_HERE"
$TWILIO_AUTH_TOKEN = "YOUR_TWILIO_TOKEN_HERE"
$GEMINI_API_KEY = "YOUR_GEMINI_KEY_HERE"

# ============================================================================
# STEP 1: Login to Azure
# ============================================================================

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "STEP 1: Logging into Azure..." -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
az login

# List subscriptions
Write-Host ""
Write-Host "Available subscriptions:" -ForegroundColor Yellow
az account list --output table

Write-Host ""
$SUBSCRIPTION_ID = Read-Host "Enter your subscription ID (or press Enter to use default)"
if ($SUBSCRIPTION_ID) {
    az account set --subscription $SUBSCRIPTION_ID
}

Write-Host "✅ Logged in successfully" -ForegroundColor Green
Write-Host ""

# ============================================================================
# STEP 2: Delete Old Deployment
# ============================================================================

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "STEP 2: Deleting old deployment..." -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

$DELETE_OLD = Read-Host "Do you want to delete the old resource group '$OLD_RESOURCE_GROUP'? (yes/no)"
if ($DELETE_OLD -eq "yes") {
    Write-Host "Deleting resource group: $OLD_RESOURCE_GROUP" -ForegroundColor Yellow
    az group delete --name $OLD_RESOURCE_GROUP --yes --no-wait
    Write-Host "✅ Deletion initiated (running in background)" -ForegroundColor Green
} else {
    Write-Host "⚠️  Skipping deletion. Make sure to delete manually if needed." -ForegroundColor Yellow
}

Write-Host ""

# ============================================================================
# STEP 3: Create New Resource Group in Southeast Asia
# ============================================================================

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "STEP 3: Creating new resource group..." -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

az group create --name $NEW_RESOURCE_GROUP --location $LOCATION
Write-Host "✅ Resource group created: $NEW_RESOURCE_GROUP in $LOCATION" -ForegroundColor Green
Write-Host ""

# ============================================================================
# STEP 4: Create Azure Container Registry
# ============================================================================

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "STEP 4: Creating Azure Container Registry..." -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

az acr create --resource-group $NEW_RESOURCE_GROUP --name $ACR_NAME --sku Basic --location $LOCATION
Write-Host "✅ ACR created: $ACR_NAME" -ForegroundColor Green
Write-Host ""

# ============================================================================
# STEP 5: Build and Push Docker Image
# ============================================================================

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "STEP 5: Building and pushing Docker image..." -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

Push-Location backend
az acr build --registry $ACR_NAME --image "${IMAGE_NAME}:latest" .
Pop-Location

Write-Host "✅ Image built and pushed to ACR" -ForegroundColor Green
Write-Host ""

# ============================================================================
# STEP 6: Get ACR Credentials
# ============================================================================

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "STEP 6: Getting ACR credentials..." -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

$ACR_USERNAME = az acr credential show --name $ACR_NAME --query username -o tsv
$ACR_PASSWORD = az acr credential show --name $ACR_NAME --query "passwords[0].value" -o tsv
$ACR_LOGIN_SERVER = az acr show --name $ACR_NAME --query loginServer -o tsv

Write-Host "✅ ACR credentials retrieved" -ForegroundColor Green
Write-Host ""

# ============================================================================
# STEP 7: Create Container Instance
# ============================================================================

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "STEP 7: Creating container instance..." -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

az container create `
  --resource-group $NEW_RESOURCE_GROUP `
  --name $CONTAINER_NAME `
  --image "$ACR_LOGIN_SERVER/${IMAGE_NAME}:latest" `
  --registry-login-server $ACR_LOGIN_SERVER `
  --registry-username $ACR_USERNAME `
  --registry-password $ACR_PASSWORD `
  --dns-name-label $DNS_LABEL `
  --ports 8000 `
  --cpu 2 `
  --memory 4 `
  --location $LOCATION `
  --environment-variables `
    OPENAI_API_KEY=$OPENAI_API_KEY `
    OPENAI_VISION_MODEL="gpt-4o" `
    OPENAI_EMBEDDING_MODEL="text-embedding-3-small" `
    OPENAI_EMBEDDING_DIMENSION="512" `
    SUPABASE_URL="https://cmsjeupljkgfmodrlosf.supabase.co" `
    SUPABASE_KEY=$SUPABASE_KEY `
    SUPABASE_STORAGE_BUCKET="complaint-images" `
    TESSERACT_CMD="/usr/bin/tesseract" `
    APP_ENV="production" `
    API_V1_PREFIX="/api/v1" `
    API_KEY=$API_KEY `
    RATE_LIMIT_PER_MINUTE="1000" `
    DUPLICATE_THRESHOLD="0.92" `
    MAX_FILE_SIZE_MB="10" `
    GEMINI_API_KEY=$GEMINI_API_KEY `
    SMTP_HOST="smtp.gmail.com" `
    SMTP_PORT="587" `
    SMTP_USER="unionbank.complaints.demo@gmail.com" `
    SMTP_PASSWORD=$SMTP_PASSWORD `
    EMAIL_FROM_ADDRESS="unionbank.complaints.demo@gmail.com" `
    TIER_TEMPLATES_PATH="app/templates/tier_responses/" `
    ENABLE_AUTO_KB_ENRICHMENT="true" `
    KB_ENRICHMENT_DELAY_HOURS="24" `
    NOTIFICATION_RETRY_COUNT="3" `
    NOTIFICATION_TIMEOUT_SECONDS="10" `
    DB_HOST="db.cmsjeupljkgfmodrlosf.supabase.co" `
    DB_PORT="5432" `
    DB_NAME="postgres" `
    DB_USER="postgres" `
    DB_PASSWORD=$DB_PASSWORD `
    TWILIO_ACCOUNT_SID=$TWILIO_ACCOUNT_SID `
    TWILIO_AUTH_TOKEN=$TWILIO_AUTH_TOKEN `
    TWILIO_WHATSAPP_NUMBER="whatsapp:+14155238886" `
    WEBHOOK_BASE_URL="https://$DNS_LABEL.$LOCATION.azurecontainer.io" `
    CORS_ALLOWED_ORIGINS="*"

Write-Host "✅ Container instance created" -ForegroundColor Green
Write-Host ""

# ============================================================================
# STEP 8: Get Backend URL
# ============================================================================

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "STEP 8: Getting backend URL..." -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

$BACKEND_URL = az container show --resource-group $NEW_RESOURCE_GROUP --name $CONTAINER_NAME --query ipAddress.fqdn -o tsv

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "✅ DEPLOYMENT COMPLETE!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Backend URL: https://$BACKEND_URL" -ForegroundColor Yellow
Write-Host "API Docs: https://$BACKEND_URL/docs" -ForegroundColor Yellow
Write-Host "Health Check: https://$BACKEND_URL/health" -ForegroundColor Yellow
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Update frontend/.env.production with:" -ForegroundColor White
Write-Host "   VITE_API_URL=https://$BACKEND_URL" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Redeploy frontend to Azure Static Web Apps" -ForegroundColor White
Write-Host ""
Write-Host "3. Test the deployment:" -ForegroundColor White
Write-Host "   curl https://$BACKEND_URL/health" -ForegroundColor Gray
Write-Host ""
Write-Host "4. Update Twilio webhook URL (if using WhatsApp):" -ForegroundColor White
Write-Host "   https://$BACKEND_URL/api/v1/whatsapp/webhook" -ForegroundColor Gray
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
