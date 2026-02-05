"""
Streamlit UI for lab assistant demo
run using python -m streamlit run ui.py
"""

import streamlit as st
import os
from langchain_ollama import ChatOllama

from database_bridge import InitializeDatabase, SaveSession, ListSessions, LoadSession, ClearCudaCache, CombineDocuments
from llm import GetSession, ClearSession
from lightrag import LightRAG
from model import GetListOfModels
from config import DEFAULT_EMBEDDING_MODEL, DEFAULT_DOCS_PATH, DEFAULT_MODEL, CHROMA_DIR, ANSWER_PROMPT, RETRIEVER_K, LLM_TEMPERATURE, LLM_TOP_P, LLM_MAX_TOKENS

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage, AIMessage
import streamlit as st
import os

st.title("AURA")

st.set_page_config(page_title="AURA", layout="centered")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "query_count" not in st.session_state:
    st.session_state.query_count = 0

if "db" not in st.session_state:
    if os.path.isdir(CHROMA_DIR) and os.listdir(CHROMA_DIR):
        try:
            with st.spinner("Loading database..."):
                st.session_state.db = InitializeDatabase(
                    DEFAULT_EMBEDDING_MODEL,
                    DEFAULT_DOCS_PATH,
                    force_reload=False
                )
                st.success("Database loaded - embedding model unloaded")
        except:
            st.session_state.db = None
    else:
        st.session_state.db = None

if "llm" not in st.session_state:
    st.session_state.llm = ChatOllama(
            model=DEFAULT_MODEL,
            temperature=LLM_TEMPERATURE,
            top_p=LLM_TOP_P,
            num_predict=LLM_MAX_TOKENS
        )
    st.session_state.current_model = DEFAULT_MODEL

if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = "main"

# Sidebar
with st.sidebar:
    st.header("Configuration")
    
    # Model selection
    models = GetListOfModels()
    if models:
        selected_model = st.selectbox("Model", models)
    else:
        st.warning("No models found")
        selected_model = DEFAULT_MODEL
    
    if st.session_state.get("current_model") != selected_model:
        st.session_state.current_model = selected_model
        st.session_state.llm = ChatOllama(
            model=selected_model,
            temperature=LLM_TEMPERATURE,
            top_p=LLM_TOP_P,
            num_predict=LLM_MAX_TOKENS
        )
    
    st.divider()
    
    # Documents
    docs_path = st.text_input("Documents Path", DEFAULT_DOCS_PATH)
    
    if st.button("Index Documents"):
        if os.path.isdir(docs_path):
            with st.spinner("Indexing..."):
                try:
                    ClearCudaCache()
                    st.session_state.db = InitializeDatabase(
                        DEFAULT_EMBEDDING_MODEL, 
                        docs_path,
                        force_reload=True
                    )
                    st.success("Indexed - embedding model unloaded")
                except Exception as e:
                    st.error(str(e))
        else:
            st.error("Invalid path")
    
    st.divider()
    
    # Mode
    query_mode = st.radio("Retrieval Augmentation Mode", ["Normal", "Enhanced"])
    
    st.divider()
    
    # Session management
    st.subheader("Session")
    
    session_id = st.text_input("Session ID", st.session_state.current_session_id)
    
    if session_id != st.session_state.current_session_id:
        st.session_state.current_session_id = session_id
        st.session_state.messages = []
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Clear", use_container_width=True):
            ClearSession(session_id)
            st.session_state.messages = []
            st.rerun()
    
    with col2:
        # Load session button
        saved_sessions = ListSessions()
        if saved_sessions:
            if st.button("Load", use_container_width=True):
                st.session_state.show_load_dialog = True
    
    # Manual cache clear button
    if st.button("Clear GPU Cache", use_container_width=True):
        ClearCudaCache()
        st.success("Cache cleared")
    
    # Show load dialog
    if st.session_state.get("show_load_dialog") and saved_sessions:
        st.subheader("Load Session")
        for sess_id in saved_sessions:
            if st.button(sess_id, key=f"load_{sess_id}", use_container_width=True):
                try:
                    loaded_data = LoadSession(sess_id)
                    st.session_state.current_session_id = sess_id
                    
                    # Clear current session
                    ClearSession(sess_id)
                    
                    # Reload messages into session
                    session = GetSession(sess_id)
                    for msg in loaded_data.get("messages", []):
                        if msg["role"] == "user" or msg["role"] == "human":
                            session.add_message(HumanMessage(content=msg["content"]))
                        else:
                            session.add_message(AIMessage(content=msg["content"]))
                    
                    # Update UI messages
                    st.session_state.messages = []
                    for msg in loaded_data.get("messages", []):
                        st.session_state.messages.append({
                            "role": "user" if msg["role"] in ["user", "human"] else "assistant",
                            "content": msg["content"],
                            "sources": []
                        })
                    
                    st.session_state.show_load_dialog = False
                    st.success(f"Loaded {sess_id}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Load error: {str(e)}")
        
        if st.button("Cancel", use_container_width=True):
            st.session_state.show_load_dialog = False
            st.rerun()

