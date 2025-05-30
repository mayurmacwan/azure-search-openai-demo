import dataclasses
import io
import json
import logging
import mimetypes
import os
import uuid
import datetime
import tempfile
import time
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, Union, cast

from azure.cognitiveservices.speech import (
    ResultReason,
    SpeechConfig,
    SpeechSynthesisOutputFormat,
    SpeechSynthesisResult,
    SpeechSynthesizer,
)
from azure.core.exceptions import ResourceNotFoundError
from azure.identity.aio import (
    ManagedIdentityCredential,
    DefaultAzureCredential,
    ClientSecretCredential,
    get_bearer_token_provider,
)
from azure.monitor.opentelemetry import configure_azure_monitor
# Removed RAG-related imports as part of pure chatbot implementation
from azure.storage.blob.aio import ContainerClient
from azure.storage.blob.aio import StorageStreamDownloader as BlobDownloader
from azure.storage.filedatalake.aio import FileSystemClient
from azure.storage.filedatalake.aio import StorageStreamDownloader as DatalakeDownloader
from openai import AsyncAzureOpenAI, AsyncOpenAI
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware
from opentelemetry.instrumentation.httpx import (
    HTTPXClientInstrumentor,
)
from opentelemetry.instrumentation.openai import OpenAIInstrumentor
from quart import (
    Blueprint,
    Quart,
    abort,
    current_app,
    jsonify,
    make_response,
    request,
    send_file,
    send_from_directory,
)
from quart_cors import cors

from approaches.approach import Approach
from approaches.purechat import PureChatApproach
from approaches.promptmanager import PromptManager
from chat_history.cosmosdb import chat_history_cosmosdb_bp
from config import (
    CONFIG_ASK_APPROACH,
    CONFIG_AUTH_CLIENT,
    CONFIG_BLOB_CONTAINER_CLIENT,
    CONFIG_CHAT_APPROACH,
    CONFIG_CHAT_HISTORY_BROWSER_ENABLED,
    CONFIG_CHAT_HISTORY_COSMOS_ENABLED,
    CONFIG_CREDENTIAL,
    CONFIG_GPT4V_DEPLOYED,
    CONFIG_LANGUAGE_PICKER_ENABLED,
    CONFIG_OPENAI_CLIENT,
    CONFIG_SPEECH_INPUT_ENABLED,
    CONFIG_SPEECH_OUTPUT_AZURE_ENABLED,
    CONFIG_SPEECH_OUTPUT_BROWSER_ENABLED,
    CONFIG_SPEECH_SERVICE_ID,
    CONFIG_SPEECH_SERVICE_LOCATION,
    CONFIG_SPEECH_SERVICE_TOKEN,
    CONFIG_SPEECH_SERVICE_VOICE,
    CONFIG_STREAMING_ENABLED,
    CONFIG_USER_BLOB_CONTAINER_CLIENT,
    CONFIG_USER_UPLOAD_ENABLED,
)
from core.authentication import AuthenticationHelper
from core.mock_auth import MockAuthenticationHelper
from core.sessionhelper import create_session_id
from decorators import authenticated, authenticated_path
from error import error_dict, error_response
from prepdocs import (
    clean_key_if_exists,
    setup_embeddings_service,
    setup_file_processors,
)
from prepdocslib.filestrategy import UploadUserFileStrategy
from prepdocslib.listfilestrategy import File

bp = Blueprint("routes", __name__, static_folder="static")
# Fix Windows registry issue with mimetypes
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")


@bp.route("/")
async def index():
    return await bp.send_static_file("index.html")


# Empty page is recommended for login redirect to work.
# See https://github.com/AzureAD/microsoft-authentication-library-for-js/blob/dev/lib/msal-browser/docs/initialization.md#redirecturi-considerations for more information
@bp.route("/redirect")
async def redirect():
    return ""


@bp.route("/favicon.ico")
async def favicon():
    return await bp.send_static_file("favicon.ico")


@bp.route("/assets/<path:path>")
async def assets(path):
    return await send_from_directory(Path(__file__).resolve().parent / "static" / "assets", path)


@bp.route("/content/<path>")
@authenticated_path
async def content_file(path: str, auth_claims: dict[str, Any]):
    """
    Serve content files from blob storage from within the app to keep the example self-contained.
    *** NOTE *** if you are using app services authentication, this route will return unauthorized to all users that are not logged in
    if AZURE_ENFORCE_ACCESS_CONTROL is not set or false, logged in users can access all files regardless of access control
    if AZURE_ENFORCE_ACCESS_CONTROL is set to true, logged in users can only access files they have access to
    This is also slow and memory hungry.
    """
    # Remove page number from path, filename-1.txt -> filename.txt
    # This shouldn't typically be necessary as browsers don't send hash fragments to servers
    if path.find("#page=") > 0:
        path_parts = path.rsplit("#page=", 1)
        path = path_parts[0]
    current_app.logger.info("Opening file %s", path)
    blob_container_client: ContainerClient = current_app.config[CONFIG_BLOB_CONTAINER_CLIENT]
    blob: Union[BlobDownloader, DatalakeDownloader]
    try:
        blob = await blob_container_client.get_blob_client(path).download_blob()
    except ResourceNotFoundError:
        current_app.logger.info("Path not found in general Blob container: %s", path)
        if current_app.config[CONFIG_USER_UPLOAD_ENABLED]:
            try:
                user_oid = auth_claims["oid"]
                user_blob_container_client = current_app.config[CONFIG_USER_BLOB_CONTAINER_CLIENT]
                user_directory_client: FileSystemClient = user_blob_container_client.get_directory_client(user_oid)
                file_client = user_directory_client.get_file_client(path)
                blob = await file_client.download_file()
            except ResourceNotFoundError:
                current_app.logger.exception("Path not found in DataLake: %s", path)
                abort(404)
        else:
            abort(404)
    if not blob.properties or not blob.properties.has_key("content_settings"):
        abort(404)
    mime_type = blob.properties["content_settings"]["content_type"]
    if mime_type == "application/octet-stream":
        mime_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
    blob_file = io.BytesIO()
    await blob.readinto(blob_file)
    blob_file.seek(0)
    return await send_file(blob_file, mimetype=mime_type, as_attachment=False, attachment_filename=path)


