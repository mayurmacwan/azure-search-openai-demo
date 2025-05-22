#!/bin/bash

# Check if all required parameters are provided
if [ $# -lt 2 ]; then
    echo "Usage: $0 <resource_group> <webapp_name> [location]"
    echo "  resource_group: The name of the Azure resource group"
    echo "  webapp_name: The name of the Azure Web App"
    echo "  location: (Optional) The Azure region (default: eastus)"
    exit 1
fi

RESOURCE_GROUP=$1
WEBAPP_NAME=$2
LOCATION=${3:-"eastus"}

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

# Check if App Service Plan exists, create if not
ASP_NAME="${WEBAPP_NAME}-plan"
if [ -z "$(az appservice plan list --query "[?name=='$ASP_NAME'].name" -o tsv)" ]; then
    echo "Creating App Service Plan '$ASP_NAME'..."
    az appservice plan create --name $ASP_NAME --resource-group $RESOURCE_GROUP --sku B1 --is-linux
    echo "App Service Plan created."
fi

# Check if Web App exists, create if not
if [ -z "$(az webapp list --query "[?name=='$WEBAPP_NAME'].name" -o tsv)" ]; then
    echo "Creating Web App '$WEBAPP_NAME'..."
    az webapp create --name $WEBAPP_NAME --resource-group $RESOURCE_GROUP --plan $ASP_NAME --runtime "PYTHON:3.10"
    echo "Web App created."
fi

# Make sure we're in the right directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

# Create deployment package for the backend
echo "Creating deployment package for the backend..."
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

# Copy backend files
BACKEND_DIR="$ROOT_DIR/app/backend"
cp -r "$BACKEND_DIR"/* "$TEMP_DIR/"

# Create web.config for Azure Web App
cat > "$TEMP_DIR/web.config" << EOL
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <system.webServer>
    <handlers>
      <add name="PythonHandler" path="*" verb="*" modules="httpPlatformHandler" resourceType="Unspecified"/>
    </handlers>
    <httpPlatform processPath="%home%\site\wwwroot\env\Scripts\python.exe"
                  arguments="%home%\site\wwwroot\main.py"
                  stdoutLogEnabled="true"
                  stdoutLogFile="%home%\LogFiles\python.log"
                  startupTimeLimit="60"
                  processesPerApplication="16">
      <environmentVariables>
        <environmentVariable name="PYTHONPATH" value="%home%\site\wwwroot"/>
      </environmentVariables>
    </httpPlatform>
  </system.webServer>
</configuration>
EOL

# Create startup script for Web App
cat > "$TEMP_DIR/startup.sh" << EOL
#!/bin/bash
cd \$HOME/site/wwwroot
pip install -r requirements.txt
exec python -m uvicorn main:app --port 8000 --host 0.0.0.0
EOL
chmod +x "$TEMP_DIR/startup.sh"

# Create ZIP file for deployment
ZIP_FILE="$TEMP_DIR/deploy.zip"
cd "$TEMP_DIR"
zip -r "$ZIP_FILE" .

# Deploy to Azure Web App
echo "Deploying backend to Azure Web App..."
az webapp deployment source config-zip --resource-group $RESOURCE_GROUP --name $WEBAPP_NAME --src "$ZIP_FILE"

# Configure CORS for the Web App
echo "Configuring CORS for the Web App..."
az webapp cors add --resource-group $RESOURCE_GROUP --name $WEBAPP_NAME --allowed-origins "*"

# Display deployment information
WEBAPP_URL=$(az webapp show --name $WEBAPP_NAME --resource-group $RESOURCE_GROUP --query "defaultHostName" -o tsv)
echo "Deployment completed successfully!"
echo "Backend API URL: https://$WEBAPP_URL"
echo "Now deploy your frontend to a static hosting service and set VITE_API_BASE_URL to https://$WEBAPP_URL" 