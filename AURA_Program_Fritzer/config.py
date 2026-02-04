"""
Configuration file for the AURA project.
This file contains any prompts, settings, & constants to be used across the app.
"""

from langchain_core.prompts import PromptTemplate

############################
###  Formatting Prompts  ###
############################

DEFAULT_DOC_PROMPT = PromptTemplate.from_template(
    template="Source: {source}, Page {page}:\n{page_content}"
)

#For standard RAG
ANSWER_PROMPT = """You are answering questions about ECEN 214 lab procedures and concepts.

Use ONLY the information in the context below. Do not add outside knowledge or make assumptions.
If the context does not contain the answer, say "The provided documents do not contain this information."

Present facts directly. Do not use phrases like "it appears that" or "based on the evidence" - just state the information.
For calculations, show clear steps using the formulas from the context.

Context:
{context}

Question: {question}

Answer (be direct and factual):"""

#LightRAG vectorization requests a different type of prompting
LIGHTRAG_PROMPT = """Answer the question using the evidence provided below. If the evidence is missing
necessary formulas or concepts, use standard domain knowledge such as Ohm's Law 
or basic circuit rules.

Rules:
1. State facts directly without hedging ("The voltage is...")
2. For calculations, clearly show each step
3. If information is missing, state what is missing
4. Do NOT fabricate components or concepts not mentioned (no invented capacitors)
5. Keep answers concise and accurate
6. Use plain text formatting for formulas even if a source doesnt (V = I*R)
7. Prefer consistent current rules in circuits (series: same current, parallel: same voltage)

{evidence}

Question: {question}

Direct answer:
"""

#####################################
###  Database & Storage Settings  ###
#####################################

#Chunking for RAG
CHUNK_SIZE = 600
CHUNK_OVERLAP = 100

#Adjust based on how many docs each should retrieve
RETRIEVER_K = 8
LIGHTRAG_K = 6

#Models Used
DEFAULT_MODEL = "llama3.2:1b"  # Use Llama3.2 3B model per Vishuam, ensure the parameters
DEFAULT_EMBEDDING_MODEL = "nomic-embed-text"

# LM parameters for better output
LLM_TEMPERATURE = 0.05  # Low temperature = more factual
LLM_TOP_P = 0.85        # Reduced randomness
LLM_MAX_TOKENS = 512   # Reasonable response length

#Make sure these always align with folders in local/remote DB
DEFAULT_DOCS_PATH = "ECEN_214_Docs"
STORAGE_DIR = "storage"
CHROMA_DIR = "storage/chroma"
SESSIONS_DIR = "storage/sessions"