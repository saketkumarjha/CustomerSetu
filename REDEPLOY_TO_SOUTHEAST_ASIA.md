# 🌏 Redeploy to Southeast Asia (Singapore) - Complete Guide

## Problem

Your backend is deployed in **Azure East Asia (Hong Kong)**, which is blocked by OpenAI. All GPT-4o API calls fail with `unsupported_country_region_territory`.

## Solution

Redeploy to **Southeast Asia (Singapore)** region - OpenAI supported, still in Asia-Pacific.

---

## 📋 Prerequisites

1. **Azure CLI installed**

   ```bash
   # Check if installed
   az --version

   # If not installed, download from:
   # https://learn.microsoft.com/en-us/cli/azure/install-azure-cli
   ```

2. **Login to Azure**

   ```bash
   az login
   ```

3. **Set your subscription** (if you have multiple)

   ```bash
   # List subscriptions
   az account list --output table

   # Set active subscription
   az account set --subscription "YOUR_SUBSCRIPTION_ID"
   ```

---

## 🗑️ STEP 1: Delete Old Deployment (East Asia)

### Option A: If you know your resource group name

```bash
# List all resource groups to find yours
az group list --output table

# Delete the entire resource group (WARNING: This deletes EVERYTHING in it)
az group delete --name YOUR_RESOURCE_GROUP_NAME --yes --no-wait
```

### Option B: If you deployed using Azure Container Instances

```bash
# List all container instances
az container list --output table

# Delete specific container
az container delete --resource-group YOUR_RESOURCE_GROUP --name YOUR_CONTAINER_NAME --yes
```

### Option C: If you deployed using Azure App Service

```bash
# List all app services
az webapp list --output table

# Delete specific app service
az webapp delete --resource-group YOUR_RESOURCE_GROUP --name YOUR_APP_NAME
```

### Option D: Delete via Azure Portal (GUI Method)

1. Go to https://portal.azure.com
2. Navigate to "Resource Groups"
3. Find your resource group (likely named something like `complaint-dashboard-rg` or `customersetu-rg`)
4. Click "Delete resource group"
5. Type the resource group name to confirm
6. Click "Delete"

---

## 🚀 STEP 2: Deploy Backend to Southeast Asia

### Method 1: Azure Container Instances (Recommended - Simplest)

```bash
# Set variables
RESOURCE_GROUP="customersetu-backend-rg"
LOCATION="southeastasia"  # Singapore
CONTAINER_NAME="customersetu-backend"
IMAGE_NAME="customersetu-backend"

# Create resource group in Southeast Asia
az group create --name $RESOURCE_GROUP --location $LOCATION

# Build and push Docker image to Azure Container Registry (ACR)
# First, create ACR
ACR_NAME="customersetuacr"  # Must be globally unique, lowercase, no hyphens
az acr create --resource-group $RESOURCE_GROUP --name $ACR_NAME --sku Basic --location $LOCATION

# Login to ACR
az acr login --name $ACR_NAME

# Build and push image
cd backend
az acr build --registry $ACR_NAME --image $IMAGE_NAME:latest .

# Get ACR credentials
ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query "passwords[0].value" -o tsv)
ACR_LOGIN_SERVER=$(az acr show --name $ACR_NAME --query loginServer -o tsv)

# Create container instance with environment variables
az container create \
  --resource-group $RESOURCE_GROUP \
  --name $CONTAINER_NAME \
  --image $ACR_LOGIN_SERVER/$IMAGE_NAME:latest \
  --registry-login-server $ACR_LOGIN_SERVER \
  --registry-username $ACR_USERNAME \
  --registry-password $ACR_PASSWORD \
  --dns-name-label customersetu-backend \
  --ports 8000 \
  --cpu 2 \
  --memory 4 \
  --location $LOCATION \
  --environment-variables \
    OPENAI_API_KEY="YOUR_OPENAI_API_KEY" \
    OPENAI_VISION_MODEL="gpt-4o" \
    OPENAI_EMBEDDING_MODEL="text-embedding-3-small" \
    OPENAI_EMBEDDING_DIMENSION="512" \
    SUPABASE_URL="https://cmsjeupljkgfmodrlosf.supabase.co" \
    SUPABASE_KEY="YOUR_SUPABASE_KEY" \
    SUPABASE_STORAGE_BUCKET="complaint-images" \
    TESSERACT_CMD="/usr/bin/tesseract" \
    APP_ENV="production" \
    API_V1_PREFIX="/api/v1" \
    API_KEY="YOUR_API_KEY" \
    RATE_LIMIT_PER_MINUTE="1000" \
    DUPLICATE_THRESHOLD="0.92" \
    MAX_FILE_SIZE_MB="10" \
    GEMINI_API_KEY="YOUR_GEMINI_KEY" \
    SMTP_HOST="smtp.gmail.com" \
    SMTP_PORT="587" \
    SMTP_USER="unionbank.complaints.demo@gmail.com" \
    SMTP_PASSWORD="YOUR_SMTP_PASSWORD" \
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
    DB_PASSWORD="YOUR_DB_PASSWORD" \
    TWILIO_ACCOUNT_SID="YOUR_TWILIO_SID" \
    TWILIO_AUTH_TOKEN="YOUR_TWILIO_TOKEN" \
    TWILIO_WHATSAPP_NUMBER="whatsapp:+14155238886" \
    WEBHOOK_BASE_URL="https://customersetu-backend.southeastasia.azurecontainer.io" \
    CORS_ALLOWED_ORIGINS="*"

# Get the public URL
az container show --resource-group $RESOURCE_GROUP --name $CONTAINER_NAME --query ipAddress.fqdn -o tsv
```

