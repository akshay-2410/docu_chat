# Document Chat

A web-based chatbot that answers questions about your uploaded documents using AI and semantic search.

## Features

- Upload PDF, DOCX, PPTX, TXT, or Markdown documents
- Select a document and ask questions about its content
- Answers are generated using an LLM and are context-aware
- Answers are rendered with full Markdown formatting (headings, lists, bold, etc.)
- Compact, modern UI with loading indicators and status messages
- Clear all uploaded files and embeddings with one click

## Tech Stack

- **Frontend:** React, Axios, react-markdown
- **Backend:** FastAPI, LangChain, Qdrant, HuggingFace Embeddings, Azure OpenAI
- **Vector DB:** Qdrant

## Setup Instructions

### 1. Clone the repository

```sh
git clone https://github.com/yourusername/document_chat.git
cd document_chat
```

### 2. Backend Setup

- Install Python dependencies:

  ```sh
  cd backend
  pip install -r requirements.txt
  ```

- Create a `.env` file in `backend/` with your Qdrant and Azure OpenAI credentials:

  ```
  QDRANT_HOST=YOUR_QDRANT_URL
  QDRANT_API_KEY=YOUR_QDRANT_API_KEY
  AZURE_OPEN_AI_API_KEY=YOUR_AZURE_OPENAI_KEY
  AZURE_API_VERSION=YOUR_AZURE_API_VERSION
  AZURE_API_ENDPOINT=YOUR_AZURE_API_ENDPOINT
  ```

- Start the FastAPI server:

  ```sh
  uvicorn backend.asgi:app --reload
  ```

### 3. Frontend Setup

- Install Node.js dependencies:

  ```sh
  cd frontend
  npm install
  ```

- Start the React app:

  ```sh
  npm start
  ```

- The frontend runs on [http://localhost:3000](http://localhost:3000) by default.

## Usage

1. **Upload a document** using the left panel.
2. **Select a document** from the list.
3. **Ask questions** in the chat window.
4. **View answers** with full Markdown formatting.
5. **Clear all files and embeddings** if needed.

## File Structure

```
document_chat/
├── backend/
│   ├── asgi.py
│   ├── services.py
│   └── ...
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── App.css
│   │   └── ...
│   └── ...
└── README.md
```

## Customization

- **Markdown Rendering:** Answers are rendered using `react-markdown` for full Markdown support.
- **Loading Animation:** Bot messages show animated dots while waiting for a response.
- **Document Types:** Supported formats: PDF, DOCX, PPTX, TXT, MD.

## License

MIT

## Credits

- [LangChain](https://github.com/langchain-ai/langchain)
- [Qdrant](https://qdrant.tech/)
- [Azure OpenAI](https://azure.microsoft.com/en-us/products/cognitive-services/openai-service/)
- [react-markdown](https://github.com/remarkjs/react-markdown)
