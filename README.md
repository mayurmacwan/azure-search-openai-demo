# QRChat - Chatbot

This project is a chatbot built with:
- **Frontend**: React + TypeScript (Vite)
- **Backend**: Python Azure Functions
- **LLM**: Azure OpenAI
- **Orchestration**: Langchain
- **Search**: Bing Search API

## Prerequisites

- [Node.js](https://nodejs.org/) (LTS version recommended)
- [Python](https://www.python.org/downloads/) (3.9+ recommended)
- [Azure Functions Core Tools](https://learn.microsoft.com/en-us/azure/azure-functions/functions-run-local)
- An Azure account with an active subscription. If you don't have one, create a [free account](https://azure.microsoft.com/free/?WT.mc_id=A261C142F).
- Access to Azure OpenAI service. Request access [here](https://aka.ms/oai/access).
- Bing Search API key. Create a Bing Search resource in the [Azure portal](https://portal.azure.com/).

## Setup Instructions

### 1. Clone the Repository (if applicable)

```bash
git clone <repository-url>
cd qrchat
```

### 2. Configure Azure Services

#### Azure OpenAI

1.  **Create an Azure OpenAI Resource:**
    Follow the instructions [here](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/create-resource?pivots=web-portal) to create an Azure OpenAI service resource.
2.  **Deploy a Model:**
    Deploy a chat model (e.g., `gpt-35-turbo` or `gpt-4`). Note down the **deployment name**.
3.  **Get Credentials:**
    From your Azure OpenAI resource in the Azure portal, navigate to "Keys and Endpoint". Note down the **API Key** and **Endpoint URL**.
    
#### Bing Search API

1.  **Create a Bing Search Resource:**
    In the Azure portal, create a Bing Search v7 resource.
2.  **Get API Key:**
    After creation, go to "Keys and Endpoint" and note down one of the API keys.
4.  **Update Backend Settings:**
    Open `backend/local.settings.json` and fill in your Azure OpenAI details:

    ```json
    {
      "IsEncrypted": false,
      "Values": {
        "AzureWebJobsStorage": "", // Optional: for Azure Storage emulator or actual storage account if needed by other functions
        "FUNCTIONS_WORKER_RUNTIME": "python",
        "AZURE_OPENAI_API_KEY": "YOUR_AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT": "YOUR_AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_DEPLOYMENT_NAME": "YOUR_AZURE_OPENAI_DEPLOYMENT_NAME",
        "AZURE_OPENAI_API_VERSION": "2023-05-15", // Or your desired API version
        "BING_SUBSCRIPTION_KEY": "YOUR_BING_SEARCH_API_KEY",
        "BING_SEARCH_URL": "https://api.bing.microsoft.com/v7.0/search" // Default Bing Search API URL
      }
    }
    ```
    **Note:** `AzureWebJobsStorage` can be left empty if you are only running this simple HTTP-triggered function and not using features like timers or durable functions that require storage. For local development without the Azure Storage Emulator, you might see a warning, but the HTTP trigger should still work.

### 3. Backend Setup (Python - Azure Functions)

1.  **Navigate to the backend directory:**
    ```bash
    cd backend
    ```
2.  **Create and activate a Python virtual environment:**
    ```bash
    python3.11 -m venv .venv
    ```
    *   On Windows:
        ```bash
        .venv\Scripts\activate
        ```
    *   On macOS/Linux:
        ```bash
        source .venv/bin/activate
        ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Run the Azure Functions locally:**
    ```bash
    func start
    ```
    The backend API should now be running, typically at `http://localhost:7071/api/chat`.

### 4. Frontend Setup (React + TypeScript - Vite)

1.  **Navigate to the frontend directory (from the project root):**
    ```bash
    cd ../frontend 
    # Or if you are in the project root: cd frontend
    ```
2.  **Install dependencies (if you haven't already):
    ```bash
    npm install
    ```
3.  **Configure Environment Variables (Optional for local development):**
    For local development, the frontend will use the proxy configuration to connect to your local Azure Functions. However, if you want to connect directly to deployed Azure Functions, create a `.env.local` file in the frontend directory:
    ```bash
    # .env.local
    VITE_API_BASE_URL=https://your-function-app-name.azurewebsites.net/api
    VITE_FUNCTION_KEY=your-function-key-here
    VITE_ENVIRONMENT=production
    ```
    
    **Note:** For production deployment, these environment variables should be configured in Azure Static Web Apps configuration, not in local files.

4.  **Run the Vite development server:**
    ```bash
    npm run dev
    ```
    The frontend application should now be running, typically at `http://localhost:5173` (Vite's default port, but it might choose another if 5173 is busy).

## Accessing the Chatbot

Once both the backend and frontend are running:

1.  Open your web browser.
2.  Navigate to the address provided by the Vite development server (e.g., `http://localhost:5173`).

You should see the chat interface and be able to interact with the chatbot.

## Production Deployment

### Azure Functions Authentication

The Azure Functions are configured with function-level authentication (`auth_level=func.AuthLevel.FUNCTION`). This means they require a function key to access them in production.

### Frontend Environment Variables (Azure Static Web Apps)

For production deployment, configure these environment variables in Azure Static Web Apps:

- `VITE_API_BASE_URL`: The base URL of your Azure Functions (e.g., `https://internal-gpt-fn-v2.azurewebsites.net/api`)
- `VITE_FUNCTION_KEY`: The function key from your Azure Functions App Keys section
- `VITE_ENVIRONMENT`: Set to `production`

### How to Get the Function Key

1. Go to your Azure Functions in the Azure Portal
2. Navigate to Functions → App keys
3. Copy the default function key or create a new one
4. Use this key in the `VITE_FUNCTION_KEY` environment variable

## Troubleshooting

-   **CORS Issues:** The `backend/function_app.py` includes basic CORS headers (`Access-Control-Allow-Origin: *`) for local development. The Vite proxy in `frontend/vite.config.ts` should handle requests from the frontend to the backend. If you encounter CORS issues when deploying, you'll need to configure CORS settings appropriately in your Azure Function App.
-   **Azure Functions Core Tools:** Ensure they are installed and up to date.
-   **Environment Variables:** Double-check that all `AZURE_OPENAI_*` variables in `local.settings.json` are correctly set.
-   **Python/Node Versions:** Ensure you are using compatible versions of Python, Node.js, and associated package managers.
