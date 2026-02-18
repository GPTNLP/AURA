import React, { useState, useEffect } from 'react';

export default function AdminConsole() {
  const [files, setFiles] = useState(null);
  const [status, setStatus] = useState("");
  const [nanoOnline, setNanoOnline] = useState(false);

  // Poll Jetson Nano Status via the Admin Backend
  useEffect(() => {
    const checkStatus = async () => {
      try {
        const res = await fetch("http://localhost:8000/api/nano-status");
        if (res.ok) {
          const data = await res.json();
          setNanoOnline(data.online);
        } else {
          setNanoOnline(false);
        }
      } catch {
        setNanoOnline(false);
      }
    };
    
    const timer = setInterval(checkStatus, 5000);
    checkStatus();
    return () => clearInterval(timer);
  }, []);

  const handleUpload = async () => {
    if (!files) return;
    setStatus("Uploading documents to staging...");
    
    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
      formData.append("files", files[i]);
    }

    try {
      const res = await fetch("http://localhost:8000/api/upload", {
        method: "POST",
        body: formData,
      });
      if (res.ok) {
        setStatus("Files uploaded. Ready to build database.");
      } else {
        setStatus("Upload failed.");
      }
    } catch (err) {
      setStatus("Error connecting to local Python backend.");
    }
  };

  const handleBuildAndDeploy = async () => {
    try {
      setStatus("Building Vector Database (This may take a minute)...");
      let res = await fetch("http://localhost:8000/api/build", { method: "POST" });
      if (!res.ok) throw new Error("Failed to build database.");
      
      setStatus("Zipping and Pushing to Jetson Nano...");
      res = await fetch("http://localhost:8000/api/deploy", { method: "POST" });
      if (!res.ok) throw new Error("Failed to deploy to Nano.");
      
      setStatus("Deployment Complete! Nano is running the latest knowledge base.");
    } catch (err) {
      setStatus("Error: " + err.message);
    }
  };

  return (
    <div className="min-h-screen bg-slate-100 p-8 font-sans">
      <div className="max-w-4xl mx-auto bg-white rounded-xl shadow-lg p-8">
        
        {/* Header */}
        <div className="flex justify-between items-center mb-8 pb-4 border-b border-slate-200">
          <h1 className="text-3xl font-bold text-slate-800">AURA Admin Control</h1>
          <div className={`px-4 py-2 rounded-full text-sm font-bold flex items-center gap-2 ${nanoOnline ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
            <span className={`h-2 w-2 rounded-full ${nanoOnline ? 'bg-green-600' : 'bg-red-600'} animate-pulse`}></span>
            {nanoOnline ? "Nano Online (WiFi Connected)" : "Nano Offline (Local Mode)"}
          </div>
        </div>

        {/* Control Panel */}
        <div className="space-y-6">
          <div className="border-2 border-dashed border-slate-300 rounded-lg p-8 text-center bg-slate-50 transition hover:bg-slate-100">
            <h2 className="text-xl font-semibold text-slate-700 mb-4">Knowledge Base Sync</h2>
            <p className="text-sm text-slate-500 mb-6">Upload lab documents to vectorize and push directly to the Jetson Nano.</p>
            
            <input 
              type="file" 
              multiple 
              onChange={(e) => setFiles(e.target.files)} 
              className="mb-6 block w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 cursor-pointer"
            />
            
            <div className="flex gap-4 justify-center">
              <button 
                onClick={handleUpload} 
                className="bg-slate-700 text-white px-6 py-2 rounded-lg font-medium hover:bg-slate-800 transition shadow-sm"
              >
                1. Stage Documents
              </button>
              <button 
                onClick={handleBuildAndDeploy} 
                disabled={!nanoOnline}
                className={`px-6 py-2 rounded-lg font-medium transition shadow-sm ${nanoOnline ? 'bg-blue-600 text-white hover:bg-blue-700' : 'bg-slate-300 text-slate-500 cursor-not-allowed'}`}
                title={!nanoOnline ? "Nano must be online to deploy" : ""}
              >
                2. Build & Deploy to Edge
              </button>
            </div>
          </div>
          
          {/* Status Terminal */}
          <div className="bg-slate-900 p-4 rounded-lg shadow-inner">
            <div className="text-xs text-slate-400 mb-1">System Terminal Output</div>
            <div className="font-mono text-sm text-green-400 min-h-[24px]">
              {status ? `> ${status}` : "> System idle. Awaiting documents..."}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}