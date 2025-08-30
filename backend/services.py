import os
import pytesseract
from typing import Optional
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_community.document_loaders import UnstructuredWordDocumentLoader, UnstructuredPowerPointLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from PIL import Image
from pdf2image import convert_from_path
from langchain_core.documents import Document
import time
from langchain_chroma import Chroma
import re

from dotenv import load_dotenv
load_dotenv()




COLLECTION_NAME = "DocuChat"
EMBEDDING_MODEL = "all-MiniLM-L6-v2" 

embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
chroma_vector_store = Chroma(
    embedding_function=embeddings,
    collection_name=COLLECTION_NAME,
    tenant=os.getenv("CHROMA_TENANT"),
    chroma_cloud_api_key=os.getenv("CHROMA_API_KEY"),
    database = 'DocuChat',
)

# --- Document Ingestion Function ---
def ocr_pdf(file_path: str) -> str:
    """Extract text from scanned PDF using OCR."""
    text = ""
    images = convert_from_path(file_path)
    for img in images:
        text += pytesseract.image_to_string(img)
    return text

def ocr_image(file_path: str) -> str:
    """Extract text from image files using OCR."""
    try:
        img = Image.open(file_path)
        return  pytesseract.image_to_string(img)
    except Exception as e:
        print(f"OCR failed for image {file_path}: {e}")
        return ""

def ingest_document(file_path: str) -> tuple[bool, str]:
    """
    Loads, splits, embeds, and stores a document in Qdrant.
    Uses OCR if the document is not machine readable.
    Supports PDF, DOCX, PPTX, TXT, MD, and image files.
    """
    print(f"Starting ingestion process for document: {file_path}")
    try:
        file_extension = os.path.splitext(file_path)[1].lower()
        file_name = os.path.basename(file_path)

        # Try standard loaders first
        try:
            if file_extension == ".pdf":
                loader = PyPDFLoader(file_path)
                documents = loader.load()
                # If no text found, fallback to OCR
                if not documents or not documents[0].page_content.strip():
                    print("No machine-readable text found, using OCR...")
                    text = ocr_pdf(file_path)
                    documents = [Document(page_content=text, metadata={"file_name": file_name})]
            elif file_extension == ".docx":
                loader = UnstructuredWordDocumentLoader(file_path)
                documents = loader.load()
            elif file_extension == ".pptx":
                loader = UnstructuredPowerPointLoader(file_path)
                documents = loader.load()
            elif file_extension in [".txt", ".md"]:
                loader = TextLoader(file_path)
                documents = loader.load()
            elif file_extension in [".png", ".jpg", ".jpeg", ".bmp", ".tiff"]:
                print("Processing image file with OCR...")
                text = ocr_image(file_path)
                documents = [Document(page_content=text, metadata={"file_name": file_name})]
            else:
                raise ValueError(f"Unsupported file type: {file_extension}")
        except Exception as e:
            # Fallback to OCR for PDFs and images
            if file_extension == ".pdf":
                print("Error loading PDF, using OCR fallback...")
                text = ocr_pdf(file_path)
                documents = [Document(page_content=text, metadata={"file_name": file_name})]
            elif file_extension in [".png", ".jpg", ".jpeg", ".bmp", ".tiff"]:
                print("Error loading image, using OCR fallback...")
                text = ocr_image(file_path)
                documents = [Document(page_content=text, metadata={"file_name": file_name})]
            else:
                raise e

        print("Splitting document into chunks...")
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        docs = text_splitter.split_documents(documents)
        for doc in docs:
            doc.metadata["file_name"] = file_name
        print(f"Split document into {len(docs)} chunks.")

        print(f"Storing embeddings in Chroma collection '{COLLECTION_NAME}'...")
        
        chroma_vector_store.add_documents(docs)
        print("Document ingestion successful.")
        return True, f"Document '{file_name}' ingested successfully."
    except Exception as e:
        print(f"An unexpected error occurred during ingestion: {e}")
        return False, str(e)

    

