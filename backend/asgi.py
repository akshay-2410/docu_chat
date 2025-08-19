# backend/asgi.py
import os
import shutil
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
# Import the client and collection name from services.py
from .services import ingest_document, retrieve_context, generate_answer, qdrant_client, COLLECTION_NAME
from typing import Optional # Import Optional

# Create the FastAPI app instance
app = FastAPI()

# Configure CORS
origins = [
    "http://localhost",
    "http://localhost:5173",  # This is the default port for Vite
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- MODIFIED UPLOAD ENDPOINT (only saves file to disk) ---
@app.post("/api/upload-document")
async def upload_document(file: UploadFile = File(...)):
    upload_dir = "uploaded_files"
    os.makedirs(upload_dir, exist_ok=True)
    file_location = os.path.join(upload_dir, file.filename)

    # Check if file already exists
    if os.path.exists(file_location):
        return {"message": f"File '{file.filename}' already exists. No ingestion performed."}

    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Ingest the document since it's a new upload
    success, message = ingest_document(file_location)
    if success:
        return {"message": f"File '{file.filename}' uploaded and ingested successfully."}
    else:
        return {"error": f"Ingestion failed: {message}"}, 500

# --- NEW ENDPOINT TO PREPARE DOCUMENT FOR QUERYING ---
@app.post("/api/prepare-document")
async def prepare_document(query_data: dict):
    file_name = query_data.get("file_name")
    if not file_name:
        return {"error": "File name not provided."}, 400
    
    upload_dir = "uploaded_files"
    file_location = os.path.join(upload_dir, file_name)
    
    if not os.path.exists(file_location):
        return {"error": f"File '{file_name}' not found in uploaded_files directory."}, 404

    # Call the ingestion service to process the selected document
    # success, message = ingest_document(file_location)
    success = True
    
    # if success:
    #     return {"message": message}
    # else:
    #     return {"error": message}, 500 # Return 500 if ingestion fails

# --- EXISTING ENDPOINTS (rest remain the same) ---
@app.get("/api/list-files")
async def list_uploaded_files():
    upload_dir = "uploaded_files"
    if not os.path.exists(upload_dir):
        return {"files": []}
    files = [f for f in os.listdir(upload_dir) if os.path.isfile(os.path.join(upload_dir, f))]
    return {"files": files}

@app.delete("/api/clear-files")
async def clear_uploaded_files():
    upload_dir = "uploaded_files"
    try:
        if os.path.exists(upload_dir):
            shutil.rmtree(upload_dir)
            os.makedirs(upload_dir)
        # It's okay if the collection doesn't exist, delete_collection will handle it.
        qdrant_client.delete_collection(collection_name=COLLECTION_NAME)
        #
        return {"message": "Uploaded files and embeddings cleared successfully."}
    except Exception as e:
        return {"error": f"Failed to clear: {str(e)}"}, 500

@app.post("/api/query")
async def handle_query(query_data: dict):
    try:
        user_query = query_data.get("text")
        selected_file_name = query_data.get("file_name")
        
        if not user_query:
            return {"error": "Query text not provided."}, 400

        print("**************")
        retrieved_docs, retrieve_error = retrieve_context(user_query, selected_file_name)
        if retrieve_error:
            return {"error": f"Retrieval failed: {retrieve_error}"}, 500
        
        answer, generate_error = generate_answer(user_query, retrieved_docs)
        if generate_error:
            return {"error": f"Answer generation failed: {generate_error}"}, 500

        return {"answer": answer}
    except Exception as e:
        return {"error": f"An unexpected error occurred: {str(e)}"}, 500