@bp.route("/ask", methods=["POST"])
@authenticated
async def ask(auth_claims: dict[str, Any]):
    if not request.is_json:
        return jsonify({"error": "request must be json"}), 415
    request_json = await request.get_json()
    context = request_json.get("context", {})
    context["auth_claims"] = auth_claims
    try:
        # Use the pure chat approach
        approach = cast(Approach, current_app.config[CONFIG_CHAT_APPROACH])
        r = await approach.run(
            request_json["messages"], context=context, session_state=request_json.get("session_state")
        )
        return jsonify(r)
    except Exception as error:
        return error_response(error, "/ask")


class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o) and not isinstance(o, type):
            return dataclasses.asdict(o)
        return super().default(o)


async def format_as_ndjson(r: AsyncGenerator[dict, None]) -> AsyncGenerator[str, None]:
    try:
        async for event in r:
            yield json.dumps(event, ensure_ascii=False, cls=JSONEncoder) + "\n"
    except Exception as error:
        logging.exception("Exception while generating response stream: %s", error)
        yield json.dumps(error_dict(error))


@bp.route("/chat", methods=["POST"])
@authenticated
async def chat(auth_claims: dict[str, Any]):
    if not request.is_json:
        return jsonify({"error": "request must be json"}), 415
    request_json = await request.get_json()
    context = request_json.get("context", {})
    context["auth_claims"] = auth_claims
    try:
        # Use the pure chat approach
        approach = current_app.config[CONFIG_CHAT_APPROACH]

        # If session state is provided, persists the session state,
        # else creates a new session_id depending on the chat history options enabled.
        session_state = request_json.get("session_state")
        if session_state is None:
            session_state = create_session_id(
                current_app.config[CONFIG_CHAT_HISTORY_COSMOS_ENABLED],
                current_app.config[CONFIG_CHAT_HISTORY_BROWSER_ENABLED],
            )
        result = await approach.run_conversation(
            request_json["messages"],
            context.get("overrides", {}),
            auth_claims
        ) if isinstance(approach, current_app.config["ASSISTANT_CHAT_APPROACH"].__class__) else await approach.run(
            request_json["messages"],
            context=context,
            session_state=session_state,
        )
        return jsonify(result)
    except Exception as error:
        return error_response(error, "/chat")


@bp.route("/chat/stream", methods=["POST"])
@authenticated
async def chat_stream(auth_claims: dict[str, Any]):
    if not request.is_json:
        return jsonify({"error": "request must be json"}), 415
    request_json = await request.get_json()
    context = request_json.get("context", {})
    context["auth_claims"] = auth_claims
    try:
        # Use the pure chat approach
        approach = current_app.config[CONFIG_CHAT_APPROACH]

        # If session state is provided, persists the session state,
        # else creates a new session_id depending on the chat history options enabled.
        session_state = request_json.get("session_state")
        if session_state is None:
            session_state = create_session_id(
                current_app.config[CONFIG_CHAT_HISTORY_COSMOS_ENABLED],
                current_app.config[CONFIG_CHAT_HISTORY_BROWSER_ENABLED],
            )
            
        # Process the request for both new conversations and follow-ups
        result = await approach.run_stream(
            request_json["messages"],
            context=context,
            session_state=session_state,
        )
        response = await make_response(format_as_ndjson(result))
        response.timeout = None  # type: ignore
        response.mimetype = "application/json-lines"
        return response
    except Exception as error:
        return error_response(error, "/chat")


# Send MSAL.js settings to the client UI
@bp.route("/auth_setup", methods=["GET"])
def auth_setup():
    auth_helper = current_app.config[CONFIG_AUTH_CLIENT]
    return jsonify(auth_helper.get_auth_setup_for_client())


@bp.route("/config", methods=["GET"])
def config():
    return jsonify(
        {
            "showGPT4VOptions": False,
            "showSemanticRankerOption": False,
            "showQueryRewritingOption": False,
            "showReasoningEffortOption": False,
            "streamingEnabled": current_app.config[CONFIG_STREAMING_ENABLED],
            "defaultReasoningEffort": "",
            "showVectorOption": False,
            "showUserUpload": False,
            "showLanguagePicker": current_app.config[CONFIG_LANGUAGE_PICKER_ENABLED],
            "showSpeechInput": current_app.config[CONFIG_SPEECH_INPUT_ENABLED],
            "showSpeechOutputBrowser": current_app.config[CONFIG_SPEECH_OUTPUT_BROWSER_ENABLED],
            "showSpeechOutputAzure": current_app.config[CONFIG_SPEECH_OUTPUT_AZURE_ENABLED],
            "showChatHistoryBrowser": current_app.config[CONFIG_CHAT_HISTORY_BROWSER_ENABLED],
            "showChatHistoryCosmos": current_app.config[CONFIG_CHAT_HISTORY_COSMOS_ENABLED],
            "showAgenticRetrievalOption": False,
        }
    )


