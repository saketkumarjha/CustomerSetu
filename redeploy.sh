#!/bin/bash

# ============================================================================
# Redeploy CustomerSetu Backend to Southeast Asia (Singapore)
# ============================================================================
# This script deletes your old East Asia deployment and redeploys to Singapore
# where OpenAI API is supported.
#
# Usage:
#   1. Update the variables below with your actual values
#   2. Run: bash redeploy.sh
# ============================================================================

set -e  # Exit on any error

# ============================================================================
# CONFIGURATION - UPDATE THESE VALUES
# ============================================================================

# Old deployment (to delete)
OLD_RESOURCE_GROUP="YOUR_OLD_RESOURCE_GROUP_NAME"  # e.g., "customersetu-eastasia-rg"

# New deployment
NEW_RESOURCE_GROUP="customersetu-backend-rg"
LOCATION="southeastasia"  # Singapore
CONTAINER_NAME="customersetu-backend"
IMAGE_NAME="customersetu-backend"
ACR_NAME="customersetuacr"  # Must be globally unique, lowercase, no hyphens
DNS_LABEL="customersetu-backend"  # Will create: customersetu-backend.southeastasia.azurecontainer.io

# Environment variables (UPDATE WITH YOUR ACTUAL VALUES)
OPENAI_API_KEY="YOUR_OPENAI_API_KEY_HERE"
SUPABASE_KEY="YOUR_SUPABASE_KEY_HERE"
API_KEY="YOUR_API_KEY_HERE"
SMTP_PASSWORD="YOUR_SMTP_PASSWORD_HERE"
DB_PASSWORD="YOUR_DB_PASSWORD_HERE"
TWILIO_ACCOUNT_SID="YOUR_TWILIO_SID_HERE"
TWILIO_AUTH_TOKEN="YOUR_TWILIO_TOKEN_HERE"
GEMINI_API_KEY="YOUR_GEMINI_KEY_HERE"

# ============================================================================
# STEP 1: Login to Azure
# ============================================================================

echo "============================================"
echo "STEP 1: Logging into Azure..."
echo "============================================"
az login

# List subscriptions
echo ""
echo "Available subscriptions:"
az account list --output table

echo ""
read -p "Enter your subscription ID (or press Enter to use default): " SUBSCRIPTION_ID
if [ ! -z "$SUBSCRIPTION_ID" ]; then
    az account set --subscription "$SUBSCRIPTION_ID"
fi

echo "✅ Logged in successfully"
echo ""

# ============================================================================
# STEP 2: Delete Old Deployment
# ============================================================================

echo "============================================"
echo "STEP 2: Deleting old deployment..."
echo "============================================"

read -p "Do you want to delete the old resource group '$OLD_RESOURCE_GROUP'? (yes/no): " DELETE_OLD
if [ "$DELETE_OLD" = "yes" ]; then
    echo "Deleting resource group: $OLD_RESOURCE_GROUP"
    az group delete --name "$OLD_RESOURCE_GROUP" --yes --no-wait
    echo "✅ Deletion initiated (running in background)"
else
    echo "⚠️  Skipping deletion. Make sure to delete manually if needed."
fi

echo ""

# ============================================================================
# STEP 3: Create New Resource Group in Southeast Asia
# ============================================================================

echo "============================================"
echo "STEP 3: Creating new resource group..."
echo "============================================"

az group create --name "$NEW_RESOURCE_GROUP" --location "$LOCATION"
echo "✅ Resource group created: $NEW_RESOURCE_GROUP in $LOCATION"
echo ""

# ============================================================================
# STEP 4: Create Azure Container Registry
# ============================================================================

echo "============================================"
echo "STEP 4: Creating Azure Container Registry..."
echo "============================================"

az acr create --resource-group "$NEW_RESOURCE_GROUP" --name "$ACR_NAME" --sku Basic --location "$LOCATION"
echo "✅ ACR created: $ACR_NAME"
echo ""

# ============================================================================
# STEP 5: Build and Push Docker Image
# ============================================================================

echo "============================================"
echo "STEP 5: Building and pushing Docker image..."
echo "============================================"

cd backend
az acr build --registry "$ACR_NAME" --image "$IMAGE_NAME:latest" .
cd ..

echo "✅ Image built and pushed to ACR"
echo ""

# ============================================================================
# STEP 6: Get ACR Credentials
# ============================================================================

echo "============================================"
echo "STEP 6: Getting ACR credentials..."
echo "============================================"

