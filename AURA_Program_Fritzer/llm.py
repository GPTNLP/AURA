"""
File to handle the Large Language Model being ran on-device.

Provides:
- GetSession(session_id) -> BaseChatMessageHistory
- BuildChain(llm, db, session_id) -> None
- ClearSession(session_id) -> None
"""
from typing import Dict
from langchain_core.chat_history import BaseChatMessageHistory, InMemoryChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.output_parsers import StrOutputParser

from database_bridge import CombineDocuments
from config import ANSWER_PROMPT, RETRIEVER_K

# Store for conversation history
sessions: Dict[str, InMemoryChatMessageHistory] = {}

def GetSession(session_id: str) -> BaseChatMessageHistory:
    """Get or create session history"""
    if session_id not in sessions:
        sessions[session_id] = InMemoryChatMessageHistory()
    return sessions[session_id]


def BuildChain(llm, db, session_id: str = "default"):
    """Build conversational RAG chain"""
    retriever = db.as_retriever(search_kwargs={"k": RETRIEVER_K})
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", ANSWER_PROMPT),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{question}")
    ])
    
    def get_context(question):
        docs = retriever.invoke(question)
        return CombineDocuments(docs)
    
    chain = (
        RunnablePassthrough.assign(context=lambda x: get_context(x["question"]))
        | prompt
        | llm
        | StrOutputParser()
    )
    
    chain_with_history = RunnableWithMessageHistory(
        chain,
        GetSession,
        input_messages_key="question",
        history_messages_key="history"
    )
    
    def chat(user_input: str):
        result = chain_with_history.invoke(
            {"question": user_input},
            config={"configurable": {"session_id": session_id}}
        )
        
        print("\n" + "="*60)
        print(result)
        print("="*60)
        
        docs = retriever.invoke(user_input)
        print("\nSources:")
        for i, doc in enumerate(docs[:3], 1):
            source = doc.metadata.get("source", "Unknown")
            page = doc.metadata.get("page", "?")
            print(f"{i}. {source} (Page {page})")
    
    return chat


def ClearSession(session_id: str = "default"):
    """Clear conversation history for session"""
    if session_id in sessions:
        sessions[session_id].clear()
        print(f"Cleared session: {session_id}")