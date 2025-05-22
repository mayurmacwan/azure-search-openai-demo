#!/bin/bash

# Check if all required parameters are provided
if [ $# -lt 3 ]; then
    echo "Usage: $0 <resource_group> <storage_account_name> <api_url>"
    echo "  resource_group: The name of the Azure resource group"
    echo "  storage_account_name: The name of the Azure Storage account for hosting the SPA"
    echo "  api_url: The URL of the backend API (e.g., https://myapp.azurewebsites.net)"
    exit 1
fi

RESOURCE_GROUP=$1
STORAGE_ACCOUNT_NAME=$2
API_URL=$3
LOCATION=${4:-"eastus"}

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo "Azure CLI is not installed. Please install it from https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi

# Check if user is logged in to Azure
if ! az account show --query "name" -o tsv &> /dev/null; then
    echo "You are not logged in to Azure. Initiating login..."
    az login
fi

# Check if resource group exists, create if not
if [ "$(az group exists --name $RESOURCE_GROUP)" = "false" ]; then
    echo "Resource group '$RESOURCE_GROUP' does not exist. Creating..."
    az group create --name $RESOURCE_GROUP --location $LOCATION
    echo "Resource group created."
fi

# Check if Storage Account exists, create if not
if [ -z "$(az storage account check-name --name $STORAGE_ACCOUNT_NAME --query "nameAvailable" -o tsv)" ] && 
   [ -z "$(az storage account list --query "[?name=='$STORAGE_ACCOUNT_NAME'].name" -o tsv)" ]; then
    echo "Creating Storage Account '$STORAGE_ACCOUNT_NAME'..."
    az storage account create \
        --name $STORAGE_ACCOUNT_NAME \
        --resource-group $RESOURCE_GROUP \
        --location $LOCATION \
        --sku Standard_LRS \
        --kind StorageV2 \
        --https-only true \
        --min-tls-version TLS1_2 \
        --enable-static-website
    echo "Storage Account created."
else
    echo "Enabling static website hosting on Storage Account '$STORAGE_ACCOUNT_NAME'..."
    az storage blob service-properties update \
        --account-name $STORAGE_ACCOUNT_NAME \
        --static-website \
        --index-document index.html \
        --404-document index.html
fi

# Make sure we're in the right directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR/app/frontend"

# Create .env file for frontend build
echo "Creating .env file with API URL configuration..."
echo "VITE_API_BASE_URL=$API_URL" > .env

# Install dependencies and build the frontend
echo "Installing frontend dependencies..."
npm install

echo "Building frontend..."
npm run build

# Deploy to Azure Storage
echo "Deploying frontend to Azure Storage Static Website..."
az storage blob upload-batch \
    --account-name $STORAGE_ACCOUNT_NAME \
    --source ./dist \
    --destination '$web' \
    --overwrite

# Display deployment information
WEBSITE_URL=$(az storage account show \
    --name $STORAGE_ACCOUNT_NAME \
    --query "primaryEndpoints.web" \
    --output tsv)

echo "Deployment completed successfully!"
echo "Frontend URL: $WEBSITE_URL"
echo "Backend API URL: $API_URL"

# Optionally configure CDN for better performance
echo "For better performance, consider setting up Azure CDN for your static website."
echo "Run: az cdn profile create --name $STORAGE_ACCOUNT_NAME-cdn --resource-group $RESOURCE_GROUP --sku Standard_Microsoft"
echo "Then: az cdn endpoint create --name $STORAGE_ACCOUNT_NAME --profile-name $STORAGE_ACCOUNT_NAME-cdn --resource-group $RESOURCE_GROUP --origin $STORAGE_ACCOUNT_NAME.z13.web.core.windows.net --origin-host-header $STORAGE_ACCOUNT_NAME.z13.web.core.windows.net --enable-compression" 