@bp.route("/speech", methods=["POST"])
async def speech():
    if not request.is_json:
        return jsonify({"error": "request must be json"}), 415

    speech_token = current_app.config.get(CONFIG_SPEECH_SERVICE_TOKEN)
    if speech_token is None or speech_token.expires_on < time.time() + 60:
        speech_token = await current_app.config[CONFIG_CREDENTIAL].get_token(
            "https://cognitiveservices.azure.com/.default"
        )
        current_app.config[CONFIG_SPEECH_SERVICE_TOKEN] = speech_token

    request_json = await request.get_json()
    text = request_json["text"]
    try:
        # Construct a token as described in documentation:
        # https://learn.microsoft.com/azure/ai-services/speech-service/how-to-configure-azure-ad-auth?pivots=programming-language-python
        auth_token = (
            "aad#"
            + current_app.config[CONFIG_SPEECH_SERVICE_ID]
            + "#"
            + current_app.config[CONFIG_SPEECH_SERVICE_TOKEN].token
        )
        speech_config = SpeechConfig(auth_token=auth_token, region=current_app.config[CONFIG_SPEECH_SERVICE_LOCATION])
        speech_config.speech_synthesis_voice_name = current_app.config[CONFIG_SPEECH_SERVICE_VOICE]
        speech_config.speech_synthesis_output_format = SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
        synthesizer = SpeechSynthesizer(speech_config=speech_config, audio_config=None)
        result: SpeechSynthesisResult = synthesizer.speak_text_async(text).get()
        if result.reason == ResultReason.SynthesizingAudioCompleted:
            return result.audio_data, 200, {"Content-Type": "audio/mp3"}
        elif result.reason == ResultReason.Canceled:
            cancellation_details = result.cancellation_details
            current_app.logger.error(
                "Speech synthesis canceled: %s %s", cancellation_details.reason, cancellation_details.error_details
            )
            raise Exception("Speech synthesis canceled. Check logs for details.")
        else:
            current_app.logger.error("Unexpected result reason: %s", result.reason)
            raise Exception("Speech synthesis failed. Check logs for details.")
    except Exception as e:
        current_app.logger.exception("Exception in /speech")
        return jsonify({"error": str(e)}), 500


@bp.post("/upload")
@authenticated
async def upload(auth_claims: dict[str, Any]):
    request_files = await request.files
    if "file" not in request_files:
        # If no files were included in the request, return an error response
        return jsonify({"message": "No file part in the request", "status": "failed"}), 400

    # Use a default user ID for unauthenticated uploads
    user_oid = auth_claims.get("oid", "public-user")
    file = request_files.getlist("file")[0]
    user_blob_container_client: FileSystemClient = current_app.config[CONFIG_USER_BLOB_CONTAINER_CLIENT]
    user_directory_client = user_blob_container_client.get_directory_client(user_oid)
    try:
        await user_directory_client.get_directory_properties()
    except ResourceNotFoundError:
        current_app.logger.info("Creating directory for user %s", user_oid)
        await user_directory_client.create_directory()
    await user_directory_client.set_access_control(owner=user_oid)
    file_client = user_directory_client.get_file_client(file.filename)
    file_io = file
    file_io.name = file.filename
    file_io = io.BufferedReader(file_io)
    await file_client.upload_data(file_io, overwrite=True, metadata={"UploadedBy": user_oid})
    
    # Save file to the data directory for prepdocs.sh processing
    temp_file_path = os.path.join("data", file.filename)
    file_io.seek(0)
    with open(temp_file_path, "wb") as f:
        f.write(file_io.read())
    
    # Run prepdocs.sh as a background process
    import subprocess
    if os.name == 'nt':  # Windows
        subprocess.Popen(["powershell", "-File", "scripts/prepdocs.ps1"], shell=True)
    else:  # Linux/Mac
        subprocess.Popen(["bash", "scripts/prepdocs.sh"], shell=True)
        
    # Also use the standard strategy to handle the file with user ACLs
    file_io.seek(0)
    ingester: UploadUserFileStrategy = current_app.config[CONFIG_INGESTER]
    await ingester.add_file(File(content=file_io, acls={"oids": [user_oid]}, url=file_client.url))
    
    return jsonify({"message": "File uploaded successfully and queued for processing"}), 200


@bp.post("/delete_uploaded")
@authenticated
async def delete_uploaded(auth_claims: dict[str, Any]):
    request_json = await request.get_json()
    filename = request_json.get("filename")
    user_oid = auth_claims["oid"]
    user_blob_container_client: FileSystemClient = current_app.config[CONFIG_USER_BLOB_CONTAINER_CLIENT]
    user_directory_client = user_blob_container_client.get_directory_client(user_oid)
    file_client = user_directory_client.get_file_client(filename)
    await file_client.delete_file()
    ingester = current_app.config[CONFIG_INGESTER]
    await ingester.remove_file(filename, user_oid)
    return jsonify({"message": f"File {filename} deleted successfully"}), 200


@bp.get("/list_uploaded")
@authenticated
async def list_uploaded(auth_claims: dict[str, Any]):
    user_oid = auth_claims["oid"]
    user_blob_container_client: FileSystemClient = current_app.config[CONFIG_USER_BLOB_CONTAINER_CLIENT]
    files = []
    try:
        all_paths = user_blob_container_client.get_paths(path=user_oid)
        async for path in all_paths:
            files.append(path.name.split("/", 1)[1])
    except ResourceNotFoundError as error:
        if error.status_code != 404:
            current_app.logger.exception("Error listing uploaded files", error)
    return jsonify(files), 200


@bp.post("/run_prepdocs")
@authenticated
async def run_prepdocs(auth_claims: dict[str, Any]):
    # Optional: Check if the user has admin privileges
    # For example, by checking if they're in a specific admin group
    # if "admin_group_id" not in auth_claims.get("groups", []):
    #     return jsonify({"message": "Unauthorized. Admin privileges required."}), 403
    
    try:
        import subprocess
        import os
        
        # Run prepdocs.sh as a background process
        if os.name == 'nt':  # Windows
            process = subprocess.Popen(["powershell", "-File", "scripts/prepdocs.ps1"], 
                                      stdout=subprocess.PIPE, 
                                      stderr=subprocess.PIPE,
                                      shell=True)
        else:  # Linux/Mac
            process = subprocess.Popen(["bash", "scripts/prepdocs.sh"], 
                                      stdout=subprocess.PIPE, 
                                      stderr=subprocess.PIPE,
                                      shell=True)
        
        # For a real app, you might want to capture the process ID and status
        # and provide a way to check on the status later
        return jsonify({
            "message": "Document processing started", 
            "process_id": process.pid
        }), 200
    except Exception as e:
        current_app.logger.exception("Error running prepdocs script")
        return jsonify({"message": f"Error running document processing: {str(e)}"}), 500


