import os
from typing import Optional
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_community.document_loaders import UnstructuredWordDocumentLoader, UnstructuredPowerPointLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_qdrant import Qdrant


from qdrant_client import QdrantClient, models

from qdrant_client.models import Distance, VectorParams, PayloadSchemaType
from qdrant_client.http.exceptions import UnexpectedResponse, ResponseHandlingException
from langchain_core.documents import Document



from dotenv import load_dotenv
load_dotenv()



QDRANT_HOST = os.getenv("QDRANT_HOST")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = "document_chatbot"
EMBEDDING_MODEL = "all-MiniLM-L6-v2" 

qdrant_client = QdrantClient(
    url=QDRANT_HOST,
    api_key=QDRANT_API_KEY,
)

embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)


# --- Document Ingestion Function ---
def ingest_document(file_path: str) -> tuple[bool, str]:
    """
    Loads, splits, embeds, and stores a document in Qdrant.
    It adds new documents to the existing collection.
    """
    print(f"Starting ingestion process for document: {file_path}")
    try:
        
        try:
            
            qdrant_client.get_collection(collection_name=COLLECTION_NAME)
        except Exception as e:
            print(e)
            print(f"Collection '{COLLECTION_NAME}' not found. Creating a new one...")
            qdrant_client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE),
            )
            
            qdrant_client.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name="file_name",
                field_schema=models.PayloadSchemaType.KEYWORD
            )
            print("Collection and index created successfully.")
        
        
        print(f"Loading document from {file_path}")
        file_extension = os.path.splitext(file_path)[1].lower()
        file_name = os.path.basename(file_path)

        if file_extension == ".pdf":
            loader = PyPDFLoader(file_path)
        elif file_extension == ".docx":
            loader = UnstructuredWordDocumentLoader(file_path)
        elif file_extension == ".pptx":
            loader = UnstructuredPowerPointLoader(file_path)
        elif file_extension in [".txt", ".md"]:
            loader = TextLoader(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_extension}")

        documents = loader.load()

        
        for doc in documents:
            doc.metadata["file_name"] = file_name

        
        print("Splitting document into chunks...")
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        docs = text_splitter.split_documents(documents)
        print(f"Split document into {len(docs)} chunks.")
        
        
        print(f"Storing embeddings in Qdrant collection '{COLLECTION_NAME}'...")
        qdrant_vector_store = Qdrant(
            embeddings=embeddings,
            client=qdrant_client,
            collection_name=COLLECTION_NAME,
        )
        qdrant_vector_store.add_documents(docs)
        print("Document ingestion successful.")
        check_collection_points()
        return True, f"Document '{file_name}' ingested successfully."
    except Exception as e:
        print(f"An unexpected error occurred during ingestion: {e}")
        return False, str(e)

    

def retrieve_context(query: str, file_name: str = None) -> tuple[list, Optional[str]]:
    """
    Embeds a user query and retrieves the most relevant document chunks from Qdrant,
    filtered by file name using the required index.
    """
    print(f"Starting context retrieval for query: '{query}' on file: '{file_name}'")
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    try:
        
        try:
            collection_info = qdrant_client.get_collection(collection_name=COLLECTION_NAME)
            print(f"Collection '{COLLECTION_NAME}' status: {collection_info.status}")
            
            
            
            print("--------------------")
            indexed_fields_info = collection_info.payload_schema
            print(indexed_fields_info)
            
            file_name_indexed = (
                "file_name" in indexed_fields_info and
                indexed_fields_info["file_name"].data_type == models.PayloadSchemaType.KEYWORD
            )


            if not file_name_indexed:
                raise ValueError(f"Qdrant collection '{COLLECTION_NAME}' exists, but 'file_name' keyword index is missing or incorrectly configured. Please re-ingest the document to ensure the index is created.")

            print("'file_name' payload index confirmed to exist.")

        except ResponseHandlingException as e:
            if e.status_code == 404:
                return [], f"Error: Qdrant collection '{COLLECTION_NAME}' not found. Please ingest a document first."
            else:
                return [], f"Qdrant API error checking collection status: {e.status_code} - {e.content}"
        except ValueError as e: 
            return [], str(e)
        except Exception as e:
            return [], f"Failed to verify Qdrant collection/index: {e}"

        print("Connecting to Qdrant for retrieval...")
        qdrant_vector_store = Qdrant(
            embeddings=embeddings,
            client=qdrant_client,
            collection_name=COLLECTION_NAME,
        )

        
        query_filter = None
        if file_name:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="file_name",
                        match=models.MatchValue(value=file_name)
                    )
                ]
            )

        
        print(f"Searching for relevant documents for query: '{query}' filtered by '{file_name}'...")
        retrieved_docs = qdrant_vector_store.similarity_search(query, k=5)
        print(f"Found {len(retrieved_docs)} relevant document chunks.")
        
        return retrieved_docs, None
    except Exception as e:
        print(f"An error occurred during context retrieval: {e}")
        return [], str(e)



def generate_answer(query: str, context: list) -> tuple[Optional[str], Optional[str]]:
    """
    Generates a final answer using an LLM based on the query and retrieved context.
    """
    print(f"Generating answer for query: '{query}'")
    try:
        if not context:
            return "I am sorry, but I could not retrieve any relevant information for that question from the selected document.", None

        context_text = "\n\n---\n\n".join([doc.page_content for doc in context])

        llm = AzureChatOpenAI(
            api_key=os.getenv("AZURE_OPEN_AI_API_KEY"), 
            api_version=os.getenv("AZURE_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_API_ENDPOINT"),
        )

        # --- START OF CHANGED PROMPT TEMPLATE ---
        template = """
You are an AI assistant who is an expert in analyzing technical documents and resumes.
Your task is to provide a detailed and helpful response to the user's question based ONLY on the provided context.

Formatting Instructions:
- Use Markdown formatting for your answer.
- Start with a brief overview or summary if appropriate.
- Organize your answer using clear section headings (e.g., ## Overview, ## Details, ## Summary).
- Use bullet points for lists and group related information together.
- Add line breaks between sections for readability.
- End your answer with a brief summary or conclusion.
- If the answer is not found in the context, clearly state: "I am sorry, but the answer to that question is not present in the uploaded document." Do not make up an answer.

Context:
{context}

Question:
{question}

Answer:
"""
        # --- END OF CHANGED PROMPT TEMPLATE ---

        rag_prompt = PromptTemplate.from_template(template)

        rag_chain = (
            {"context": RunnablePassthrough(), "question": RunnablePassthrough()}
            | rag_prompt
            | llm
            | StrOutputParser()
        )
        
        answer = rag_chain.invoke({"context": context_text, "question": query})

        print("Successfully generated answer.")
        return answer, None
    except Exception as e:
        print(f"An error occurred during answer generation: {e}")
        return None, str(e)


def check_collection_points():
    try:
        count_result = qdrant_client.count(collection_name=COLLECTION_NAME, exact=True)
        print(f"Current number of points in collection '{COLLECTION_NAME}': {count_result.count}")
        if count_result.count > 0:
            # Also try to retrieve one point to check its payload
            sample_points = qdrant_client.scroll(collection_name=COLLECTION_NAME, limit=1, with_payload=True)
            if sample_points and sample_points[0]:
                print(f"Sample point payload: {sample_points[0][0].payload}")
            else:
                print("Could not retrieve a sample point even though points exist.")
    except Exception as e:
        print(f"Error checking collection points: {e}")
