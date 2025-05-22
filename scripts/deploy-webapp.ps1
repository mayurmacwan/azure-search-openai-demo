param(
    [Parameter(Mandatory=$true)]
    [string]$ResourceGroup,
    
    [Parameter(Mandatory=$true)]
    [string]$WebAppName,
    
    [Parameter(Mandatory=$false)]
    [string]$Location = "East US"
)

# Check if Azure CLI is installed
try {
    az --version | Out-Null
} catch {
    Write-Error "Azure CLI is not installed. Please install it from https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
}

# Check if user is logged in to Azure
$loginStatus = az account show --query "name" -o tsv 2>$null
if (-not $loginStatus) {
    Write-Host "You are not logged in to Azure. Initiating login..."
    az login
}

# Check if resource group exists, create if not
$rgExists = az group exists --name $ResourceGroup
if ($rgExists -eq "false") {
    Write-Host "Resource group '$ResourceGroup' does not exist. Creating..."
    az group create --name $ResourceGroup --location $Location
    Write-Host "Resource group created."
}

# Check if App Service Plan exists, create if not
$aspName = "$WebAppName-plan"
$aspExists = az appservice plan list --query "[?name=='$aspName'].name" -o tsv
if (-not $aspExists) {
    Write-Host "Creating App Service Plan '$aspName'..."
    az appservice plan create --name $aspName --resource-group $ResourceGroup --sku B1 --is-linux
    Write-Host "App Service Plan created."
}

# Check if Web App exists, create if not
$webAppExists = az webapp list --query "[?name=='$WebAppName'].name" -o tsv
if (-not $webAppExists) {
    Write-Host "Creating Web App '$WebAppName'..."
    az webapp create --name $WebAppName --resource-group $ResourceGroup --plan $aspName --runtime "PYTHON:3.10"
    Write-Host "Web App created."
}

# Make sure we're in the right directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = Split-Path -Parent $scriptDir
Set-Location $rootDir

# Create deployment package for the backend
Write-Host "Creating deployment package for the backend..."
$tempDir = Join-Path $env:TEMP "azure-search-openai-deploy"
if (Test-Path $tempDir) {
    Remove-Item $tempDir -Recurse -Force
}
New-Item -ItemType Directory -Path $tempDir | Out-Null

# Copy backend files
$backendDir = Join-Path $rootDir "app/backend"
Copy-Item -Path "$backendDir/*" -Destination $tempDir -Recurse

# Create web.config for Azure Web App
$webConfig = @"
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
"@
$webConfig | Out-File -FilePath "$tempDir/web.config" -Encoding utf8

# Create startup script for Web App
$startupScript = @"
#!/bin/bash
cd \$HOME/site/wwwroot
pip install -r requirements.txt
exec python -m uvicorn main:app --port 8000 --host 0.0.0.0
"@
$startupScript | Out-File -FilePath "$tempDir/startup.sh" -Encoding utf8 -NoNewline

# Deploy to Azure Web App
Write-Host "Deploying backend to Azure Web App..."
az webapp deployment source config-zip --resource-group $ResourceGroup --name $WebAppName --src "$tempDir.zip"

# Configure CORS for the Web App
Write-Host "Configuring CORS for the Web App..."
az webapp cors add --resource-group $ResourceGroup --name $WebAppName --allowed-origins "*"

# Display deployment information
$webAppUrl = az webapp show --name $WebAppName --resource-group $ResourceGroup --query "defaultHostName" -o tsv
Write-Host "Deployment completed successfully!"
Write-Host "Backend API URL: https://$webAppUrl"
Write-Host "Now deploy your frontend to a static hosting service and set VITE_API_BASE_URL to https://$webAppUrl" 