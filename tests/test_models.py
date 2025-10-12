import pytest
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)).split('tests')[0])
import tempfile
import shutil
import torch
from unittest.mock import patch, MagicMock
import models
from models import discover_models, pop_session_from_loaded_models, add_session_to_loaded_model, load_model, inference, TORCH_DEVICE
import numpy as np


@pytest.fixture
def temp_models_dir():
    """Create a temporary models directory with test model files."""
    temp_dir = tempfile.mkdtemp()
    models_dir = os.path.join(temp_dir, 'models')
    os.makedirs(models_dir)
    
    # Create dummy model files
    test_files = ['model1.pth', 'model2.pth', 'not_a_model.txt']
    for file in test_files:
        with open(os.path.join(models_dir, file), 'w') as f:
            f.write('dummy content')
    
    yield temp_dir, models_dir
    
    # Cleanup
    shutil.rmtree(temp_dir)

@pytest.fixture
def reset_torch_loaded_models():
    """Reset the global torch_loaded_models before each test."""
    original_models = models.torch_loaded_models.copy()
    models.torch_loaded_models.clear()
    yield
    models.torch_loaded_models = original_models


class TestDiscoverModels:
    
    @patch('models.os.path.dirname')
    @patch('models.glob.glob')
    def test_discover_models_returns_model_files(self, mock_glob, mock_dirname):
        """Test that discover_models returns only .pth files."""
        mock_dirname.return_value = '/fake/path'
        mock_glob.return_value = [
            '/fake/path/models/model1.pth',
            '/fake/path/models/model2.pth'
        ]
        
        result = discover_models()
        
        assert result == ['model1.pth', 'model2.pth']
        mock_glob.assert_called_once_with('/fake/path/models/*.pth')
    
    def test_discover_models_empty_directory(self):
        """Test discover_models with empty models directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            empty_models_dir = os.path.join(temp_dir, 'models')
            os.makedirs(empty_models_dir)
            
            with patch('models.os.path.dirname', return_value=temp_dir):
                result = discover_models()
                assert result == []


class TestPopSessionFromLoadedModels:
    
    def test_pop_session_removes_session(self, reset_torch_loaded_models):
        """Test that pop_session removes a session from active users."""
        
        models.torch_loaded_models = {
            'model1.pth': {
                'model': MagicMock(),
                'path': '/path/to/model1.pth',
                'active_users': {'session1', 'session2'}
            }
        }
        
        pop_session_from_loaded_models('session1')
        
        assert 'session1' not in models.torch_loaded_models['model1.pth']['active_users']
        assert 'session2' in models.torch_loaded_models['model1.pth']['active_users']
    
    def test_pop_session_removes_model_when_no_users(self, reset_torch_loaded_models):
        """Test that the model is removed when no active users remain."""
        models.torch_loaded_models = {
            'model1.pth': {
                'model': MagicMock(),
                'path': '/path/to/model1.pth',
                'active_users': {'session1'}
            }
        }
        
        pop_session_from_loaded_models('session1')
        
        assert 'model1.pth' not in models.torch_loaded_models
    
    def test_pop_session_nonexistent_session(self, reset_torch_loaded_models):
        """Test popping a session that doesn't exist."""
        models.torch_loaded_models = {
            'model1.pth': {
                'model': MagicMock(),
                'path': '/path/to/model1.pth',
                'active_users': {'session1'}
            }
        }
        
        # Should not raise an exception
        pop_session_from_loaded_models('nonexistent_session')
        
        # Model should still exist
        assert 'model1.pth' in models.torch_loaded_models
        assert 'session1' in models.torch_loaded_models['model1.pth']['active_users']


