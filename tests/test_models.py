import pytest
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)).split('tests')[0])
import tempfile
import torch
from unittest.mock import patch
import models
from models import discover_models, model_path, get_model, inference_on_numpy
import numpy as np


class FakeUnet(torch.nn.Module):
    """Predicts class 1 (asphalt) for every pixel."""
    def forward(self, x):
        logits = torch.zeros(x.shape[0], 3, x.shape[2], x.shape[3])
        logits[:, 1] = 5.0  # clearly below the 0.2 probability that turns a pixel into class 2
        return logits


@pytest.fixture
def empty_model_cache():
    """An empty model cache for each test; the original one is put back afterwards."""
    original = models.torch_loaded_models.copy()
    models.torch_loaded_models.clear()
    yield models.torch_loaded_models
    models.torch_loaded_models.clear()
    models.torch_loaded_models.update(original)


@pytest.fixture
def fake_models():
    """torch.load returns a new FakeUnet for any of the files model1.pth, model2.pth, model3.pth."""
    with patch('models.model_path', side_effect=lambda name: f'/fake/{name}'), \
         patch('models.torch.load', side_effect=lambda *args, **kwargs: FakeUnet()) as load:
        yield load


class TestDiscoverModels:

    @patch('models.os.path.dirname')
    @patch('models.glob.glob')
    def test_discover_models_returns_model_files(self, mock_glob, mock_dirname):
        """discover_models returns the file names, the latest model (by name) first."""
        mock_dirname.return_value = '/fake/path'
        mock_glob.return_value = [
            '/fake/path/models/model1.pth',
            '/fake/path/models/model2.pth'
        ]

        result = discover_models()

        assert result == ['model2.pth', 'model1.pth']
        mock_glob.assert_called_once_with(os.path.join('/fake/path', 'models', '*.pth'))

    def test_discover_models_empty_directory(self):
        """Test discover_models with empty models directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            empty_models_dir = os.path.join(temp_dir, 'models')
            os.makedirs(empty_models_dir)

            with patch('models.os.path.dirname', return_value=temp_dir):
                result = discover_models()
                assert result == []


class TestModelPath:

    def test_shipped_model_is_accepted(self):
        name = discover_models()[0]
        assert model_path(name).endswith(os.path.join('models', name))

    @pytest.mark.parametrize('name', ['../app.py', 'unknown.pth', os.path.join('..', 'models', 'x.pth'), ''])
    def test_other_names_are_refused(self, name):
        with pytest.raises(ValueError):
            model_path(name)


class TestModelCache:

    def test_model_is_loaded_once(self, empty_model_cache, fake_models):
        first = get_model('model1.pth')
        second = get_model('model1.pth')

        assert first is second
        assert fake_models.call_count == 1

    def test_least_recently_used_model_is_dropped(self, empty_model_cache, fake_models):
        with patch('models.MODEL_CACHE_SIZE', 2):
            get_model('model1.pth')
            get_model('model2.pth')
            get_model('model1.pth')  # model2 is now the least recently used
            get_model('model3.pth')

        assert list(empty_model_cache) == ['model1.pth', 'model3.pth']
        assert fake_models.call_count == 3

    def test_default_cache_keeps_one_model(self, empty_model_cache, fake_models):
        with patch('models.MODEL_CACHE_SIZE', 1):
            get_model('model1.pth')
            get_model('model2.pth')

        assert list(empty_model_cache) == ['model2.pth']

    def test_inference_uses_the_cache(self, empty_model_cache, fake_models):
        image = np.random.randint(0, 255, (48, 64, 3), dtype=np.uint8)

        for _ in range(3):
            asphalt_mask, aggregate_mask, background_mask = inference_on_numpy(image, 'model1.pth')

        assert fake_models.call_count == 1
        assert asphalt_mask.shape == image.shape[:2]
        assert asphalt_mask.all() and not aggregate_mask.any() and not background_mask.any()


class TestIntegration:

    def test_real_model(self, empty_model_cache):
        """The latest shipped model runs on a small image and stays loaded."""
        name = discover_models()[0]
        image = np.random.randint(0, 255, (300, 400, 3), dtype=np.uint8)

        masks = inference_on_numpy(image, name)

        assert all(mask.shape == image.shape[:2] for mask in masks)
        # every pixel belongs to exactly one class
        assert (masks[0].astype(int) + masks[1] + masks[2] == 1).all()
        assert name in empty_model_cache