**Your backend will be available at:**

```
https://customersetu-backend.southeastasia.azurecontainer.io
```

---

### Method 2: Azure App Service (More Features, Slightly Complex)

```bash
# Set variables
RESOURCE_GROUP="customersetu-backend-rg"
LOCATION="southeastasia"
APP_SERVICE_PLAN="customersetu-plan"
WEB_APP_NAME="customersetu-backend"  # Must be globally unique

# Create resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create App Service Plan (B1 tier - Basic)
az appservice plan create \
  --name $APP_SERVICE_PLAN \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --is-linux \
  --sku B1

# Create Web App with Docker container
az webapp create \
  --resource-group $RESOURCE_GROUP \
  --plan $APP_SERVICE_PLAN \
  --name $WEB_APP_NAME \
  --deployment-container-image-name python:3.11-slim

# Configure environment variables (use your actual values)
az webapp config appsettings set \
  --resource-group $RESOURCE_GROUP \
  --name $WEB_APP_NAME \
  --settings \
    OPENAI_API_KEY="YOUR_OPENAI_API_KEY" \
    OPENAI_VISION_MODEL="gpt-4o" \
    OPENAI_EMBEDDING_MODEL="text-embedding-3-small" \
    OPENAI_EMBEDDING_DIMENSION="512" \
    SUPABASE_URL="https://cmsjeupljkgfmodrlosf.supabase.co" \
    SUPABASE_KEY="YOUR_SUPABASE_KEY" \
    SUPABASE_STORAGE_BUCKET="complaint-images" \
    TESSERACT_CMD="/usr/bin/tesseract" \
    APP_ENV="production" \
    CORS_ALLOWED_ORIGINS="*"

# Deploy using local Docker build
cd backend
az webapp config container set \
  --name $WEB_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --docker-custom-image-name $WEB_APP_NAME \
  --docker-registry-server-url https://index.docker.io

# Or deploy from ACR (if you created one)
az webapp config container set \
  --name $WEB_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --docker-custom-image-name $ACR_LOGIN_SERVER/$IMAGE_NAME:latest \
  --docker-registry-server-url https://$ACR_LOGIN_SERVER \
  --docker-registry-server-user $ACR_USERNAME \
  --docker-registry-server-password $ACR_PASSWORD

# Enable continuous deployment
az webapp deployment container config \
  --name $WEB_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --enable-cd true

# Get the URL
echo "Backend URL: https://$WEB_APP_NAME.azurewebsites.net"
```

---

## 🌐 STEP 3: Update Frontend Configuration

### Update Frontend Environment Variable

```bash
cd frontend

# Update .env.production (create if doesn't exist)
cat > .env.production << EOF
VITE_API_URL=https://customersetu-backend.southeastasia.azurecontainer.io
EOF
```

### Redeploy Frontend to Azure Static Web Apps

```bash
# If using Azure Static Web Apps CLI
cd frontend
npm run build

# Deploy (you'll need your deployment token from Azure Portal)
# Get it from: Azure Portal > Static Web Apps > Your App > Manage deployment token
az staticwebapp deploy \
  --app-name YOUR_STATIC_WEB_APP_NAME \
  --resource-group YOUR_FRONTEND_RESOURCE_GROUP \
  --source ./dist \
  --token YOUR_DEPLOYMENT_TOKEN
```

