import React, { useState, useEffect } from 'react';
import axios from 'axios';
import ReactMarkdown from 'react-markdown'; // Add this import
import './App.css'; // Ensure this path is correct relative to App.js

function App() {
  const [file, setFile] = useState(null);
  const [uploadStatus, setUploadStatus] = useState('');
  const [clearStatus, setClearStatus] = useState('');
  const [query, setQuery] = useState('');
  const [chatHistory, setChatHistory] = useState([
    { type: 'bot', text: "Hi there! I'm ready to answer questions about your documents." }
  ]);
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [selectedFile, setSelectedFile] = useState('');
  const [showUploadSection, setShowUploadSection] = useState(false);
  const [showFileListSection, setShowFileListSection] = useState(false);
  const [isReadyForQuery, setIsReadyForQuery] = useState(false);
  const [isBotLoading, setIsBotLoading] = useState(false);

  // Backend URL - ensure this is correct for your setup
  const backendUrl = "http://127.0.0.1:8000/api";

  // Effect to fetch uploaded files on component mount
  useEffect(() => {
    fetchUploadedFiles();
  }, []);

  // Effect to hide uploadStatus message after 2 seconds
  useEffect(() => {
    if (uploadStatus) {
      const timer = setTimeout(() => {
        setUploadStatus('');
      }, 2000); // Hide after 2 seconds
      return () => clearTimeout(timer); // Clean up the timer
    }
  }, [uploadStatus]); // Re-run when uploadStatus changes

  // Effect to hide clearStatus message after 2 seconds
  useEffect(() => {
    if (clearStatus) {
      const timer = setTimeout(() => {
        setClearStatus('');
      }, 2000); // Hide after 2 seconds
      return () => clearTimeout(timer); // Clean up the timer
    }
  }, [clearStatus]); // Re-run when clearStatus changes


  // Function to fetch list of uploaded files from backend
  const fetchUploadedFiles = async () => {
    try {
      const response = await axios.get(`${backendUrl}/list-files`);
      const files = response.data.files;
      setUploadedFiles(files);

      // Automatically select and prepare file if only one is present
      if (files.length === 1) {
        const singleFileName = files[0];
        setSelectedFile(singleFileName);
        setUploadStatus(`Only one file ("${singleFileName}") detected. Preparing for query...`);
        try {
          await axios.post(`${backendUrl}/prepare-document`, { file_name: singleFileName });
          setIsReadyForQuery(true);
          setUploadStatus(`Document "${singleFileName}" is ready for questions.`);
        } catch (error) {
          setUploadStatus(`Failed to prepare "${singleFileName}": ${error.response?.data?.error || error.message}`);
          setIsReadyForQuery(false);
        }
      } else {
        setSelectedFile('');
        setIsReadyForQuery(false);
      }
    } catch (error) {
      console.error('Error fetching uploaded files:', error);
      // setUploadStatus(`Error fetching files: ${error.message}`); // Optional: display error to user
    }
  };

  // Handle file input change
  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
  };

  // Handle file upload submission
  const handleUploadSubmit = async (e) => {
    e.preventDefault();
    if (!file) {
      setUploadStatus('Please select a file to upload.');
      return;
    }

    setUploadStatus('Uploading...');
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post(`${backendUrl}/upload-document`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      setUploadStatus(response.data.message);
      setFile(null); // Clear selected file
      e.target.reset(); // Reset form input
      fetchUploadedFiles(); // Refresh the list of uploaded files
    } catch (error) {
      setUploadStatus(`Upload failed: ${error.response?.data?.error || error.message}`);
    }
  };

  // Handle selection of an existing file for querying
  const handleFileSelectSubmit = async (e) => {
    e.preventDefault();
    if (!selectedFile) {
        // Use a more user-friendly message instead of alert
        setUploadStatus("Please select a document from the list.");
        return;
    }
    setUploadStatus(`Preparing document "${selectedFile}" for questions...`);
    try {
      await axios.post(`${backendUrl}/prepare-document`, { file_name: selectedFile });
      setIsReadyForQuery(true);
      setUploadStatus(`Document "${selectedFile}" is now ready for questions.`);
    } catch (error) {
      setIsReadyForQuery(false);
      setUploadStatus(`Failed to prepare document: ${error.response?.data?.error || error.message}`);
    }
  };

  // Update the file selection radio button handler
  const handleFileRadioChange = async (e) => {
    const fileName = e.target.value;
    setSelectedFile(fileName);
    setUploadStatus(`Preparing document "${fileName}" for questions...`);
    try {
      await axios.post(`${backendUrl}/prepare-document`, { file_name: fileName });
      setIsReadyForQuery(true);
      setUploadStatus(`Document "${fileName}" is now ready for questions.`);
    } catch (error) {
      setIsReadyForQuery(false);
      setUploadStatus(`Failed to prepare document: ${error.response?.data?.error || error.message}`);
    }
  };

  // Handle clearing all uploaded files and embeddings
  const handleClearFiles = async () => {
    setClearStatus('Clearing all uploaded files and embeddings...');
    try {
      const response = await axios.delete(`${backendUrl}/clear-files`);
      setClearStatus(response.data.message);
      setUploadedFiles([]); // Clear file list in UI
      setSelectedFile(''); // Deselect any chosen file
      setIsReadyForQuery(false); // Reset query readiness
      setChatHistory([ // Reset chat history
        { type: 'bot', text: "Hi there! I'm ready to answer questions about your documents." }
      ]);
      window.location.reload(); // Reload the page to reflect changes
    } catch (error) {
      setClearStatus(`Failed to clear: ${error.response?.data?.error || error.message}`);
    }
  };

  // Handle user query submission
  const handleQuerySubmit = async (e) => {
    e.preventDefault();
    if (!query.trim()) return; // Don't send empty queries
    if (!isReadyForQuery) {
      setChatHistory((prevHistory) => [...prevHistory, { type: 'bot', text: "Please select a document and click 'Submit Selected Document' or upload a single document to begin asking questions." }]);
      return;
    }

    const userMessage = { type: 'user', text: query };
    setChatHistory((prevHistory) => [
      ...prevHistory,
      userMessage,
      { type: 'bot', text: '...', loading: true } // Loading placeholder
    ]);
    setQuery(''); // Clear query input

    try {
      setIsBotLoading(true);
      const response = await axios.post(`${backendUrl}/query`, { text: query, file_name: selectedFile });
      setChatHistory((prevHistory) => {
        // Remove the last loading bot message and add the real answer
        const updated = prevHistory.slice(0, -1);
        return [...updated, { type: 'bot', text: response.data.answer }];
      });
    } catch (error) {
      setChatHistory((prevHistory) => {
        const updated = prevHistory.slice(0, -1);
        return [...updated, { type: 'bot', text: `Error: ${error.response?.data?.error || error.message}` }];
      });
    }
    setIsBotLoading(false);
  };

  return (
    <div className="container">
      <div className="left-panel">
        {/* Toggle button for Upload Document section - now closes file list */}
        <button className="toggle-button" onClick={() => {
          setShowUploadSection(!showUploadSection);
          setShowFileListSection(false); // Close file list when upload is opened
        }}>
          {showUploadSection ? 'Hide Upload Section' : 'Show Upload Section'}
        </button>

        {/* Toggle button for File List section - now closes upload section */}
        <button className="toggle-button" onClick={() => {
          setShowFileListSection(!showFileListSection);
          setShowUploadSection(false); // Close upload section when file list is opened
        }}>
          {showFileListSection ? 'Hide Document List' : 'Show Document List'}
        </button>

        {/* Clear Files Button */}
        <button className="clear-all-button" onClick={handleClearFiles}>
          Clear All Files & Embeddings
        </button>
        {/* Display clearStatus message if it exists */}
        {clearStatus && <div id="clear-status" className="status-message">{clearStatus}</div>}

        {/* Conditional rendering for Upload Document section */}
        {showUploadSection && (
          <>
            <div className="upload-section">
              <h2>Upload Document</h2>
              <form onSubmit={handleUploadSubmit}>
                <input type="file" onChange={handleFileChange} required />
                <button type="submit">Upload</button>
              </form>
              {/* Display uploadStatus message if it exists */}
              {uploadStatus && <div id="upload-status" className="status-message">{uploadStatus}</div>}
            </div>
            <hr />
          </>
        )}

        {/* Conditional rendering for File Selection Section */}
        {showFileListSection && (
          <>
            <div className="file-selection-section">
              <h2>Select Document for Query</h2>
              {uploadedFiles.length === 0 ? (
                <p>No documents uploaded yet. Please upload a document to begin.</p>
              ) : (
                <div className="file-list">
                  {uploadedFiles.map((fileName) => (
                    <label key={fileName} className="file-item">
                      <input
                        type="radio"
                        name="selectedDocument"
                        value={fileName}
                        checked={selectedFile === fileName}
                        onChange={handleFileRadioChange}
                      />
                      <span>{fileName}</span>
                    </label>
                  ))}
                </div>
              )}
            </div>
            <hr />
          </>
        )}
      </div> {/* End of left-panel */}

      {/* Chatbot Section (Right Panel) */}
      <div className="chat-section">
        <h2>Ask a Question</h2>
        <div className="chat-window">
          {chatHistory.map((msg, index) => (
            <div key={index} className={`message ${msg.type}-message`}>
              {msg.type === 'bot'
                ? msg.loading
                  ? <span className="loading-dots">Loading<span className="dot">.</span><span className="dot">.</span><span className="dot">.</span></span>
                  : <ReactMarkdown>{msg.text}</ReactMarkdown>
                : msg.text}
            </div>
          ))}
          {/* Show a loading indicator when the bot is processing */}
          {isBotLoading && (
            <div className="message bot-message loading-message">
              {/* You can customize the loading indicator here */}
              <ReactMarkdown>Processing your request...</ReactMarkdown>
            </div>
          )}
        </div>
        <form className="query-form" onSubmit={handleQuerySubmit}>
          <input
            className="query-input"
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={isReadyForQuery ? `Ask about "${selectedFile}"...` : "Upload or select a document first..."}
            disabled={!isReadyForQuery}
            required
          />
          <button className="query-button" type="submit" disabled={!isReadyForQuery}>Send</button>
        </form>
      </div>
    </div>
  );
}

export default App;
