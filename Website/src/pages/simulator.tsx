import React, { useState } from 'react';

export default function Simulator() {
  const [query, setQuery] = useState("");
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);

  const handleSearch = async () => {
    if (!query.trim()) return;
    
    // Add user message to UI immediately
    const newHistory = [...history, { role: 'user', content: query }];
    setHistory(newHistory);
    setQuery("");
    setLoading(true);

    try {
      // Calls the Admin Backend's simulation endpoint
      const res = await fetch("http://localhost:8000/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: newHistory[newHistory.length - 1].content }),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Failed to generate response");
      }

      const data = await res.json();
      
      setHistory([...newHistory, { 
        role: 'ai', 
        content: data.answer,
        sources: data.sources 
      }]);
    } catch (err) {
      setHistory([...newHistory, { 
        role: 'error', 
        content: `Simulation Error: ${err.message}` 
      }]);
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-slate-100 p-8 font-sans flex flex-col items-center">
      <div className="w-full max-w-4xl bg-white rounded-xl shadow-lg flex flex-col h-[85vh]">
        
        {/* Header */}
        <div className="p-6 border-b border-slate-200 bg-slate-50 rounded-t-xl">
          <h1 className="text-2xl font-bold text-slate-800">Edge Device Simulator</h1>
          <p className="text-sm text-slate-500 mt-1">
            Test the RAG pipeline and compiled database locally before deploying to the Jetson Nano.
          </p>
        </div>

        {/* Chat History */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-slate-50">
          {history.length === 0 && (
            <div className="text-center text-slate-400 mt-20">
              <p>Database loaded. Send a message to test the AURA model.</p>
            </div>
          )}
          
          {history.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[80%] rounded-2xl p-4 shadow-sm ${
                msg.role === 'user' 
                  ? 'bg-blue-600 text-white rounded-br-none' 
                  : msg.role === 'error'
                  ? 'bg-red-50 text-red-700 border border-red-200 rounded-bl-none'
                  : 'bg-white border border-slate-200 text-slate-700 rounded-bl-none'
              }`}>
                <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                
                {/* Source Citations */}
                {msg.sources && msg.sources.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-slate-100 text-xs text-slate-500 font-mono">
                    <span className="font-semibold">Sources:</span> {msg.sources.join(", ")}
                  </div>
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-white border border-slate-200 text-slate-500 rounded-2xl rounded-bl-none p-4 shadow-sm animate-pulse">
                AURA is thinking...
              </div>
            </div>
          )}
        </div>
        
        {/* Input Area */}
        <div className="p-4 bg-white border-t border-slate-200 rounded-b-xl">
          <div className="flex gap-3">
            <input 
              className="flex-1 p-3 rounded-lg bg-slate-100 border-transparent focus:bg-white focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none transition"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask a question about the lab documents..."
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              disabled={loading}
            />
            <button 
              onClick={handleSearch}
              disabled={loading || !query.trim()}
              className="bg-blue-600 text-white px-6 py-3 rounded-lg font-bold hover:bg-blue-700 transition disabled:opacity-50 shadow-sm"
            >
              Test Model
            </button>
          </div>
        </div>
        
      </div>
    </div>
  );
}