# Main chat
if st.session_state.db is None:
    st.warning("Index documents first")
else:
    # Display history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            if "sources" in msg and msg["sources"]:
                with st.expander("Sources"):
                    for s in msg["sources"]:
                        st.text(s)
    
    # Input
    if prompt := st.chat_input("Ask a question"):
        def process_message(prompt, session_id, query_mode):
            return prompt, session_id, query_mode
        
        prompt, session_id, query_mode = process_message(prompt, session_id, query_mode)
        session_id = st.session_state.current_session_id
        
        # Auto-clear cache every 5 queries
        st.session_state.query_count += 1
        if st.session_state.query_count % 5 == 0:
            ClearCudaCache()
        
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.write(prompt)
        
        with st.chat_message("assistant"):
            try:
                sources = []
                
                if query_mode == "Normal":
                    
                    retriever = st.session_state.db.as_retriever(
                        search_kwargs={"k": RETRIEVER_K}
                    )
                    
                    prompt_template = ChatPromptTemplate.from_messages([
                        ("system", ANSWER_PROMPT),
                        MessagesPlaceholder(variable_name="history"),
                        ("human", "{question}")
                    ])
                    
                    def get_context(q):
                        docs = retriever.invoke(q)
                        return CombineDocuments(docs)
                    
                    def run_rag_chain(chain_with_history, question, session_id):
                        response_text = ""
                        for chunk in chain_with_history.stream(
                            {"question": question},
                            config={"configurable": {"session_id": session_id}}
                        ):
                            response_text += chunk if isinstance(chunk, str) else chunk
                            yield response_text

                    chain = (
                        RunnablePassthrough.assign(
                            context=lambda x: get_context(x["question"])
                        )
                        | prompt_template
                        | st.session_state.llm
                        | StrOutputParser()
                    )
                    
                    chain_with_history = RunnableWithMessageHistory(
                        chain,
                        GetSession,
                        input_messages_key="question",
                        history_messages_key="history"
                    )

                    placeholder = st.empty()

                    response_text = ""
                    for partial in run_rag_chain(chain_with_history, prompt, session_id):
                        response_text = partial
                        placeholder.write(response_text)
                    
                    docs = retriever.invoke(prompt)
                    sources = [
                        f"{d.metadata.get('source', 'Unknown')} (Page {d.metadata.get('page', '?')})" 
                        for d in docs[:3]
                    ]
                    
                    with st.expander("Sources"):
                        for s in sources:
                            st.text(s)
                
                else:
                    if "lightrag" not in st.session_state:
                        st.session_state.lightrag = LightRAG(
                            st.session_state.llm,
                            st.session_state.db
                        )
                    
                    def traced_lightrag(prompt):
                        return st.session_state.lightrag.generate(prompt)

                    result = traced_lightrag(prompt)
                    response_text = result["answer"]
                    
                    st.write(response_text)
                    
                    with st.expander("Evidence"):
                        for ev in result["evidence"][:3]:
                            st.write(f"[{ev['id']}] {ev['source']} (Page {ev['page']})")
                            st.write(f"Retrieval: {ev['retrieval_score']:.3f} | Overlap: {ev['overlap_score']:.3f}")
                    
                    sources = result["sources"]
                    with st.expander("Sources"):
                        for s in sources:
                            st.text(s)
                
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response_text,
                    "sources": sources
                })
                
                # Force save after adding message to state
                st.rerun()
                
            except Exception as e:
                st.error(str(e))
                response_text = "Error occurred"
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response_text,
                    "sources": []
                })

# Auto-save logic runs after rerun, outside the input block
if st.session_state.get("messages") and len(st.session_state.messages) > 0:
    try:
        session_id = st.session_state.current_session_id
        session = GetSession(session_id)
        
        # Get messages from LangChain session
        lc_messages = session.messages
        
        # Build save data from UI messages (more reliable)
        session_data = {"messages": []}
        
        for msg in st.session_state.messages:
            if msg["role"] in ["user", "assistant"]:
                session_data["messages"].append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        
        # Only save if we have messages
        if session_data["messages"]:
            saved_id = SaveSession(session_data, session_id)
            # Don't display anything to avoid clutter
            
    except Exception as e:
        # Silent fail for auto-save
        pass