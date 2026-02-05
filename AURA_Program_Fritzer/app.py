"""
Central project application, can be ran locally using inputs from console or
on the AURA with inputs from Voice to Text module.

Code for this application based on LocalLLM with RAG project:
https://github.com/amscotti/local-LLM-with-RAG
"""

import argparse
import sys
from langchain_ollama import ChatOllama

# Pull funcs from local files
from model import CheckModelAvailability
from database_bridge import InitializeDatabase
from llm import BuildChain
from lightrag import LightRAG
from config import DEFAULT_EMBEDDING_MODEL, DEFAULT_MODEL, DEFAULT_DOCS_PATH


def main(model_name: str, embedding_model: str, docs_path: str, reload: bool = False):
    """Main application loop"""
    
    print("ECEN 214 Lab Assistant")
    print("="*60)
    
    # Check models
    print("\nChecking models...")
    if not CheckModelAvailability(model_name):
        print(f"Error: Model {model_name} not available")
        sys.exit(1)
    
    if not CheckModelAvailability(embedding_model):
        print(f"Error: Embedding model {embedding_model} not available")
        sys.exit(1)
    
    # Initialize database
    print("\nInitializing document database...")
    try:
        db = InitializeDatabase(embedding_model, docs_path, reload)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    # Initialize LLM and chains
    print("\nInitializing language model...")
    llm = ChatOllama(model=model_name)
    chat = BuildChain(llm, db, session_id="main")
    lightrag = LightRAG(llm, db)
    
    print("\n" + "="*60)
    print("Ready. Ask questions or type 'quit' to exit.")
    print("Prefix with 'rag:' for enhanced retrieval mode.")
    print("="*60 + "\n")
    
    # Main loop
    while True:
        try:
            user_input = input("Question: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ["quit", "exit", "q"]:
                print("\nGoodbye!")
                break
            
            if user_input.lower().startswith("rag:"):
                # LightRAG mode
                query = user_input[4:].strip()
                if not query:
                    print("Error: No question provided after 'rag:'")
                    continue
                
                result = lightrag.generate(query)
                
                print("\n" + "="*60)
                print("ANSWER")
                print("="*60)
                print(result["answer"])
                
                print("\n" + "="*60)
                print("EVIDENCE")
                print("="*60)
                for ev in result["evidence"][:3]:
                    print(f"\n[{ev['id']}] {ev['source']} (Page {ev['page']})")
                    print(f"  Retrieval: {ev['retrieval_score']:.3f} | Overlap: {ev['overlap_score']:.3f}")
                
                print("\n" + "="*60)
                print("SOURCES")
                print("="*60)
                for i, source in enumerate(result["sources"], 1):
                    print(f"{i}. {source}")
            else:
                # Normal mode
                chat(user_input)
        
        except KeyboardInterrupt:
            print("\n\nInterrupted. Type 'quit' to exit.")
            continue
        except Exception as e:
            print(f"\nError: {e}")
            continue


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="ECEN 214 Lab Assistant - Local RAG system for Jetson Orin Nano"
    )
    
    parser.add_argument(
        "-m", "--model",
        default=DEFAULT_MODEL,
        help=f"LLM model name (default: {DEFAULT_MODEL})"
    )
    
    parser.add_argument(
        "-e", "--embedding",
        default=DEFAULT_EMBEDDING_MODEL,
        help=f"Embedding model name (default: {DEFAULT_EMBEDDING_MODEL})"
    )
    
    parser.add_argument(
        "-p", "--path",
        default=DEFAULT_DOCS_PATH,
        help=f"Documents directory (default: {DEFAULT_DOCS_PATH})"
    )
    
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Force rebuild of vector database"
    )
    
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args.model, args.embedding, args.path, args.reload)