ACR_USERNAME=$(az acr credential show --name "$ACR_NAME" --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name "$ACR_NAME" --query "passwords[0].value" -o tsv)
ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --query loginServer -o tsv)

echo "✅ ACR credentials retrieved"
echo ""

# ============================================================================
# STEP 7: Create Container Instance
# ============================================================================

echo "============================================"
echo "STEP 7: Creating container instance..."
echo "============================================"

az container create \
  --resource-group "$NEW_RESOURCE_GROUP" \
  --name "$CONTAINER_NAME" \
  --image "$ACR_LOGIN_SERVER/$IMAGE_NAME:latest" \
  --registry-login-server "$ACR_LOGIN_SERVER" \
  --registry-username "$ACR_USERNAME" \
  --registry-password "$ACR_PASSWORD" \
  --dns-name-label "$DNS_LABEL" \
  --ports 8000 \
  --cpu 2 \
  --memory 4 \
  --location "$LOCATION" \
  --environment-variables \
    OPENAI_API_KEY="$OPENAI_API_KEY" \
    OPENAI_VISION_MODEL="gpt-4o" \
    OPENAI_EMBEDDING_MODEL="text-embedding-3-small" \
    OPENAI_EMBEDDING_DIMENSION="512" \
    SUPABASE_URL="https://cmsjeupljkgfmodrlosf.supabase.co" \
    SUPABASE_KEY="$SUPABASE_KEY" \
    SUPABASE_STORAGE_BUCKET="complaint-images" \
    TESSERACT_CMD="/usr/bin/tesseract" \
    APP_ENV="production" \
    API_V1_PREFIX="/api/v1" \
    API_KEY="$API_KEY" \
    RATE_LIMIT_PER_MINUTE="1000" \
    DUPLICATE_THRESHOLD="0.92" \
    MAX_FILE_SIZE_MB="10" \
    GEMINI_API_KEY="$GEMINI_API_KEY" \
    SMTP_HOST="smtp.gmail.com" \
    SMTP_PORT="587" \
    SMTP_USER="unionbank.complaints.demo@gmail.com" \
    SMTP_PASSWORD="$SMTP_PASSWORD" \
    EMAIL_FROM_ADDRESS="unionbank.complaints.demo@gmail.com" \
    TIER_TEMPLATES_PATH="app/templates/tier_responses/" \
    ENABLE_AUTO_KB_ENRICHMENT="true" \
    KB_ENRICHMENT_DELAY_HOURS="24" \
    NOTIFICATION_RETRY_COUNT="3" \
    NOTIFICATION_TIMEOUT_SECONDS="10" \
    DB_HOST="db.cmsjeupljkgfmodrlosf.supabase.co" \
    DB_PORT="5432" \
    DB_NAME="postgres" \
    DB_USER="postgres" \
    DB_PASSWORD="$DB_PASSWORD" \
    TWILIO_ACCOUNT_SID="$TWILIO_ACCOUNT_SID" \
    TWILIO_AUTH_TOKEN="$TWILIO_AUTH_TOKEN" \
    TWILIO_WHATSAPP_NUMBER="whatsapp:+14155238886" \
    WEBHOOK_BASE_URL="https://$DNS_LABEL.$LOCATION.azurecontainer.io" \
    CORS_ALLOWED_ORIGINS="*"

echo "✅ Container instance created"
echo ""

# ============================================================================
# STEP 8: Get Backend URL
# ============================================================================

echo "============================================"
echo "STEP 8: Getting backend URL..."
echo "============================================"

BACKEND_URL=$(az container show --resource-group "$NEW_RESOURCE_GROUP" --name "$CONTAINER_NAME" --query ipAddress.fqdn -o tsv)

echo ""
echo "============================================"
echo "✅ DEPLOYMENT COMPLETE!"
echo "============================================"
echo ""
echo "Backend URL: https://$BACKEND_URL"
echo "API Docs: https://$BACKEND_URL/docs"
echo "Health Check: https://$BACKEND_URL/health"
echo ""
echo "Next steps:"
echo "1. Update frontend/.env.production with:"
echo "   VITE_API_URL=https://$BACKEND_URL"
echo ""
echo "2. Redeploy frontend to Azure Static Web Apps"
echo ""
echo "3. Test the deployment:"
echo "   curl https://$BACKEND_URL/health"
echo ""
echo "4. Update Twilio webhook URL (if using WhatsApp):"
echo "   https://$BACKEND_URL/api/v1/whatsapp/webhook"
echo ""
echo "============================================"
