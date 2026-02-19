# models_resave
import os
import glob 
import numpy as np
import torch
import segmentation_models_pytorch as smp
from typing_extensions import deprecated
from models import TorchModel

TORCH_DEVICE = os.environ.get('TORCH_DEVICE', 'cuda' if torch.cuda.is_available() else 'cpu')

VN_specific_models = ["unet_mixed_300ep.pth"]

handled_model = VN_specific_models[0]

def VN_specific_Unet(path):
    model = smp.Unet('resnet34', encoder_weights='imagenet', in_channels=3, classes=3)
    model.load_state_dict(torch.load(path, map_location=torch.device(TORCH_DEVICE)))
    model.to(torch.device(TORCH_DEVICE)).eval()
    return model



# TODO: remove this after testing
new_model = smp.Unet('resnet34', encoder_weights='imagenet', in_channels=3, classes=3)
new_model.load_state_dict(torch.load(os.path.join(os.path.dirname(__file__), 'models', handled_model), map_location=torch.device(TORCH_DEVICE)))
torch.save(new_model.state_dict(), os.path.join(os.path.dirname(__file__), 'models', f'{handled_model.split(".")[0]}_state_dict.pth'))
torch.save(new_model, os.path.join(os.path.dirname(__file__), 'models', f'{handled_model.split(".")[0]}_lazy.pth'))

model = VN_specific_Unet(os.path.join(os.path.dirname(__file__), 'models', handled_model))
model = torch.load(os.path.join(os.path.dirname(__file__), 'models', f'{handled_model.split(".")[0]}_lazy.pth'), map_location=torch.device(TORCH_DEVICE), weights_only=False)
model.to(torch.device(TORCH_DEVICE)).eval()
result = model(torch.randn(1, 3, 256, 256).to(TORCH_DEVICE))

model_torch = TorchModel()
model_torch.model = model
result = model_torch.evaluate(torch.randn(1, 3, 256, 256).to(TORCH_DEVICE))
print(f"Model loaded and evaluated: {result.shape}")
print(result[0,:,0,0])
print(result[0,:,0,0].sum())