class TestAddSessionToLoadedModel:
    
    def test_add_session_to_existing_model(self, reset_torch_loaded_models):
        """Test adding a session to an existing model."""
        models.torch_loaded_models = {
            'model1.pth': {
                'model': MagicMock(),
                'path': '/path/to/model1.pth',
                'active_users': {'session1'}
            }
        }
        
        add_session_to_loaded_model('model1.pth', 'session2')
        
        assert 'session2' in models.torch_loaded_models['model1.pth']['active_users']
        assert len(models.torch_loaded_models['model1.pth']['active_users']) == 2
    
    def test_add_duplicate_session(self, reset_torch_loaded_models):
        """Test that adding the same session twice doesn't create duplicates."""
        models.torch_loaded_models = {
            'model1.pth': {
                'model': MagicMock(),
                'path': '/path/to/model1.pth',
                'active_users': {'session1'}
            }
        }
        
        add_session_to_loaded_model('model1.pth', 'session1')
        
        # Should still only have one instance
        assert len(models.torch_loaded_models['model1.pth']['active_users']) == 1


class TestLoadModel:
    
    @patch('models.torch.load')
    # @patch('models.torch.nn.Module.load_state_dict')
    def test_load_new_model(self, mock_torch_load, reset_torch_loaded_models):
        """Test loading a new model."""
        mock_model = MagicMock()
        mock_torch_load.return_value = mock_model
        # mock_load_state_dict.return_value = None
        
        load_model('/path/to/model1.pth', 'session1')

        assert 'model1.pth' in models.torch_loaded_models
        assert isinstance(models.torch_loaded_models['model1.pth']['model'], torch.nn.Module)
        models.torch_loaded_models['model1.pth']['model'].model == mock_model
        assert 'session1' in models.torch_loaded_models['model1.pth']['active_users']
        mock_torch_load.assert_called_once_with('/path/to/model1.pth', map_location=torch.device(TORCH_DEVICE), weights_only=False)
    
    @patch('models.torch.load')
    def test_load_existing_model(self, mock_torch_load, reset_torch_loaded_models):
        """Test adding a session to an already loaded model."""
        mock_model = MagicMock()
        models.torch_loaded_models = {
            'model1.pth': {
                'model': mock_model,
                'path': '/path/to/model1.pth',
                'active_users': {'session1'}
            }
        }
        
        load_model('/path/to/model1.pth', 'session2')
        
        # torch.load should not be called again
        mock_torch_load.assert_not_called()
        # session2 should be added to active users
        assert 'session2' in models.torch_loaded_models['model1.pth']['active_users']
        assert len(models.torch_loaded_models['model1.pth']['active_users']) == 2


class TestInference:
    
    @patch('models.load_model')
    def test_inference_with_loaded_model(self, mock_load_model, reset_torch_loaded_models):
        """Test inference with an already loaded model."""
        mock_model = MagicMock()
        mock_model.evaluate.return_value = torch.tensor([1, 2, 3])
        
        models.torch_loaded_models = {
            'model1.pth': {
                'model': mock_model,
                'path': '/path/to/model1.pth',
                'active_users': {'session1'}
            }
        }
        
        input_data = torch.tensor([1, 2, 3])
        result = inference('model1.pth', input_data, 'session1')

        mock_load_model.assert_not_called()
        assert torch.equal(result, torch.tensor([1, 2, 3]))

    
    @patch('models.load_model')
    @patch('models.add_session_to_loaded_model')
    def test_inference_with_new_session(self, mock_add_session, mock_load_model, reset_torch_loaded_models):
        """Test inference when session is not in active users."""
        mock_model = MagicMock()
        mock_model.evaluate.return_value = torch.tensor([1, 2, 3])
        
        models.torch_loaded_models = {
            'model1.pth': {
                'model': mock_model,
                'path': '/path/to/model1.pth',
                'active_users': {'session1'}
            }
        }
        
        input_data = torch.tensor([1, 2, 3])
        result = inference('model1.pth', input_data, 'session2')
        
        mock_load_model.assert_not_called()
        mock_add_session.assert_called_once_with('model1.pth', 'session2')
        assert torch.equal(result, torch.tensor([1, 2, 3]))
    
    @patch('models.load_model')
    @patch('models.os.path.dirname')
    def test_inference_with_unloaded_model(self, mock_dirname, mock_load_model, reset_torch_loaded_models):
        """Test inference when model is not loaded."""
        mock_dirname.return_value = '/fake/path'
        mock_model = MagicMock()
        mock_model.evaluate.return_value = torch.tensor([1, 2, 3])
        
        # Simulate load_model behavior
        def side_effect(model_path, session_id):
            models.torch_loaded_models['model1.pth'] = {
                'model': mock_model,
                'path': model_path,
                'active_users': {session_id}
            }
        
        mock_load_model.side_effect = side_effect
        
        input_data = torch.tensor([1, 2, 3])
        result = inference('model1.pth', input_data, 'session1')
        
        mock_load_model.assert_called_once_with('/fake/path/models/model1.pth', 'session1')
        assert torch.equal(result, torch.tensor([1, 2, 3]))

