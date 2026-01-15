import os
import glob 
import numpy as np
import torch
import segmentation_models_pytorch as smp
from typing_extensions import deprecated

# Default
TORCH_DEVICE = os.environ.get('TORCH_DEVICE', 'cuda' if torch.cuda.is_available() else 'cpu')
torch_loaded_models = {}

def discover_models() -> list[str]:
    """Discover all model files in the models directory."""
    model_files = glob.glob(os.path.join(os.path.dirname(__file__), 'models', '*.pth'))
    models = [os.path.basename(file) for file in model_files]
    return models

def pop_session_from_loaded_models(session_id: str) -> None:
    """
    Remove a session from the loaded models tracking. If the session is the last one using a model, the model will be removed from memory.

    Parameters:
    - session_id (str): Unique identifier for the session to be removed.
    """

    keys_to_remove = []

    for model_name, model_info in torch_loaded_models.items():
        if session_id in model_info["active_users"]:
            model_info["active_users"].remove(session_id)
            if not model_info["active_users"]:
                keys_to_remove.append(model_name)

    for key in keys_to_remove:
        del torch_loaded_models[key]

def add_session_to_loaded_model(model_name: str,session_id: str) -> None:
    """
    Add a session to the loaded models tracking. If the session already exists, it will not be added again.

    Parameters:
    - session_id (str): Unique identifier for the session to be added.
    """
    torch_loaded_models[model_name]["active_users"].add(session_id)


class TorchModel(torch.nn.Module):
    """
    Base class for all Torch models. It provides a method to evaluate the model.
    """

    def __init__(self):
        super().__init__()
        self.model = None

    def __call__(self, *args, **kwds):
        return self.evaluate(*args, **kwds)

    def evaluate(self, input_data: torch.Tensor) -> torch.Tensor:
        """
        Perform inference on the input data using the loaded model.

        Parameters:
        - input_data (torch.Tensor): Input tensor for the model.

        Returns:
        - torch.Tensor: Output tensor from the model. Of shape (N, C, H, W) where N is batch size, C is number of classes, H and W are height and width.
        """
        self.model.eval()  # Set the model to evaluation mode
        if self.model is None:
            raise ValueError("Model is not loaded.")
        
        with torch.no_grad():
            # assuming the model is returning the logits
            logits = self.model(input_data.to(TORCH_DEVICE))
            probabilities = torch.nn.functional.softmax(logits, dim=1)
            return probabilities

# VN_specific_models = ["unet_optimal_(v5).pth"]
# def VN_specific_Unet(path):
#     model = smp.Unet('resnet34', encoder_weights='imagenet', in_channels=3, classes=3)
#     model.load_state_dict(torch.load(path, map_location=torch.device(TORCH_DEVICE)))
#     model.to(torch.device(TORCH_DEVICE)).eval()
#     return model

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
        model = TorchModel()
        # model.load_state_dict(torch.load(model_path, map_location=torch.device(TORCH_DEVICE)))
        model.model = torch.load(model_path, map_location=torch.device(TORCH_DEVICE), weights_only=False)
        model.to(torch.device(TORCH_DEVICE)).eval()
        torch_loaded_models[model_name] = {"model": model, "path": model_path, "active_users": {session_id}}


# TODO: remove this after testing
# new_model = smp.Unet('resnet34', encoder_weights='imagenet', in_channels=3, classes=3)
# new_model.load_state_dict(torch.load(os.path.join(os.path.dirname(__file__), 'models', 'unet_optimal_(v5).pth'), map_location=torch.device(TORCH_DEVICE)))
# torch.save(new_model.state_dict(), os.path.join(os.path.dirname(__file__), 'models', 'unet_optimal_state_dict.pth'))
# torch.save(new_model, os.path.join(os.path.dirname(__file__), 'models', 'unet_optimal_lazy.pth'))

# # model = VN_specific_Unet(os.path.join(os.path.dirname(__file__), 'models', 'unet_optimal_(v5).pth'))
# model = torch.load(os.path.join(os.path.dirname(__file__), 'models', 'unet_optimal_lazy.pth'), map_location=torch.device(TORCH_DEVICE), weights_only=False)
# model.to(torch.device(TORCH_DEVICE)).eval()
# result = model(torch.randn(1, 3, 256, 256).to(TORCH_DEVICE))

# model_torch = TorchModel()
# model_torch.model = model
# result = model_torch.evaluate(torch.randn(1, 3, 256, 256).to(TORCH_DEVICE))
# print(f"Model loaded and evaluated: {result.shape}")
# print(result[0,:,0,0])
# print(result[0,:,0,0].sum())

def inference(model_name: str, input_data: torch.Tensor, session_id: str) -> torch.Tensor:
    """
    Perform inference using a loaded model.

    Parameters:
    - model_name (str): Name of the model to use for inference.
    - input_data (torch.Tensor): Input data for the model.
    - session_id (str): Unique identifier for the session using the model.

    Returns:
    - torch.Tensor: Output from the model after inference. Of shape (N, C, H, W) where N is batch size, C is number of classes, H and W are height and width.
    """
    if model_name not in torch_loaded_models:
        load_model(os.path.join(os.path.dirname(__file__), 'models', model_name), session_id)
    if session_id not in torch_loaded_models[model_name]["active_users"]:
        add_session_to_loaded_model(model_name, session_id)

    # Perform inference with the loaded model
    model = torch_loaded_models[model_name]["model"]
    return model.evaluate(input_data.to(TORCH_DEVICE))

def postprocess_model_prediction(prediction: torch.Tensor):
    """
    Postprocess the model prediction to save separated masks.

    
    Parameters:
    prediction (torch.Tensor): 
        expected to be a tensor with shape (batch_size, num_classes, height, width).
        containig the probabilities for each class.
        the class are expected
        - 0 is asphalt, 
        - 1 is aggregate,
        - 2 is background

    """
    prediction = prediction.squeeze(0).cpu().numpy()  # Remove batch dimension and convert to numpy array
    boolean_prediction = np.argmax(prediction, axis=0)  # Get the class with the highest probability

    background_mask = boolean_prediction == 2
    asphalt_mask = boolean_prediction == 1
    aggregate_mask = boolean_prediction == 0

    return asphalt_mask, aggregate_mask, background_mask

def inference_on_numpy(np_image: np.ndarray, model_name: str, session_id: int) -> tuple:
    """
    Perform inference on the given numpy image using the specified model.
    Parameters:
    -----------
        np_image (np.ndarray): The input image as a numpy array.
        model_name (str): The name of the model to use for inference.
        session_id (int): The session ID for the user.

    Returns:
    --------
        tuple: A tuple containing asphalt_mask, aggregate_mask, and background_mask.
    """
    input_data = torch.from_numpy(np_image).unsqueeze(0).float()  # Add batch channel dimension
    input_data = input_data.permute(0, 3, 1, 2)  # Change to torch (batch_size, channels, height, width)
    
    print("input_data.shape")
    print(input_data.shape)

    model_prediction = inference(model_name=model_name,
                                 input_data=input_data,
                                 session_id=session_id)
    
    # get model prediction and save it to the sessions
    asphalt_mask, aggregate_mask, background_mask = postprocess_model_prediction(model_prediction)
    return asphalt_mask, aggregate_mask, background_mask

