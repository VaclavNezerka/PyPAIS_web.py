import os
import glob 
import torch


# Default
TORCH_DEVICE = os.environ.get('TORCH_DEVICE', 'cuda' if torch.cuda.is_available() else 'cpu')
torch_loaded_models = {}

def discover_models() -> list[str]:
    """Discover all model files in the models directory."""
    model_files = glob.glob(os.path.join(os.path.dirname(__file__), 'models', '*.pt'))
    models = [os.path.basename(file) for file in model_files]
    return models

def pop_session_from_loaded_models(session_id: str) -> None:
    """
    Remove a session from the loaded models tracking. If the session is the last one using a model, the model will be removed from memory.

    Parameters:
    - session_id (str): Unique identifier for the session to be removed.
    """
    for model_name, model_info in torch_loaded_models.items():
        if session_id in model_info["active_users"]:
            model_info["active_users"].remove(session_id)
            if not model_info["active_users"]:
                del torch_loaded_models[model_name]

def add_session_to_loaded_model(model_name: str,session_id: str) -> None:
    """
    Add a session to the loaded models tracking. If the session already exists, it will not be added again.

    Parameters:
    - session_id (str): Unique identifier for the session to be added.
    """
    torch_loaded_models[model_name]["active_users"].add(session_id)


def load_model(model_path: str, session_id: str) -> None:
    """
    Safely load a model and track its usage by session ID.

    - If the session already uses different model, it will not be loaded again.
    - If the model is already loaded for this session, it will not be loaded again.
    - If the model is already loaded for another session, it will be shared.

    Parameters:
    - model_path (str): Path to the model file.
    - session_id (str): Unique identifier for the session using the model.
    """
    
    model_name = os.path.basename(model_path)
    # Check if the model is already loaded for this session
    if model_name in torch_loaded_models:
        # session ids are stored in a set to avoid duplicates
        add_session_to_loaded_model(model_name, session_id)
    else:
        # load the model if not already loaded
        model = torch.load(model_path, map_location=torch.device(TORCH_DEVICE))
        torch_loaded_models[model_name] = {"model": model, "path": model_path, "active_users": {session_id}}

def inference(model_name: str, input_data: torch.Tensor, session_id: str) -> torch.Tensor:
    """
    Perform inference using a loaded model.

    Parameters:
    - model_name (str): Name of the model to use for inference.
    - input_data (torch.Tensor): Input data for the model.
    - session_id (str): Unique identifier for the session using the model.

    Returns:
    - torch.Tensor: Output from the model after inference.
    """
    if model_name not in torch_loaded_models:
        load_model(os.path.join(os.path.dirname(__file__), 'models', model_name), session_id)
    if session_id not in torch_loaded_models[model_name]["active_users"]:
        add_session_to_loaded_model(model_name, session_id)

    # Perform inference with the loaded model
    model = torch_loaded_models[model_name]["model"]
    return model.eval(input_data.to(TORCH_DEVICE))