class TestTorchDevice:
    
    @patch.dict(os.environ, {'TORCH_DEVICE': 'cpu'})
    def test_torch_device_from_env(self):
        """Test that TORCH_DEVICE uses environment variable."""
        # Need to reload the module to pick up the new environment variable
        import importlib
        importlib.reload(models)
        assert models.TORCH_DEVICE == 'cpu'
    
    @patch.dict(os.environ, {}, clear=True)
    @patch('models.torch.cuda.is_available', return_value=True)
    def test_torch_device_cuda_available(self, mock_cuda_available):
        """Test TORCH_DEVICE defaults to cuda when available."""
        import importlib
        importlib.reload(models)
        assert models.TORCH_DEVICE == 'cuda'
    
    @patch.dict(os.environ, {}, clear=True)
    @patch('models.torch.cuda.is_available', return_value=False)
    def test_torch_device_cuda_not_available(self, mock_cuda_available):
        """Test TORCH_DEVICE defaults to cpu when cuda not available."""
        import importlib
        importlib.reload(models)
        assert models.TORCH_DEVICE == 'cpu'


# Integration tests
class TestIntegration:

    # @patch('models.torch.load')
    # @patch('models.TorchModel.load_state_dict')
    # def test_full_workflow(self, reset_torch_loaded_models, mock_load_state_dict, mock_torch_load):
    #     """Test a complete workflow of loading, using, and cleaning up models."""
    #     mock_model = MagicMock()
    #     mock_model.eval.return_value = torch.tensor([1, 2, 3])
    #     mock_torch_load.return_value = mock_model
        
    #     # Load model for session1
    #     load_model('/path/to/model1.pth', 'session1')
    #     assert len(models.torch_loaded_models) == 1
        
    #     # Add session2 to same model
    #     load_model('/path/to/model1.pth', 'session2')
    #     assert len(models.torch_loaded_models['model1.pth']['active_users']) == 2
    #     # Perform inference
    #     input_data = torch.tensor([1, 2, 3])
    #     result = inference('model1.pth', input_data, 'session1')
    #     assert torch.equal(result, torch.tensor([1, 2, 3]))
        
    #     # Remove session1
    #     pop_session_from_loaded_models('session1')
    #     assert len(models.torch_loaded_models['model1.pth']['active_users']) == 1
    #     assert 'model1.pth' in models.torch_loaded_models
    #     # Remove session2 (should remove model)
    #     pop_session_from_loaded_models('session2')
    #     assert len(models.torch_loaded_models) == 0

    def test_real_workflow(self, reset_torch_loaded_models):
        """Test with a real model and inference."""

        load_model('models/unet_optimal (v5).pth', 'session1')
        assert 'unet_optimal (v5).pth' in models.torch_loaded_models

        # print("Loaded models:", models.torch_loaded_models['unet_optimal_(v5).pth']['model'])

        input_data = torch.rand(1, 3, 256, 256)  # Simulated input data
        result = inference('unet_optimal (v5).pth', input_data, 'session1')
        assert result is not None
        assert isinstance(result, torch.Tensor)
        assert result.shape == (1, 3, 256, 256)
        assert result.sum().round() == 256 * 256


# load_model('models/unet_optimal_(v5).pth', 'session1')
# model = models.torch_loaded_models['unet_optimal_(v5).pth']['model']
# input_data = torch.rand(1, 3, 20, 20)  # Simulated input data
# response = model(input_data)  # Set model to evaluation mode


if __name__ == "__main__":
    pytest.main([__file__])