@bp.post("/upload_no_auth")
async def upload_no_auth():
    """Upload endpoint that doesn't require authentication and stores files for document Q&A"""
    try:
        # Log OpenAI configuration for debugging
        try:
            openai_client: AsyncOpenAI = current_app.config[CONFIG_OPENAI_CLIENT]
            current_app.logger.info(f"OpenAI client type: {type(openai_client).__name__}")
            current_app.logger.info(f"OpenAI base URL: {openai_client.base_url}")
        except Exception as log_error:
            current_app.logger.warning(f"Could not log OpenAI client details: {str(log_error)}")
        
        request_files = await request.files
        if "file" not in request_files:
            # If no files were included in the request, return an error response
            return jsonify({"message": "No file part in the request", "status": "failed"}), 400

        file = request_files.getlist("file")[0]
        
        # Check file size (limit to 10MB)
        file_content = file.read()
        file_size = len(file_content)
        if file_size > 10 * 1024 * 1024:  # 10MB in bytes
            return jsonify({"message": "File size exceeds 10MB limit", "status": "failed"}), 413
        
        # Reset file pointer
        file.seek(0)
        
        # Create a temporary file for processing
        temp_file_path = ""
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name
        
        try:
            # Extract text from the file based on file type
            file_extension = os.path.splitext(file.filename)[1].lower()
            extracted_text = ""
            
            # Process different file types
            if file_extension in [".txt", ".md"]:
                # For text files, just read the content
                with open(temp_file_path, "r", encoding="utf-8", errors="ignore") as f:
                    extracted_text = f.read()
            elif file_extension == ".pdf":
                # For PDFs, use PyPDF2 or similar library
                try:
                    import PyPDF2
                    with open(temp_file_path, "rb") as f:
                        pdf_reader = PyPDF2.PdfReader(f)
                        for page_num in range(len(pdf_reader.pages)):
                            page = pdf_reader.pages[page_num]
                            extracted_text += page.extract_text() + "\n\n"
                except ImportError:
                    current_app.logger.warning("PyPDF2 not installed, using basic text extraction")
                    extracted_text = f"[PDF content from {file.filename}] - Install PyPDF2 for better extraction"
            elif file_extension in [".docx"]:
                # For Word documents
                try:
                    import docx
                    doc = docx.Document(temp_file_path)
                    extracted_text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
                except ImportError:
                    current_app.logger.warning("python-docx not installed, using basic text extraction")
                    extracted_text = f"[DOCX content from {file.filename}] - Install python-docx for better extraction"
            else:
                # For other file types, just note the file was uploaded
                extracted_text = f"[Content from {file.filename} - file type {file_extension} not directly supported for text extraction]"
            
            # Generate a unique file ID
            file_id = str(uuid.uuid4())
            
            # Save the extracted text and metadata
            # Fix: Use the same data directory path as in PureChatApproach
            data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
            os.makedirs(data_dir, exist_ok=True)
            print(f"Saving uploaded file to data directory: {data_dir}")
            
            # Save the original file
            file_path = os.path.join(data_dir, file.filename)
            current_app.logger.info(f"Saving original file to: {file_path}")
            with open(file_path, "wb") as f:
                f.write(file_content)
            
            # Save the extracted text
            text_file_path = os.path.join(data_dir, f"{file_id}.txt")
            with open(text_file_path, "w", encoding="utf-8") as f:
                f.write(extracted_text)
            
            # Save metadata about the file
            metadata = {
                "file_id": file_id,
                "filename": file.filename,
                "upload_time": datetime.datetime.now().isoformat(),
                "size": file_size,
                "text_path": text_file_path
            }
            
            # Store metadata in a JSON file
            metadata_path = os.path.join(data_dir, f"{file_id}.json")
            with open(metadata_path, "w") as f:
                json.dump(metadata, f)
            
            # Store the file ID in the app config for later use
            # If we don't have a list of uploaded files yet, create one
            if "UPLOADED_FILES" not in current_app.config:
                current_app.config["UPLOADED_FILES"] = []
            
            # Add this file to the list
            current_app.config["UPLOADED_FILES"].append(metadata)
            current_app.logger.info(f"Added file {file.filename} with ID {file_id} to uploaded files list")
            
            # Skip blob storage upload - we only need the local files for chat
            current_app.logger.info(f"File saved locally, skipping blob storage upload")
            
            return jsonify({
                "message": f"File {file.filename} uploaded successfully", 
                "status": "success",
                "file_id": file_id,
                "extracted_text_length": len(extracted_text)
            }), 200
                
        except Exception as process_error:
            current_app.logger.exception(f"Error processing file: {str(process_error)}")
            return jsonify({
                "message": f"Error processing file: {str(process_error)}", 
                "status": "failed"
            }), 500
        finally:
            # Clean up the temporary file
            if temp_file_path and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
            
    except Exception as e:
        current_app.logger.exception(f"Exception in upload_no_auth: {str(e)}")
        return jsonify({"message": f"Error uploading file: {str(e)}", "status": "failed"}), 500


@bp.before_app_serving
async def load_existing_documents():
    """Load existing documents from the data directory"""
    try:
        # Define the data directory path
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        
        # Check if the directory exists
        if not os.path.exists(data_dir):
            current_app.logger.info(f"Data directory {data_dir} does not exist, creating it")
            os.makedirs(data_dir, exist_ok=True)
            return
        
        # Look for JSON metadata files
        current_app.logger.info(f"Scanning data directory {data_dir} for document metadata")
        metadata_files = [f for f in os.listdir(data_dir) if f.endswith(".json") and not f.startswith(".")]
        
        if not metadata_files:
            current_app.logger.info("No document metadata files found in data directory")
            return
        
        # Initialize the uploaded files list if it doesn't exist
        if "UPLOADED_FILES" not in current_app.config:
            current_app.config["UPLOADED_FILES"] = []
        
        # Load metadata from each file
        for metadata_file in metadata_files:
            try:
                metadata_path = os.path.join(data_dir, metadata_file)
                with open(metadata_path, "r") as f:
                    metadata = json.load(f)
                
                # Check if the text file exists
                text_path = metadata.get("text_path")
                if text_path and os.path.exists(text_path):
                    # Add to the uploaded files list if not already there
                    file_id = metadata.get("file_id")
                    if file_id and not any(f.get("file_id") == file_id for f in current_app.config["UPLOADED_FILES"]):
                        current_app.config["UPLOADED_FILES"].append(metadata)
                        current_app.logger.info(f"Loaded document metadata for {metadata.get('filename')} (ID: {file_id})")
            except Exception as e:
                current_app.logger.error(f"Error loading document metadata from {metadata_file}: {str(e)}")
        
        current_app.logger.info(f"Loaded {len(current_app.config['UPLOADED_FILES'])} documents from data directory")
    except Exception as e:
        current_app.logger.error(f"Error loading existing documents: {str(e)}")