def retrieve_context(query: str, file_name: str = None) -> tuple[list, Optional[str]]:
    print(f"Starting context retrieval for query: '{query}' on file: '{file_name}'")
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    try:
        filter = {"file_name": file_name} if file_name else None
        retriever = chroma_vector_store.as_retriever(
            search_kwargs={"filter": filter, "k": 50}
        )
        retrieved_docs = retriever.invoke(query)
        print(f"Found {len(retrieved_docs)} relevant document chunks.")
        return retrieved_docs, None
    except Exception as e:
        print(f"An error occurred during context retrieval: {e}")
        return [], str(e)



def get_used_citations(answer, context):
    import re
    def text_to_tokens(text):
        return set(re.findall(r'\w+', text.lower()))
    used_citations = set()
    answer_tokens = text_to_tokens(answer)
    for doc in context:
        chunk_tokens = text_to_tokens(doc.page_content)
        overlap = answer_tokens.intersection(chunk_tokens)
        # Require at least 10 overlapping tokens and >50% overlap ratio
        if len(overlap) > 10 and len(overlap) / max(1, len(chunk_tokens)) > 0.5:
            meta = doc.metadata
            citation = f"- {meta.get('file_name', '')}"
            if 'page' in meta:
                citation += f", page {meta['page'] + 1}"
            used_citations.add(citation)
    return used_citations

def generate_answer(query: str, context: list, message_history: Optional[list] = None) -> tuple[Optional[str], Optional[str]]:
    """
    Generates a final answer using an LLM based on the query, retrieved context, and previous message history.
    Also returns citations from the document chunks used.
    """
    print(f"Generating answer for query: '{query}'")
    try:
        if not context:
            return "I am sorry, but I could not retrieve any relevant information for that question from the selected document.", None

        context_text = "\n\n---\n\n".join([doc.page_content for doc in context])

        # Prepare message history for the prompt
        history_text = ""
        if message_history:
            for i, msg in enumerate(message_history):
                sender = "User" if msg["type"] == "user" else "Bot"
                history_text += f"{sender}: {msg['text']}\n"

        # Collect citations from context, removing duplicates
        citations = set()
        for doc in context:
            meta = doc.metadata
            citation = f"- {meta.get('file_name', '')}"
            if 'page' in meta:
                citation += f", page {meta['page'] + 1}"
            citations.add(citation)

        llm = AzureChatOpenAI(
            api_key=os.getenv("AZURE_OPEN_AI_API_KEY"), 
            api_version=os.getenv("AZURE_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_API_ENDPOINT"),
        )

        template = """
You are an AI assistant who is an expert in analyzing technical documents and resumes.
Your task is to provide a detailed and helpful response to the user's question based ONLY on the provided context.

Formatting Instructions:
- Use Markdown formatting for your answer.
- Start with a brief overview or summary if appropriate.
- Use bullet points for lists and group related information together.
- Add line breaks between sections for readability.
- End your answer with a brief summary or conclusion.
- If the answer is not found in the context, clearly state: "I am sorry, but the answer to that question is not present in the uploaded document." Do not make up an answer.

Previous Conversation:
{history}

Context:
{context}

Question:
{question}

Answer:
"""
        rag_prompt = PromptTemplate.from_template(template)

        rag_chain = (
            {
                "context": RunnablePassthrough(),
                "question": RunnablePassthrough(),
                "history": RunnablePassthrough()
            }
            | rag_prompt
            | llm
            | StrOutputParser()
        )
        
        answer = rag_chain.invoke({
            "context": context_text,
            "question": query,
            "history": history_text
        })
        used_citations = get_used_citations(answer, context)
        if used_citations:
            answer += "\n\n---\n**Citations:**\n" + "\n".join(sorted(used_citations))
        else:
            answer += "\n\n---\n**Citations:**\nNo specific chunk was directly referenced in the answer."

        print("Successfully generated answer.")
        return answer, None
    except Exception as e:
        print(f"An error occurred during answer generation: {e}")
        return None, str(e)