**Or update via GitHub Actions** (if you're using that):

1. Update the `VITE_API_URL` in your GitHub repository secrets
2. Push to main branch
3. GitHub Actions will auto-deploy

---

## ✅ STEP 4: Verify Deployment

### Test Backend Health

```bash
# Replace with your actual backend URL
BACKEND_URL="https://customersetu-backend.southeastasia.azurecontainer.io"

# Test health endpoint
curl $BACKEND_URL/health

# Test OpenAI connectivity (should work now!)
curl -X POST $BACKEND_URL/api/v1/pipeline/run/CMP-TEST1234 \
  -H "X-API-Key: YOUR_API_KEY"
```

### Test from Frontend

1. Open your frontend: https://proud-plant-0e6ce2600.7.azurestaticapps.net
2. Submit a test complaint
3. Watch the console - agents should now complete successfully!

Expected output:

```
✅ agent_update Classification Agent {"status":"complete"}
✅ agent_update Sentiment Agent {"status":"complete"}
✅ agent_update Compliance Agent {"status":"complete"}
✅ Confidence score: 0.85
```

---

## 🔧 STEP 5: Update Twilio Webhook (If Using WhatsApp)

```bash
# Update Twilio webhook URL to point to new backend
# Go to: https://console.twilio.com/
# Navigate to: Messaging > Try it out > Send a WhatsApp message
# Update webhook URL to: https://customersetu-backend.southeastasia.azurecontainer.io/api/v1/whatsapp/webhook
```

---

## 📊 Cost Comparison

| Service                           | East Asia (Old) | Southeast Asia (New) | Difference |
| --------------------------------- | --------------- | -------------------- | ---------- |
| Container Instances (2 vCPU, 4GB) | ~$73/month      | ~$73/month           | Same       |
| App Service B1                    | ~$13/month      | ~$13/month           | Same       |
| Data Transfer                     | Minimal         | Minimal              | Same       |

**No cost increase!** Southeast Asia pricing is identical to East Asia.

---

## 🚨 Troubleshooting

### If agents still fail after redeployment:

1. **Verify region:**

   ```bash
   az container show --resource-group $RESOURCE_GROUP --name $CONTAINER_NAME --query location -o tsv
   ```

   Should output: `southeastasia`

2. **Test OpenAI from container:**

   ```bash
   az container exec --resource-group $RESOURCE_GROUP --name $CONTAINER_NAME --exec-command "/bin/bash"

   # Inside container:
   curl -H "Authorization: Bearer $OPENAI_API_KEY" https://api.openai.com/v1/models
   ```

3. **Check container logs:**

   ```bash
   az container logs --resource-group $RESOURCE_GROUP --name $CONTAINER_NAME --follow
   ```

4. **Verify environment variables:**
   ```bash
   az container show --resource-group $RESOURCE_GROUP --name $CONTAINER_NAME --query containers[0].environmentVariables
   ```

---

## 📝 Quick Reference Commands

```bash
# List all resources in Southeast Asia
az resource list --location southeastasia --output table

# Check container status
az container show --resource-group $RESOURCE_GROUP --name $CONTAINER_NAME --query instanceView.state

# Restart container
az container restart --resource-group $RESOURCE_GROUP --name $CONTAINER_NAME

# Update environment variable
az container create --resource-group $RESOURCE_GROUP --name $CONTAINER_NAME --environment-variables KEY=VALUE

# Delete everything and start over
az group delete --name $RESOURCE_GROUP --yes --no-wait
```

---

## ✨ Expected Results After Redeployment

- ✅ All agents complete successfully
- ✅ Confidence scores: 70-95% (not 30%)
- ✅ No OpenAI API errors in logs
- ✅ Pipeline completes in 5-10 seconds
- ✅ No "unsupported_country_region_territory" errors

---

## 🆘 Need Help?

1. **Check Azure Portal:** https://portal.azure.com
2. **View container logs:** Azure Portal > Container Instances > Your Container > Logs
3. **Test OpenAI key:** Run `python backend/test_openai_key.py` locally first
4. **Verify region:** Ensure you see "Southeast Asia" in Azure Portal

---

**Deployment Time:** ~15-20 minutes total
**Downtime:** ~5 minutes (during DNS propagation)
**Cost Impact:** $0 (same pricing as East Asia)

Good luck! 🚀