@bp.before_app_serving
async def setup_clients():
    # Replace these with your own values, either in environment variables or directly here
    AZURE_STORAGE_ACCOUNT = os.environ["AZURE_STORAGE_ACCOUNT"]
    AZURE_STORAGE_CONTAINER = os.environ["AZURE_STORAGE_CONTAINER"]
    AZURE_USERSTORAGE_ACCOUNT = os.environ.get("AZURE_USERSTORAGE_ACCOUNT")
    AZURE_USERSTORAGE_CONTAINER = os.environ.get("AZURE_USERSTORAGE_CONTAINER")
    # Shared by all OpenAI deployments
    OPENAI_HOST = os.getenv("OPENAI_HOST", "azure")
    OPENAI_CHATGPT_MODEL = os.environ["AZURE_OPENAI_CHATGPT_MODEL"]
    OPENAI_EMB_MODEL = os.getenv("AZURE_OPENAI_EMB_MODEL_NAME", "text-embedding-ada-002")
    OPENAI_EMB_DIMENSIONS = int(os.getenv("AZURE_OPENAI_EMB_DIMENSIONS") or 1536)
    # Used with Azure OpenAI deployments
    AZURE_OPENAI_SERVICE = os.getenv("AZURE_OPENAI_SERVICE")
    AZURE_OPENAI_GPT4V_DEPLOYMENT = os.environ.get("AZURE_OPENAI_GPT4V_DEPLOYMENT")
    AZURE_OPENAI_GPT4V_MODEL = os.environ.get("AZURE_OPENAI_GPT4V_MODEL")
    AZURE_OPENAI_CHATGPT_DEPLOYMENT = (
        os.getenv("AZURE_OPENAI_CHATGPT_DEPLOYMENT") if OPENAI_HOST.startswith("azure") else None
    )
    AZURE_OPENAI_EMB_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMB_DEPLOYMENT") if OPENAI_HOST.startswith("azure") else None
    AZURE_OPENAI_CUSTOM_URL = os.getenv("AZURE_OPENAI_CUSTOM_URL")
    # https://learn.microsoft.com/azure/ai-services/openai/api-version-deprecation#latest-ga-api-release
    # Use a version known to support Assistants API
    AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION") or "2024-02-15-preview"
    # Used only with non-Azure OpenAI deployments
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_ORGANIZATION = os.getenv("OPENAI_ORGANIZATION")

    AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID")
    AZURE_USE_AUTHENTICATION = os.getenv("AZURE_USE_AUTHENTICATION", "").lower() == "true"
    AZURE_ENFORCE_ACCESS_CONTROL = os.getenv("AZURE_ENFORCE_ACCESS_CONTROL", "").lower() == "true"
    AZURE_ENABLE_GLOBAL_DOCUMENT_ACCESS = os.getenv("AZURE_ENABLE_GLOBAL_DOCUMENT_ACCESS", "").lower() == "true"
    AZURE_ENABLE_UNAUTHENTICATED_ACCESS = os.getenv("AZURE_ENABLE_UNAUTHENTICATED_ACCESS", "").lower() == "true"
    AZURE_SERVER_APP_ID = os.getenv("AZURE_SERVER_APP_ID")
    AZURE_SERVER_APP_SECRET = os.getenv("AZURE_SERVER_APP_SECRET")
    AZURE_CLIENT_APP_ID = os.getenv("AZURE_CLIENT_APP_ID")
    AZURE_AUTH_TENANT_ID = os.getenv("AZURE_AUTH_TENANT_ID", AZURE_TENANT_ID)

    KB_FIELDS_CONTENT = os.getenv("KB_FIELDS_CONTENT", "content")
    KB_FIELDS_SOURCEPAGE = os.getenv("KB_FIELDS_SOURCEPAGE", "sourcepage")

    AZURE_SPEECH_SERVICE_ID = os.getenv("AZURE_SPEECH_SERVICE_ID")
    AZURE_SPEECH_SERVICE_LOCATION = os.getenv("AZURE_SPEECH_SERVICE_LOCATION")
    AZURE_SPEECH_SERVICE_VOICE = os.getenv("AZURE_SPEECH_SERVICE_VOICE") or "en-US-AndrewMultilingualNeural"

    USE_GPT4V = os.getenv("USE_GPT4V", "").lower() == "true"
    USE_USER_UPLOAD = os.getenv("USE_USER_UPLOAD", "").lower() == "true"
    ENABLE_LANGUAGE_PICKER = os.getenv("ENABLE_LANGUAGE_PICKER", "").lower() == "true"
    USE_SPEECH_INPUT_BROWSER = os.getenv("USE_SPEECH_INPUT_BROWSER", "").lower() == "true"
    USE_SPEECH_OUTPUT_BROWSER = os.getenv("USE_SPEECH_OUTPUT_BROWSER", "").lower() == "true"
    USE_SPEECH_OUTPUT_AZURE = os.getenv("USE_SPEECH_OUTPUT_AZURE", "").lower() == "true"
    USE_CHAT_HISTORY_BROWSER = os.getenv("USE_CHAT_HISTORY_BROWSER", "").lower() == "true"
    USE_CHAT_HISTORY_COSMOS = os.getenv("USE_CHAT_HISTORY_COSMOS", "").lower() == "true"
    USE_AGENTIC_RETRIEVAL = os.getenv("USE_AGENTIC_RETRIEVAL", "").lower() == "true"
    USE_STREAMING = os.getenv("USE_STREAMING", "true").lower() == "true"

    # WEBSITE_HOSTNAME is always set by App Service, RUNNING_IN_PRODUCTION is set in main.bicep
    RUNNING_ON_AZURE = os.getenv("WEBSITE_HOSTNAME") is not None or os.getenv("RUNNING_IN_PRODUCTION") is not None

    # Use the appropriate authentication method based on available credentials
    # Priority: 1. Service Principal (if credentials provided) 2. DefaultAzureCredential 3. ManagedIdentity (on Azure)
    AZURE_CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")
    AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
    
    if RUNNING_ON_AZURE:
        current_app.logger.info("Setting up Azure credential using ManagedIdentityCredential")
        if AZURE_CLIENT_ID:
            current_app.logger.info(
                "Setting up Azure credential using ManagedIdentityCredential with client_id %s", AZURE_CLIENT_ID
            )
            azure_credential = ManagedIdentityCredential(client_id=AZURE_CLIENT_ID)
        else:
            current_app.logger.info("Setting up Azure credential using ManagedIdentityCredential")
            azure_credential = ManagedIdentityCredential()
    elif AZURE_CLIENT_ID and AZURE_CLIENT_SECRET and AZURE_TENANT_ID:
        current_app.logger.info(
            "Setting up Azure credential using ClientSecretCredential with client_id %s", AZURE_CLIENT_ID
        )
        azure_credential = ClientSecretCredential(
            tenant_id=AZURE_TENANT_ID,
            client_id=AZURE_CLIENT_ID,
            client_secret=AZURE_CLIENT_SECRET
        )
    else:
        current_app.logger.info("Setting up Azure credential using DefaultAzureCredential")
        # DefaultAzureCredential tries multiple authentication methods including environment variables
        azure_credential = DefaultAzureCredential()

    # Set the Azure credential in the app config for use in other parts of the app
    current_app.config[CONFIG_CREDENTIAL] = azure_credential

    # Print out endpoint values for debugging
    current_app.logger.info("============ DEBUG INFORMATION ============")
    current_app.logger.info(f"AZURE_OPENAI_SERVICE: {AZURE_OPENAI_SERVICE}")
    current_app.logger.info(f"OPENAI_HOST: {OPENAI_HOST}")
    current_app.logger.info(f"AZURE_OPENAI_CHATGPT_DEPLOYMENT: {AZURE_OPENAI_CHATGPT_DEPLOYMENT}")
    current_app.logger.info(f"AZURE_OPENAI_EMB_DEPLOYMENT: {AZURE_OPENAI_EMB_DEPLOYMENT}")
    current_app.logger.info(f"AZURE_OPENAI_API_VERSION: {AZURE_OPENAI_API_VERSION}")
    current_app.logger.info("=============================================")
    
    # Set up OpenAI client
    current_app.logger.info("Setting up OpenAI client for pure chat approach")
    

    # Print storage account info for debugging
    storage_url = f"https://{AZURE_STORAGE_ACCOUNT}.blob.core.windows.net"
    current_app.logger.info(f"Storage URL: {storage_url}")
    current_app.logger.info(f"Storage container: {AZURE_STORAGE_CONTAINER}")
    
    try:
        blob_container_client = ContainerClient(
            storage_url, AZURE_STORAGE_CONTAINER, credential=azure_credential
        )
        current_app.logger.info("Successfully created blob_container_client")
    except Exception as e:
        current_app.logger.error(f"Error creating blob_container_client: {str(e)}")
        raise

    auth_helper = AuthenticationHelper(
        use_authentication=AZURE_USE_AUTHENTICATION,
        server_app_id=AZURE_SERVER_APP_ID,
        server_app_secret=AZURE_SERVER_APP_SECRET,
        client_app_id=AZURE_CLIENT_APP_ID,
        tenant_id=AZURE_AUTH_TENANT_ID,
        require_access_control=AZURE_ENFORCE_ACCESS_CONTROL,
        enable_global_documents=AZURE_ENABLE_GLOBAL_DOCUMENT_ACCESS,
        enable_unauthenticated_access=AZURE_ENABLE_UNAUTHENTICATED_ACCESS,
    )

    if USE_USER_UPLOAD:
        current_app.logger.info("USE_USER_UPLOAD is true, setting up user upload feature")
        if not AZURE_USERSTORAGE_ACCOUNT or not AZURE_USERSTORAGE_CONTAINER:
            raise ValueError(
                "AZURE_USERSTORAGE_ACCOUNT and AZURE_USERSTORAGE_CONTAINER must be set when USE_USER_UPLOAD is true"
            )
        user_blob_container_client = FileSystemClient(
            f"https://{AZURE_USERSTORAGE_ACCOUNT}.dfs.core.windows.net",
            AZURE_USERSTORAGE_CONTAINER,
            credential=azure_credential,
        )
        current_app.config[CONFIG_USER_BLOB_CONTAINER_CLIENT] = user_blob_container_client

        # Set up ingester
        file_processors = setup_file_processors(
            azure_credential=azure_credential,
            document_intelligence_service=os.getenv("AZURE_DOCUMENTINTELLIGENCE_SERVICE"),
            local_pdf_parser=os.getenv("USE_LOCAL_PDF_PARSER", "").lower() == "true",
            local_html_parser=os.getenv("USE_LOCAL_HTML_PARSER", "").lower() == "true",
            search_images=USE_GPT4V,
        )
        text_embeddings_service = setup_embeddings_service(
            azure_credential=azure_credential,
            openai_host=OPENAI_HOST,
            openai_model_name=OPENAI_EMB_MODEL,
            openai_service=AZURE_OPENAI_SERVICE,
            openai_custom_url=AZURE_OPENAI_CUSTOM_URL,
            openai_deployment=AZURE_OPENAI_EMB_DEPLOYMENT,
            openai_dimensions=OPENAI_EMB_DIMENSIONS,
            openai_api_version=AZURE_OPENAI_API_VERSION,
            openai_key=clean_key_if_exists(OPENAI_API_KEY),
            openai_org=OPENAI_ORGANIZATION,
            disable_vectors=os.getenv("USE_VECTORS", "").lower() == "false",
        )
        ingester = UploadUserFileStrategy(
            embeddings=text_embeddings_service,
            file_processors=file_processors,
        )
        current_app.config[CONFIG_INGESTER] = ingester

    # Used by the OpenAI SDK
    openai_client: AsyncOpenAI

    if USE_SPEECH_OUTPUT_AZURE:
        current_app.logger.info("USE_SPEECH_OUTPUT_AZURE is true, setting up Azure speech service")
        if not AZURE_SPEECH_SERVICE_ID or AZURE_SPEECH_SERVICE_ID == "":
            raise ValueError("Azure speech resource not configured correctly, missing AZURE_SPEECH_SERVICE_ID")
        if not AZURE_SPEECH_SERVICE_LOCATION or AZURE_SPEECH_SERVICE_LOCATION == "":
            raise ValueError("Azure speech resource not configured correctly, missing AZURE_SPEECH_SERVICE_LOCATION")
        current_app.config[CONFIG_SPEECH_SERVICE_ID] = AZURE_SPEECH_SERVICE_ID
        current_app.config[CONFIG_SPEECH_SERVICE_LOCATION] = AZURE_SPEECH_SERVICE_LOCATION
        current_app.config[CONFIG_SPEECH_SERVICE_VOICE] = AZURE_SPEECH_SERVICE_VOICE
        # Wait until token is needed to fetch for the first time
        current_app.config[CONFIG_SPEECH_SERVICE_TOKEN] = None

    if OPENAI_HOST.startswith("azure"):
        if OPENAI_HOST == "azure_custom":
            current_app.logger.info("OPENAI_HOST is azure_custom, setting up Azure OpenAI custom client")
            if not AZURE_OPENAI_CUSTOM_URL:
                raise ValueError("AZURE_OPENAI_CUSTOM_URL must be set when OPENAI_HOST is azure_custom")
            endpoint = AZURE_OPENAI_CUSTOM_URL
        else:
            current_app.logger.info("OPENAI_HOST is azure, setting up Azure OpenAI client")
            if not AZURE_OPENAI_SERVICE:
                raise ValueError("AZURE_OPENAI_SERVICE must be set when OPENAI_HOST is azure")
            
            # Clean up the service name to ensure it doesn't have any extra parts
            service_name = AZURE_OPENAI_SERVICE.strip()
            # Remove any trailing slashes
            service_name = service_name.rstrip("/")
            
            current_app.logger.info(f"Cleaned service name: {service_name}")
            endpoint = f"https://{service_name}.openai.azure.com"
            current_app.logger.info(f"Azure OpenAI endpoint: {endpoint}")
            # Try to resolve the hostname to check connectivity
            try:
                import socket
                hostname = endpoint.replace("https://", "").split(":")[0]
                current_app.logger.info(f"Attempting to resolve hostname: {hostname}")
                ip_address = socket.gethostbyname(hostname)
                current_app.logger.info(f"Successfully resolved {hostname} to {ip_address}")
            except Exception as e:
                current_app.logger.error(f"Failed to resolve hostname {hostname}: {str(e)}")
        
        # First try to use API key from .env if available
        api_key = os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY_OVERRIDE")
        if api_key:
            current_app.logger.info("Using API key for Azure OpenAI client")
            current_app.logger.info(f"API key length: {len(api_key)} characters")
            try:
                endpoint = endpoint.rstrip("/")
                if not endpoint.endswith("/openai/v1"):
                    endpoint = f"{endpoint}/openai/v1"
                openai_client = AsyncAzureOpenAI(
                    api_version=AZURE_OPENAI_API_VERSION, azure_endpoint=endpoint, api_key=api_key
                )
                current_app.logger.info("Successfully created OpenAI client with API key")
            except Exception as e:
                current_app.logger.error(f"Error creating OpenAI client with API key: {str(e)}")
                raise
        else:
            # Fall back to token-based authentication if no API key is available
            current_app.logger.info("Using Azure credential (passwordless authentication) for Azure OpenAI client")
            try:
                token_provider = get_bearer_token_provider(azure_credential, "https://cognitiveservices.azure.com/.default")
                openai_client = AsyncAzureOpenAI(
                    api_version=AZURE_OPENAI_API_VERSION,
                    azure_endpoint=endpoint,
                    azure_ad_token_provider=token_provider,
                )
            except Exception as e:
                current_app.logger.error(f"Error setting up token provider: {str(e)}")
                raise ValueError("Failed to set up Azure OpenAI client. Please provide AZURE_OPENAI_API_KEY in your .env file.")
    elif OPENAI_HOST == "local":
        current_app.logger.info("OPENAI_HOST is local, setting up local OpenAI client for OPENAI_BASE_URL with no key")
        openai_client = AsyncOpenAI(
            base_url=os.environ["OPENAI_BASE_URL"],
            api_key="no-key-required",
        )
    else:
        current_app.logger.info(
            "OPENAI_HOST is not azure, setting up OpenAI client using OPENAI_API_KEY and OPENAI_ORGANIZATION environment variables"
        )
        openai_client = AsyncOpenAI(
            api_key=OPENAI_API_KEY,
            organization=OPENAI_ORGANIZATION,
        )

    current_app.config[CONFIG_OPENAI_CLIENT] = openai_client
    # Removed CONFIG_AGENT_CLIENT reference as part of Azure Search removal
    current_app.config[CONFIG_BLOB_CONTAINER_CLIENT] = blob_container_client
    current_app.config[CONFIG_AUTH_CLIENT] = auth_helper

    current_app.config[CONFIG_GPT4V_DEPLOYED] = bool(USE_GPT4V)
    current_app.config[CONFIG_STREAMING_ENABLED] = USE_STREAMING
    current_app.config[CONFIG_LANGUAGE_PICKER_ENABLED] = ENABLE_LANGUAGE_PICKER
    current_app.config[CONFIG_SPEECH_INPUT_ENABLED] = USE_SPEECH_INPUT_BROWSER
    current_app.config[CONFIG_SPEECH_OUTPUT_BROWSER_ENABLED] = USE_SPEECH_OUTPUT_BROWSER
    current_app.config[CONFIG_SPEECH_OUTPUT_AZURE_ENABLED] = USE_SPEECH_OUTPUT_AZURE
    current_app.config[CONFIG_CHAT_HISTORY_BROWSER_ENABLED] = USE_CHAT_HISTORY_BROWSER
    current_app.config[CONFIG_CHAT_HISTORY_COSMOS_ENABLED] = USE_CHAT_HISTORY_COSMOS
    # Removed CONFIG_AGENTIC_RETRIEVAL_ENABLED reference as part of Azure Search removal
    # Set up the approach objects
    if OPENAI_HOST.startswith("azure"):
        # Use the Azure OpenAI API
        if AZURE_OPENAI_CUSTOM_URL:
            base_url = AZURE_OPENAI_CUSTOM_URL
        else:
            base_url = f"https://{AZURE_OPENAI_SERVICE}.openai.azure.com"

        # Set up OpenAI client
        openai_client = AsyncAzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
            api_version=AZURE_OPENAI_API_VERSION,
            azure_endpoint=base_url,
            default_headers={"x-ms-useragent": "AzureSearchDemo/1.0.0"},
        )
    else:
        # Use the non-Azure OpenAI API
        openai_client = AsyncOpenAI(
            api_key=OPENAI_API_KEY,
            organization=OPENAI_ORGANIZATION,
            default_headers={"x-ms-useragent": "AzureSearchDemo/1.0.0"},
        )

    # Set up prompt manager
    prompt_manager = PromptManager()

    # Set up the authentication helper
    if AZURE_USE_AUTHENTICATION:
        if AZURE_SERVER_APP_ID and AZURE_SERVER_APP_SECRET and AZURE_CLIENT_APP_ID and AZURE_AUTH_TENANT_ID:
            current_app.logger.info("Using AAD auth with client credential flow")
            auth_helper = AuthenticationHelper(
                server_app_id=AZURE_SERVER_APP_ID,
                server_app_secret=AZURE_SERVER_APP_SECRET,
                client_app_id=AZURE_CLIENT_APP_ID,
                tenant_id=AZURE_AUTH_TENANT_ID,
                enable_global_document_access=AZURE_ENABLE_GLOBAL_DOCUMENT_ACCESS,
                enable_unauthenticated_access=AZURE_ENABLE_UNAUTHENTICATED_ACCESS,
            )
        else:
            current_app.logger.info("Using AAD auth with on-behalf-of flow")
            auth_helper = AuthenticationHelper(
                enable_global_document_access=AZURE_ENABLE_GLOBAL_DOCUMENT_ACCESS,
                enable_unauthenticated_access=AZURE_ENABLE_UNAUTHENTICATED_ACCESS,
            )
    else:
        current_app.logger.info("Using mock auth")
        auth_helper = MockAuthenticationHelper()

    # Set up the pure chat approach
    current_app.logger.info("Initializing PureChatApproach")
    current_app.config[CONFIG_CHAT_APPROACH] = PureChatApproach(
        openai_client=openai_client,
        chatgpt_model=OPENAI_CHATGPT_MODEL,
        chatgpt_deployment=AZURE_OPENAI_CHATGPT_DEPLOYMENT,
    )
    
    # Use the same approach for ask endpoint
    current_app.config[CONFIG_ASK_APPROACH] = current_app.config[CONFIG_CHAT_APPROACH]

    # Removed GPT4V and vision approach setup as part of Azure Search removal
    current_app.logger.info("Skipping GPT4V setup as we're using pure chat approach")

    # Register our custom ChatApproach implementation for handling file uploads
    from approaches.chat import ChatApproach as AssistantChatApproach
    current_app.config["ASSISTANT_CHAT_APPROACH"] = AssistantChatApproach(openai_client)


