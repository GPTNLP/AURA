import React, { useState, useEffect } from 'react';

export default function AdminConsole() {
  const [files, setFiles] = useState(null);
  const [status, setStatus] = useState("Awaiting input...");
  const [nanoOnline, setNanoOnline] = useState(false);
  const [dbBuilt, setDbBuilt] = useState(false);

  // Poll Jetson Nano Status
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

  // Step 1: Upload PDFs
  const handleUpload = async () => {
    if (!files || files.length === 0) {
      setStatus("Please select files first.");
      return;
    }
    setStatus("Uploading PDFs to staging area...");
    
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
        setStatus(`Successfully uploaded ${files.length} files. Ready to build database.`);
        setDbBuilt(false); // Reset build status on new upload
      } else {
        setStatus("Upload failed.");
      }
    } catch (err) {
      setStatus("Error connecting to Python backend.");
    }
  };

  // Step 2: Build Local Chroma DB (For Simulator)
  const handleBuild = async () => {
    try {
      setStatus("Building local Chroma DB from PDFs. This may take a minute...");
      const res = await fetch("http://localhost:8000/api/build", { method: "POST" });
      if (!res.ok) throw new Error("Failed to build database.");
      
      setStatus("Local Chroma DB created successfully! You can now test it in the Simulator.");
      setDbBuilt(true);
    } catch (err) {
      setStatus("Build Error: " + err.message);
    }
  };

  // Step 3: Send to Jetson Nano
  const handleDeploy = async () => {
    try {
      setStatus("Zipping local Chroma DB and pushing to Jetson Nano...");
      const res = await fetch("http://localhost:8000/api/deploy", { method: "POST" });
      if (!res.ok) throw new Error("Failed to deploy to Nano.");
      
      setStatus("Deployment Complete! The Jetson Nano is now running the new database locally.");
    } catch (err) {
      setStatus("Deployment Error: " + err.message);
    }
  };

  return (
    <div className="min-h-screen bg-slate-100 p-8 font-sans">
      <div className="max-w-4xl mx-auto bg-white rounded-xl shadow-lg p-8">
        
        {/* Header */}
        <div className="flex justify-between items-center mb-8 pb-4 border-b border-slate-200">
          <div>
            <h1 className="text-3xl font-bold text-slate-800">Knowledge Base Manager</h1>
            <p className="text-slate-500 mt-1">Upload PDFs, build the vector database, and deploy to edge.</p>
          </div>
          <div className={`px-4 py-2 rounded-full text-sm font-bold flex items-center gap-2 ${nanoOnline ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
            <span className={`h-2 w-2 rounded-full ${nanoOnline ? 'bg-green-600' : 'bg-red-600'} animate-pulse`}></span>
            {nanoOnline ? "Nano Online (WiFi Connected)" : "Nano Offline (Local Mode)"}
          </div>
        </div>

        {/* 3-Step Pipeline */}
        <div className="space-y-6">
          
          {/* Step 1: Upload */}
          <div className="p-6 border border-slate-200 rounded-lg bg-slate-50">
            <h2 className="text-lg font-bold text-slate-700 mb-2">Step 1: Stage Documents</h2>
            <p className="text-sm text-slate-500 mb-4">Select the lab PDFs you want the AI to learn from.</p>
            <div className="flex gap-4 items-center">
              <input 
                type="file" 
                multiple 
                accept=".pdf,.txt"
                onChange={(e) => setFiles(e.target.files)} 
                className="block w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-slate-200 file:text-slate-700 hover:file:bg-slate-300 cursor-pointer"
              />
              <button onClick={handleUpload} className="bg-slate-700 text-white px-6 py-2 rounded-md font-medium hover:bg-slate-800 transition whitespace-nowrap">
                Upload PDFs
              </button>
            </div>
          </div>

          {/* Step 2: Build Local */}
          <div className="p-6 border border-slate-200 rounded-lg bg-slate-50 flex justify-between items-center">
            <div>
              <h2 className="text-lg font-bold text-slate-700 mb-1">Step 2: Build Local Database</h2>
              <p className="text-sm text-slate-500">Creates the Chroma DB locally for the Simulator to use.</p>
            </div>
            <button 
              onClick={handleBuild} 
              className="bg-blue-600 text-white px-6 py-2 rounded-md font-medium hover:bg-blue-700 transition"
            >
              Build Chroma DB
            </button>
          </div>

          {/* Step 3: Deploy to Edge */}
          <div className="p-6 border border-slate-200 rounded-lg bg-slate-50 flex justify-between items-center">
            <div>
              <h2 className="text-lg font-bold text-slate-700 mb-1">Step 3: Deploy to Jetson Nano</h2>
              <p className="text-sm text-slate-500">Sends a copy of the built database to the physical robot.</p>
            </div>
            <button 
              onClick={handleDeploy} 
              disabled={!nanoOnline || !dbBuilt}
              className={`px-6 py-2 rounded-md font-medium transition ${
                nanoOnline && dbBuilt 
                  ? 'bg-green-600 text-white hover:bg-green-700' 
                  : 'bg-slate-300 text-slate-500 cursor-not-allowed'
              }`}
              title={!nanoOnline ? "Nano is offline" : !dbBuilt ? "Build DB first" : ""}
            >
              Sync to Nano
            </button>
          </div>
          
          {/* Status Terminal */}
          <div className="bg-slate-900 p-4 rounded-lg shadow-inner mt-6">
            <div className="text-xs text-slate-400 mb-1">System Terminal Output</div>
            <div className="font-mono text-sm text-green-400 min-h-[24px]">
              > {status}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}