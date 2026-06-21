# 🚀 Quick Deployment Commands

## Option 1: Automated Script (Recommended)

### Windows (PowerShell)

```powershell
# 1. Edit redeploy.ps1 and update the configuration variables at the top
# 2. Run:
.\redeploy.ps1
```

### Linux/Mac (Bash)

```bash
# 1. Edit redeploy.sh and update the configuration variables at the top
# 2. Run:
chmod +x redeploy.sh
./redeploy.sh
```

---

## Option 2: Manual Commands (Step by Step)

### Prerequisites

```bash
# Install Azure CLI (if not installed)
# Windows: https://aka.ms/installazurecliwindows
# Mac: brew install azure-cli
# Linux: curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Login
az login

# Set subscription (if you have multiple)
az account set --subscription "YOUR_SUBSCRIPTION_ID"
```

### 1. Delete Old Deployment

```bash
# List resource groups to find yours
az group list --output table

# Delete old resource group (WARNING: Deletes everything in it!)
az group delete --name "YOUR_OLD_RESOURCE_GROUP" --yes --no-wait
```

### 2. Create New Resources in Southeast Asia

```bash
# Set variables
RESOURCE_GROUP="customersetu-backend-rg"
LOCATION="southeastasia"
ACR_NAME="customersetuacr"
CONTAINER_NAME="customersetu-backend"
IMAGE_NAME="customersetu-backend"

# Create resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create container registry
az acr create --resource-group $RESOURCE_GROUP --name $ACR_NAME --sku Basic --location $LOCATION
```

### 3. Build and Push Docker Image

```bash
# Build and push to ACR
cd backend
az acr build --registry $ACR_NAME --image $IMAGE_NAME:latest .
cd ..

# Get ACR credentials
ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query "passwords[0].value" -o tsv)
ACR_LOGIN_SERVER=$(az acr show --name $ACR_NAME --query loginServer -o tsv)
```

### 4. Deploy Container Instance

```bash
# Create container with environment variables
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
    OPENAI_API_KEY="YOUR_KEY" \
    SUPABASE_KEY="YOUR_KEY" \
    API_KEY="YOUR_KEY" \
    CORS_ALLOWED_ORIGINS="*"
```

### 5. Get Backend URL

```bash
az container show --resource-group $RESOURCE_GROUP --name $CONTAINER_NAME --query ipAddress.fqdn -o tsv
```

### 6. Update Frontend

```bash
cd frontend

# Create/update .env.production
echo "VITE_API_URL=https://YOUR_BACKEND_URL" > .env.production

# Build and deploy
npm run build
# Then deploy to Azure Static Web Apps via portal or CLI
```

---

## Verification Commands

```bash
# Check container status
az container show --resource-group $RESOURCE_GROUP --name $CONTAINER_NAME --query instanceView.state

# View logs
az container logs --resource-group $RESOURCE_GROUP --name $CONTAINER_NAME --follow

# Test health endpoint
curl https://YOUR_BACKEND_URL/health

# Test OpenAI connectivity from container
az container exec --resource-group $RESOURCE_GROUP --name $CONTAINER_NAME --exec-command "/bin/bash"
# Inside container:
curl -H "Authorization: Bearer $OPENAI_API_KEY" https://api.openai.com/v1/models
```

---

## Troubleshooting Commands

```bash
# Restart container
az container restart --resource-group $RESOURCE_GROUP --name $CONTAINER_NAME

# Check environment variables
az container show --resource-group $RESOURCE_GROUP --name $CONTAINER_NAME --query containers[0].environmentVariables

# Delete and recreate container
az container delete --resource-group $RESOURCE_GROUP --name $CONTAINER_NAME --yes
# Then run the create command again

# Check all resources in region
az resource list --location southeastasia --output table
```

---

## Cost Management

```bash
# Check current costs
az consumption usage list --output table

# Set budget alert (optional)
az consumption budget create \
  --budget-name "customersetu-budget" \
  --amount 100 \
  --time-grain Monthly \
  --start-date 2026-05-01 \
  --end-date 2027-05-01
```

---

## Cleanup (Delete Everything)

```bash
# Delete entire resource group
az group delete --name $RESOURCE_GROUP --yes --no-wait

# Verify deletion
az group list --output table
```

---

## Environment Variables Reference

Required environment variables for container:

```bash
OPENAI_API_KEY="sk-proj-..."
OPENAI_VISION_MODEL="gpt-4o"
OPENAI_EMBEDDING_MODEL="text-embedding-3-small"
OPENAI_EMBEDDING_DIMENSION="512"
SUPABASE_URL="https://cmsjeupljkgfmodrlosf.supabase.co"
SUPABASE_KEY="eyJhbGci..."
SUPABASE_STORAGE_BUCKET="complaint-images"
TESSERACT_CMD="/usr/bin/tesseract"
APP_ENV="production"
API_V1_PREFIX="/api/v1"
API_KEY="your-api-key"
RATE_LIMIT_PER_MINUTE="1000"
DUPLICATE_THRESHOLD="0.92"
MAX_FILE_SIZE_MB="10"
GEMINI_API_KEY="AIzaSy..."
SMTP_HOST="smtp.gmail.com"
SMTP_PORT="587"
SMTP_USER="unionbank.complaints.demo@gmail.com"
SMTP_PASSWORD="qzwr..."
EMAIL_FROM_ADDRESS="unionbank.complaints.demo@gmail.com"
TIER_TEMPLATES_PATH="app/templates/tier_responses/"
ENABLE_AUTO_KB_ENRICHMENT="true"
KB_ENRICHMENT_DELAY_HOURS="24"
NOTIFICATION_RETRY_COUNT="3"
NOTIFICATION_TIMEOUT_SECONDS="10"
DB_HOST="db.cmsjeupljkgfmodrlosf.supabase.co"
DB_PORT="5432"
DB_NAME="postgres"
DB_USER="postgres"
DB_PASSWORD="pCg16..."
TWILIO_ACCOUNT_SID="AC05cf..."
TWILIO_AUTH_TOKEN="f88031..."
TWILIO_WHATSAPP_NUMBER="whatsapp:+14155238886"
WEBHOOK_BASE_URL="https://customersetu-backend.southeastasia.azurecontainer.io"
CORS_ALLOWED_ORIGINS="*"
```

---

## Expected Timeline

- **Delete old deployment:** 2-5 minutes
- **Create new resources:** 3-5 minutes
- **Build Docker image:** 10-15 minutes (first time)
- **Deploy container:** 2-3 minutes
- **Total:** ~20-30 minutes

---

## Success Indicators

✅ Container status: "Running"
✅ Health endpoint returns 200 OK
✅ OpenAI API calls succeed (no geo-restriction errors)
✅ Agents complete with "status": "complete"
✅ Confidence scores > 70%
✅ No "unsupported_country_region_territory" errors in logs

---

## Support Resources

- **Azure Portal:** https://portal.azure.com
- **Azure CLI Docs:** https://learn.microsoft.com/en-us/cli/azure/
- **Container Instances Docs:** https://learn.microsoft.com/en-us/azure/container-instances/
- **OpenAI Supported Regions:** https://platform.openai.com/docs/supported-countries