@bp.after_app_serving
async def close_clients():
    await current_app.config[CONFIG_BLOB_CONTAINER_CLIENT].close()
    if current_app.config.get(CONFIG_USER_BLOB_CONTAINER_CLIENT):
        await current_app.config[CONFIG_USER_BLOB_CONTAINER_CLIENT].close()


def create_app():
    app = Quart(__name__, static_folder="static")
    
    # Enable CORS for all origins when deployed as SPA
    # The following environments will enable all-origin CORS
    # DEPLOYMENT_MODE can be "SPA" or other values
    is_spa_deployment = os.environ.get("DEPLOYMENT_MODE", "").upper() == "SPA"
    
    if is_spa_deployment:
        # For SPA deployment, allow all origins
        app = cors(app, allow_origin="*")
    else:
        # For local or container deployment, use the default CORS config
        app = cors(app)
    
    # Register blueprints and middleware
    app.register_blueprint(bp)
    if CONFIG_CHAT_HISTORY_COSMOS_ENABLED:
        app.register_blueprint(chat_history_cosmosdb_bp)
    
    # Configure JSON serialization
    app.json_encoder = JSONEncoder
    
    # Setup telemetry if enabled
    if "APPLICATIONINSIGHTS_CONNECTION_STRING" in os.environ:
        configure_azure_monitor()
        AioHttpClientInstrumentor().instrument()
        HTTPXClientInstrumentor().instrument()
        OpenAIInstrumentor().instrument()
        app.asgi_app = OpenTelemetryMiddleware(app.asgi_app)
    
    # Initialize AuthenticationHelper in the app config
    if os.environ.get("AZURE_USE_AUTHENTICATION", "").lower() == "false":
        app.config[CONFIG_AUTH_CLIENT] = MockAuthenticationHelper()
    else:
        app.config[CONFIG_AUTH_CLIENT] = AuthenticationHelper()
    
    return app
