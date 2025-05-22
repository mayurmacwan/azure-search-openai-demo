# SPA Deployment Guide for Azure Search OpenAI Demo

This guide provides instructions for running the Azure Search OpenAI Demo application locally or deploying it as a Single Page Application (SPA) with an Azure Web App backend.

## Prerequisites

- [Node.js 20+](https://nodejs.org/)
- [Python 3.9-3.11](https://www.python.org/downloads/)
- [Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli)
- Azure Subscription with existing deployed services:
  - Azure OpenAI Service
  - Azure AI Search
  - Azure Blob Storage
  - Azure Document Intelligence
  - (Optional) Azure Cosmos DB for chat history

## Running Locally

### Option 1: Using the Start Scripts

The simplest way to run the application locally is to use the provided start scripts:

**On Windows:**
```
.\app\start.ps1
```

**On macOS/Linux:**
```
./app/start.sh
```

This will:
1. Create a Python virtual environment
2. Install backend dependencies
3. Install and build the frontend
4. Start the application at http://localhost:50505

### Option 2: Manual Setup

For more control over the setup process:

1. Set up the Python virtual environment:
   ```
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r app/backend/requirements.txt
   ```

2. Set up the frontend:
   ```
   cd app/frontend
   npm install
   npm run build
   ```

3. Start the backend server:
   ```
   cd ../backend
   python -m quart --app main:app run --port 50505 --host localhost --reload
   ```

## Deploying as a SPA with Azure Web App Backend

This repository includes scripts to deploy:
1. The backend to Azure Web App
2. The frontend to Azure Storage Static Website

### Step 1: Deploy the Backend to Azure Web App

**On Windows:**
```powershell
.\scripts\deploy-webapp.ps1 -ResourceGroup "your-resource-group" -WebAppName "your-webapp-name"
```

**On macOS/Linux:**
```bash
./scripts/deploy-webapp.sh your-resource-group your-webapp-name
```

This will create or update:
- Azure Resource Group (if it doesn't exist)
- App Service Plan
- Web App with Python 3.10 runtime

The script will output the URL of your deployed backend API.

### Step 2: Deploy the Frontend to Azure Storage Static Website

```bash
./scripts/deploy-frontend-spa.sh your-resource-group your-storage-account-name https://your-webapp-name.azurewebsites.net
```

This will:
1. Create a Storage Account with static website hosting enabled
2. Build the frontend with the correct API URL configuration
3. Upload the built frontend to the Storage Account

The script will output the URL of your SPA frontend.

### Step 3: Configure Environment Variables

For the backend Web App, you need to configure environment variables to connect to your Azure services. Set the following in the Azure Portal or using Azure CLI:

```bash
az webapp config appsettings set --name your-webapp-name --resource-group your-resource-group --settings \
  AZURE_SEARCH_SERVICE= \
  AZURE_SEARCH_INDEX= \
  AZURE_SEARCH_KEY= \
  AZURE_STORAGE_ACCOUNT= \
  AZURE_STORAGE_CONTAINER= \
  AZURE_STORAGE_KEY= \
  AZURE_OPENAI_SERVICE= \
  AZURE_OPENAI_API_KEY= \
  AZURE_OPENAI_CHATGPT_DEPLOYMENT= \
  AZURE_OPENAI_EMBEDDING_DEPLOYMENT= \
  DEPLOYMENT_MODE=SPA
```

Replace the empty values with your actual service information.

## Advanced Configuration

### Enabling CDN for Better Performance

For production environments, consider adding Azure CDN in front of your static website:

```bash
az cdn profile create --name your-cdn-profile --resource-group your-resource-group --sku Standard_Microsoft
az cdn endpoint create --name your-cdn-endpoint --profile-name your-cdn-profile --resource-group your-resource-group --origin your-storage-account.z13.web.core.windows.net --origin-host-header your-storage-account.z13.web.core.windows.net --enable-compression
```

### Custom Domain and HTTPS

To add a custom domain and HTTPS to your static website:

1. Configure a custom domain in Azure CDN
2. Enable HTTPS on the CDN endpoint

## Troubleshooting

### CORS Issues

If you encounter CORS issues:

1. Ensure the Web App has `DEPLOYMENT_MODE=SPA` set in the application settings
2. Check that the frontend is correctly configured with the backend API URL
3. Verify the CORS settings in the Web App allow your frontend domain

### Authentication Issues

If you're using authentication:

1. Configure authentication in the Azure Web App settings
2. Update the frontend auth configuration to match

## Additional Resources

- [Azure Web Apps Documentation](https://docs.microsoft.com/en-us/azure/app-service/)
- [Azure Storage Static Website Hosting](https://docs.microsoft.com/en-us/azure/storage/blobs/storage-blob-static-website)
- [Azure CDN Documentation](https://docs.microsoft.com/en-us/azure/cdn/) 