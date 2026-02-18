"""
File to maintain the model and ensure functionality of ollama integration.
Provides:
- CheckLocalAvailability(modelName) -> bool
- CheckModelAvailability(modelName) -> bool
- GetListOfModels() -> list[str]
- PullModel(modelName) -> bool
"""
import ollama
from tqdm import tqdm
from typing import List

#Helper Functions
def CheckLocalAvailability(modelName: str) -> bool:
    """
    Return True if the model is available locally via ollama
    """
    try:
        ollama.show(model=modelName)
        return True
    except Exception:
        return False
        
def CheckModelAvailability(modelName: str) -> bool:
    """
    Ensure the specified model is available locally, attempt to pull it if not.
    Return True when the model becomes available locally (with or without pulling)
    Return False if the model couldnt be found nor pulled.
    """

    if CheckLocalAvailability(modelName):
        return True
    
    try:
        pulled=PullModel(modelName)
    except Exception:
        pulled = False
    
    if pulled and CheckLocalAvailability(modelName):
        return True
    
    print(f"Failed to get model {modelName}")
    return False
    

def GetListOfModels() -> List[str]:
    """
    Return a list of model names from Ollama service.
    If service cant be contacted, return an empty list
    """
    try:
        response = ollama.list()
        models = response.get("models", [])
        
        model_names = []
        for m in models:
            if "name" in m:
                model_names.append(m["name"])
            elif "model" in m:
                model_names.append(m["model"])
        
        return model_names
    except Exception as e:
        print(f"Error getting models: {e}")
        return []

def PullModel(modelName: str) -> bool:
    """
    Attempt to pull modelName from Ollama hub.
    Stream progress and returns True or False depending on success.
    """
    try:
        currDigest = ""
        bars = {}

        for progress in ollama.pull(modelName, stream=True):
            digest = progress.get("digest", "")
            
            if digest != currDigest and currDigest in bars:
                bars[currDigest].close()
            
            if not digest:
                status = progress.get("status")
                if status:
                    print(status)
                continue
            
            if digest not in bars and (total := progress.get("total")):
                bars[digest] = tqdm(
                    total=total, 
                    desc=f"Pulling {digest[7:19]}", 
                    unit="B", 
                    unit_scale=True
                )
            
            if completed := progress.get("completed"):
                bars[digest].update(completed - bars[digest].n)
            
            currDigest = digest

        for bar in bars.values():
            bar.close()

        print(f"Successfully pulled {modelName}")
        return True
        
    except Exception as e:
        print(f"Failed to pull {modelName}: {e}")
        return False
