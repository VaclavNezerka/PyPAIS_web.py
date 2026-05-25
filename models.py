import os
import glob 
import numpy as np
import torch
import segmentation_models_pytorch as smp
from typing_extensions import deprecated
import cv2
import albumentations as A
from albumentations.pytorch import ToTensorV2
import time
import gc

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
    
    print(len(torch_loaded_models))
    for key in keys_to_remove:
        del torch_loaded_models[key]["model"]  # Delete the model from memory
        del torch_loaded_models[key]
        gc.collect()  # Force garbage collection to free up memory
        torch.cuda.empty_cache()  # Clear GPU memory after removing the model

    print(f"Removing session {session_id} from models: {keys_to_remove}")
    print(len(torch_loaded_models))

def add_session_to_loaded_model(model_name: str,session_id: str) -> None:
    """
    Add a session to the loaded models tracking. If the session already exists, it will not be added again.

    Parameters:
    - session_id (str): Unique identifier for the session to be added.
    """
    torch_loaded_models[model_name]["active_users"].add(session_id)

normalize_tf = A.Compose([A.Normalize(), ToTensorV2()])
# def sliding_window_inference(image, model, device, patch_size=512, stride=256, normalize_transform=None,
#                              stripped_threshold=0.2):
def sliding_window_inference(image, model, device, patch_size=1024, stride=512, normalize_transform=None,
                             stripped_threshold=0.2):
    H, W = image.shape[:2]

    # Pad image to be cleanly divisible by patch_size and stride
    pad_h = (patch_size - H % patch_size) % patch_size
    pad_w = (patch_size - W % patch_size) % patch_size
    img_pad = cv2.copyMakeBorder(image, 0, pad_h, 0, pad_w, cv2.BORDER_REFLECT)
    H_pad, W_pad = img_pad.shape[:2]

    prob_map = np.zeros((3, H_pad, W_pad), dtype=np.float32)
    count_map = np.zeros((H_pad, W_pad), dtype=np.float32)

    for y in range(0, H_pad - patch_size + 1, stride):
        for x in range(0, W_pad - patch_size + 1, stride):
            patch = img_pad[y:y + patch_size, x:x + patch_size]

            if normalize_transform:
                aug = normalize_transform(image=patch)
                inp = aug['image'].unsqueeze(0).to(device)
            else:
                inp = torch.from_numpy(patch).permute(2, 0, 1).unsqueeze(0).float().to(device) / 255.0

            with torch.no_grad():
                logits = model(inp)
                # Softmax converts raw logits into probabilities (0.0 to 1.0) for each class
                probs = torch.softmax(logits, dim=1).cpu().numpy()[0]

            prob_map[:, y:y + patch_size, x:x + patch_size] += probs
            count_map[y:y + patch_size, x:x + patch_size] += 1

    # Average overlapping patches
    np.maximum(count_map, 1, out=count_map)
    prob_map /= count_map[None, ...]
    prob_map = prob_map[:, :H, :W]

    # --- THRESHOLD LOGIC ---
    # First, get the standard argmax prediction (the class with the highest probability wins)
    preds = np.argmax(prob_map, axis=0).astype(np.uint8)

    # If a custom threshold is provided, override the prediction for the Stripped class (Index 2)
    if stripped_threshold:
        # If the probability for 'Stripped' is greater than our threshold, force it to be 'Stripped'
        # This overrides the background or aggregate classes if stripped probability is high enough
        preds[prob_map[2, :, :] > stripped_threshold] = 2

    # delete the unused variables to free up memory
    print(f"Allocated memory: {torch.cuda.memory_allocated() / 1024**2:.2f} MB")
    print(f"Cached memory: {torch.cuda.memory_reserved() / 1024**2:.2f} MB")
    del prob_map, count_map, probs, logits, inp, patch
    # gc.collect()  # Force garbage collection
    torch.cuda.empty_cache()  # Clear GPU memory after inference
    print(f"Allocated memory: {torch.cuda.memory_allocated() / 1024**2:.2f} MB")
    print(f"Cached memory: {torch.cuda.memory_reserved() / 1024**2:.2f} MB")

    return preds

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
    print("len(torch_loaded_models)")
    print(len(torch_loaded_models))
    if model_name not in torch_loaded_models:
        load_model(os.path.join(os.path.dirname(__file__), 'models', model_name), session_id)
    if session_id not in torch_loaded_models[model_name]["active_users"]:
        add_session_to_loaded_model(model_name, session_id)

    # Perform inference with the loaded model
    model = torch_loaded_models[model_name]["model"]
    print(torch_loaded_models)
    # return model.evaluate(input_data.to(TORCH_DEVICE))
    print(type(input_data))
    input_data = input_data.transpose(1, 0, 2) 
    # input_data = cv2.cvtColor(input_data, cv2.COLOR_BGR2RGB)
    
    prediction: np.ndarray = sliding_window_inference(
        image=input_data,
        model=model.model, 
        normalize_transform=normalize_tf,
        device=TORCH_DEVICE
    )
    prediction = prediction.T
    
    # delete the unused model
    print(len(torch_loaded_models))
    pop_session_from_loaded_models(session_id)
    print(len(torch_loaded_models))
    return prediction

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
    # try:
    #     prediction = prediction.squeeze(0).cpu().numpy()  # Remove batch dimension and convert to numpy array
    #     prediction = prediction.squeeze(0).cpu().numpy()  # Remove batch dimension and convert to numpy array
    # except:
    #     pass
    # boolean_prediction = np.argmax(prediction, axis=0)  # Get the class with the highest probability

    # BUG: OLD 
    # background_mask = boolean_prediction == 2
    # asphalt_mask = boolean_prediction == 1
    # aggregate_mask = boolean_prediction == 0
    background_mask = prediction == 0
    asphalt_mask = prediction == 1
    aggregate_mask = prediction == 2

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
    # input_data = torch.from_numpy(np_image).unsqueeze(0).float()  # Add batch channel dimension
    # input_data = input_data.permute(0, 3, 1, 2)  # Change to torch (batch_size, channels, height, width)
    # input_data = input_data.permute(0, 3, 2, 1)  # Change to torch (batch_size, channels, height, width)
    input_data = np_image
    print("input_data.shape")
    print(input_data.shape)

    model_prediction = inference(model_name=model_name,
                                 input_data=input_data,
                                 session_id=session_id)
    # model_prediction= model_prediction.permute(0, 1, 3, 2 )  # Change back to (batch_size, height, width, channels)
    # get model prediction and save it to the sessions
    asphalt_mask, aggregate_mask, background_mask = postprocess_model_prediction(model_prediction)
    return asphalt_mask, aggregate_mask, background_mask

