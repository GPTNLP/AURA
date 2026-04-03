import sys
import asyncio
from pathlib import Path

# Fix paths so it can find your core/ai folders
AGENT_DIR = Path(__file__).resolve().parent
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from ai.rag_manager import rag_manager

async def run_standalone_test():
    print("\n=== 1. INITIALIZING LIGHTRAG ===")
    success = rag_manager.initialize()
    if not success:
        print("❌ Failed to initialize LightRAG. Check your config.py model names.")
        return
    print("✅ LightRAG Initialized!")

    print("\n=== 2. TESTING TEXT INGESTION (VECTORIZATION) ===")
    test_text = (
        "AURA is an advanced robotic teaching assistant designed to help university students. "
        "It uses a Jetson Orin Nano for its brain and an ESP32 microcontroller for motor control. "
        "AURA's primary goal is to reduce instructional overhead in research environments."
    )
    print("Vectorizing dummy text...")
    try:
        # We bypass the PDF download here to purely test the local vectorization engine
        await asyncio.to_thread(rag_manager.rag_system.insert, test_text)
        print("✅ Text successfully vectorized and saved to local DB!")
    except Exception as e:
        print(f"❌ Vectorization failed: {e}")
        return

    print("\n=== 3. TESTING LOCAL LLM QUERY ===")
    query = "What hardware components make up AURA's brain and motor control?"
    print(f"User Query: '{query}'")
    print("Generating answer via local LLM...")
    
    try:
        answer = await rag_manager.query(query)
        print("\n🤖 AI RESPONSE:")
        print("-" * 40)
        print(answer)
        print("-" * 40)
        print("✅ LLM Query Successful!")
    except Exception as e:
        print(f"❌ LLM Query failed: {e}")

if __name__ == "__main__":
    asyncio.run(run_standalone_test())