import pytest
import numpy as np
import os, sys
import PIL
import cv2
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ['SECRET_KEY_LENGTH'] = '32'
os.environ['DB_NAME'] = 'test_db'

from flask import Flask, session
from app import (
    app, ts, 
    UserTemporaryStorage,
    dict_to_json,
    get_masks_corrected,
    check_data_ownership, # decorator
    check_authentication, # decorator
    is_password_correct,
    generate_password_hash,
    sort_records,
    grayscale_image,
    temporary_store_image,
    downscale_image,
    polish_input_image_file,
)
import base64
from unittest.mock import MagicMock, patch
import requests

TEST_URL = 'http://localhost:5000'

@pytest.fixture
def user_storage():
    return UserTemporaryStorage()

def test_UserTemporaryStorage_initialization(user_storage):
    # ALL attributes should be initialized to None
    for attr in dir(user_storage):
        if not attr.startswith('__') and not callable(getattr(user_storage, attr)):
            assert getattr(user_storage, attr) is None, f"Attribute {attr} is not None"

def test_UserTemporaryStorage_initialization():
    user_storage = UserTemporaryStorage(user_id = 123, username='test_user')

    # ALL attributes should be initialized to None
    for attr in dir(user_storage):
        if not attr.startswith('__') and not callable(getattr(user_storage, attr)):
            if attr in ['user_id', 'username']:
                expected_value = 123 if attr == 'user_id' else 'test_user'
                assert getattr(user_storage, attr) == expected_value, f"Attribute {attr} is not correctly set"
            else:
                assert getattr(user_storage, attr) is None, f"Attribute {attr} is not None"

def test_UserTemporaryStorage_from_dict(user_storage):
    data = {
        'username': 'test_user',
        'img_width': 800,
        'img_height': 600,
        'aggregate_mask': np.array([[1, 1], [0, 0]]),
        'asphalt_mask': np.array([[0, 0], [1, 1]]),
        'aggregate_mask_manual_corrections': np.array([[0, 1], [1, 1]]),
        'asphalt_mask_manual_corrections': np.array([[1, 0], [0, 1]])
    }

    user_storage.from_dict(data)
    for key, value in data.items():
        if isinstance(value, np.ndarray):
            assert np.array_equal(getattr(user_storage, key), value), f"Attribute {key} does not match"
        else:
            assert getattr(user_storage, key) == value, f"Attribute {key} does not match"

    assert user_storage.user_id is None, "user_id should remain None"

def test_UserTemporaryStorage_partial_from_dict_invalid_input(user_storage):
    data = {
        'username': 'test_user',
        'img_width': 800,
        'invalid_key': 'should be ignored'
    }

    user_storage.from_dict(data)
    assert user_storage.username == 'test_user', "Attribute username does not match"
    assert user_storage.img_width == 800, "Attribute image_width does not match"
    assert user_storage.user_id is None, "user_id should remain None"
    assert not hasattr(user_storage, 'invalid_key'), "Attribute invalid_key should not exist"

def test_UserTemporaryStorage_to_dict(user_storage):
    user_storage.username = 'test_user'
    user_storage.img_width = 800
    user_storage.img_height = 600

    output_dict = user_storage.to_dict()
    assert output_dict['username'] == 'test_user', "Attribute username does not match"
    assert output_dict['img_width'] == 800, "Attribute img_width does not match"
    assert output_dict['img_height'] == 600, "Attribute img_height does not match"
    assert output_dict['user_id'] == None, "Attribute user_id does not match"

    # Test with specific features
    features = ['username', 'img_width']
    output_dict = user_storage.to_dict(features=features)
    assert output_dict['username'] == 'test_user', "Attribute username does not match"
    assert output_dict['img_width'] == 800, "Attribute img_width does not match"
    assert 'img_height' not in output_dict, "img_height should not be in the output dict"
    assert 'user_id' not in output_dict, "user_id should not be in the output dict"

def test_UserTemporaryStorage_to_dict_for_save(user_storage):
    """ With for_save=True, numpy arrays should be converted to bytes."""
    
    user_storage.aggregate_mask = np.array([[1, 1], [0, 0]])

    expected_aggregate_mask = user_storage.aggregate_mask.tobytes()

    output_dict = user_storage.to_dict(for_save=True)

    assert output_dict['aggregate_mask'] == expected_aggregate_mask, "Attribute aggregate_mask does not match"

def test_UserTemporaryStorage_to_json(user_storage):
    user_storage.username = 'test_user'
    user_storage.image_width = 800
    user_storage.image_height = 600
    user_storage.aggregate_mask = np.array([[1, 1], [0, 0]])

    with patch('app.to_base64', return_value='mocked_base64_string') as mock_to_base64:
        output_json = user_storage.to_json()

        assert isinstance(output_json, str), "Output is not a string"
        assert '"username": "test_user"' in output_json, "Attribute username does not match in JSON"
        assert '"image_width": 800' in output_json, "Attribute image_width does not match in JSON"
        assert '"image_height": 600' in output_json, "Attribute image_height does not match in JSON"
        assert '"user_id": null' in output_json, "Attribute user_id does not match in JSON"
        assert '"aggregate_mask": [[1, 1], [0, 0]]' not in output_json, "Attribute aggregate_mask is in raw form does not match in JSON"
        assert f'"aggregate_mask": "mocked_base64_string"' in output_json, "Attribute aggregate_mask does not match in JSON"

    # Test with specific features
    features = ['username', 'image_width']
    output_json = user_storage.to_json(features=features)
    assert '"username": "test_user"' in output_json, "Attribute username does not match in JSON"
    assert '"image_width": 800' in output_json, "Attribute image_width does not match in JSON"
    assert '"image_height"' not in output_json, "image_height should not be in the output JSON"
    assert '"user_id"' not in output_json, "user_id should not be in the output JSON"

def test_UserTemporaryStorage_get_asphalt_mask(user_storage):
    user_storage.asphalt_mask = np.array([[1, 0], [0, 1]])
    user_storage.asphalt_mask_manual_corrections = np.array([[-1, 0], [1, 1]])
    np.testing.assert_array_equal(user_storage.get_asphalt_mask(), np.array([[0, 0], [1, 1]], dtype=bool), "asphalt_mask does not match")

def test_UserTemporaryStorage_get_aggregate_mask(user_storage):
    user_storage.aggregate_mask = np.array([[1, 0], [0, 1]])
    user_storage.aggregate_mask_manual_corrections = np.array([[-1, 0], [1, 1]])
    np.testing.assert_array_equal(user_storage.get_aggregate_mask(), np.array([[0, 0], [1, 1]], dtype=bool), "aggregate_mask does not match")

def test_UserTemporaryStorage_get_bg_mask_realWF(user_storage):
    user_storage.get_aggregate_mask = MagicMock(return_value=np.array([[1, 0], [0, 1]], dtype=bool))
    user_storage.get_asphalt_mask = MagicMock(return_value=np.array([[0, 0], [1, 0]], dtype=bool))
    np.testing.assert_array_equal(user_storage.get_bg_mask(), np.array([[0, 1], [0, 0]], dtype=bool), "bg_mask does not match")

def test_UserTemporaryStorage_get_bg_mask_realWF(user_storage):
    user_storage.aggregate_mask = np.array([[1, 0], [0, 1]])
    user_storage.aggregate_mask_manual_corrections = np.array([[-1, 0], [0, 0]])
    user_storage.asphalt_mask = np.array([[0, 1], [1, 0]])
    user_storage.asphalt_mask_manual_corrections = np.array([[0, 0], [0, 0]])
    np.testing.assert_array_equal(user_storage.get_bg_mask(), np.array([[1, 0], [0, 0]], dtype=bool), "bg_mask does not match")

def test_UserTemporaryStorage_get_asphalt_ratio_invalid_masks(user_storage):
    """ Test when aggregate mask and asphalt mask have ovelaps. Should raise ValueError."""
    user_storage.get_aggregate_mask = MagicMock(return_value=np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]]))
    user_storage.get_asphalt_mask = MagicMock(return_value=np.array([[1, 0, 0], [0, 1, 0], [0, 0, 0]]))
    with pytest.raises(ValueError, match="Aggregate mask and asphalt mask have overlapping areas."):
        user_storage.get_asphalt_ratio()
        

def test_UserTemporaryStorage_get_asphalt_ratio(user_storage):
    user_storage.get_aggregate_mask = MagicMock(return_value=np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]]))
    user_storage.get_asphalt_mask = MagicMock(return_value=np.array([[0, 1, 0], [0, 0, 0], [1, 0, 0]]))
    result = user_storage.get_asphalt_ratio()
    assert result == 2/5, "asphalt ratio does not match"

def test_UserTemporaryStorage_get_asphalt_None_mask(user_storage):
    user_storage.get_aggregate_mask = MagicMock(return_value=np.array([[1, 0], [0, 1]]))
    user_storage.get_asphalt_mask = MagicMock(return_value=None)
    result = user_storage.get_asphalt_ratio()
    assert result == 0.0, "asphalt ratio does not match"

def test_UserTemporaryStorage_get_asphalt_0_bg_pixels(user_storage):
    user_storage.get_aggregate_mask = MagicMock(return_value=np.array([[0, 0], [0, 0]]))
    user_storage.get_asphalt_mask = MagicMock(return_value=np.array([[0, 0], [0, 0]]))
    result = user_storage.get_asphalt_ratio()
    assert result == 0.0, "asphalt ratio does not match"

def test_get_mask_corrected():
    mask = np.array([[1, 0], [0, 1]])
    manual_corrections = np.array([[-1, 0], [1, 1]])
    mask = get_masks_corrected(mask, manual_corrections)
    np.testing.assert_array_equal(mask, np.array([[0, 0], [1, 1]], dtype=bool), "get_mask_corrected does not match")

def test_get_mask_corrected_corrections_none():
    mask = np.array([[1, 0], [0, 1]])
    manual_corrections = None
    mask = get_masks_corrected(mask, manual_corrections)
    np.testing.assert_array_equal(mask, np.array([[1, 0], [0, 1]], dtype=bool), "get_mask_corrected does not match")

def test_get_mask_corrected_original_none():
    mask = None
    manual_corrections = np.array([[1, 0], [0, 1]])
    mask = get_masks_corrected(mask, manual_corrections)
    np.testing.assert_array_equal(mask, np.array([[1, 0], [0, 1]], dtype=bool), "get_mask_corrected does not match")

def test_get_mask_corrected_both_args_None():
    manual_corrections = None
    mask = None
    with pytest.raises(ValueError):
        mask = get_masks_corrected(mask, manual_corrections)
    
@app.route('/fake_view_auth/<int:id>', methods=['GET'])
@check_authentication
def fake_view_auth(id):
    return f"Access granted to the user"

@app.route('/fake_view_own/<int:id>', methods=['GET'])
@check_data_ownership
def fake_view_own(id):
    return f"Access granted to the user"

@app.route('/internal-server-error-trigger', methods=['GET'])
def internal_server_error_trigger():
    raise Exception("Intentional Exception for testing")

@pytest.fixture
def app(**kwargs):
    from app import app
    app.config['TESTING'] = True
    yield app

@pytest.fixture
def ts(monkeypatch):
    test_ts = {}
    monkeypatch.setattr("app.ts", test_ts)
    return test_ts

@pytest.fixture
def client(request, app, ts):
    authenticated = request.param if hasattr(request, 'param') else False
    app.config['TESTING'] = True
    with app.test_client() as client:
        if authenticated:
            with client.session_transaction() as session:
                session['user_id'] = "1"
                session['authenticated'] = True
                # Temporary Storage should be created
                # ts["1"] = UserTemsporaryStorage(user_id=1, username='test_user')
        yield client


# parametrized test for both authenticated and unauthenticated clients
# indirect= ... tro which fixture use indirect data passing
@pytest.mark.parametrize("client, expected_status",
                         [(True, 200), (False, 302)],
                        # true - ok, false - redirect to login 
                         indirect=["client"])
def test_load_experiment(client, expected_status):
    mock_response = {'experiment_id': 1, 'info': 'Test experiment'}

    with patch('db_api.load_experiment_from_db', return_value=mock_response):
        response = client.get('/load-experiment/1', base_url='https://localhost')
        assert response.status_code == expected_status

        if expected_status == 200:
            # Add more assertions as needed
            assert response.content_type == 'application/json'
            assert b'"experiment_id": 1' in response.data
            assert b'"info": "Test experiment"' in response.data

@pytest.mark.parametrize("client, expected_status",
                         [(True, 302), (False, 302)],
                        # true - ok, false - redirect to login 
                         indirect=["client"])
def test_http_redirect(client, expected_status):
    """Test checks wether the Talisman redirect an http request to https."""
    response = client.get('/load-experiment/1')
    assert response.status_code == expected_status  # Redirect to login

@pytest.mark.parametrize("client", [True], indirect=["client"])
def test_logout(client, ts):
    with client.session_transaction() as session:
        session['user_id'] = "1"
        session['username'] = "test_user"
        session['authenticated'] = True
        # ts[1] = UserTemporaryStorage(user_id=1, username='test_user')

    response = client.get('/logout', base_url='https://localhost')
    assert response.status_code == 302  # Redirect to login

    with client.session_transaction() as session:
        print(session)
        assert 'username' not in session
        assert 'authenticated' not in session
        # assert "1" not in ts  # Temporary storage should be removed

def test_dict_to_json_not_None_features():
    data = {
        'username': 'test_user',
        'image_width': 800,
        'image_height': 600,
        'random_feature': 'test_value',
    }

    json_str = dict_to_json(data, features=['username', 'image_width', 'image_height'])

    assert isinstance(json_str, str), "Output is not a string"
    assert '"username": "test_user"' in json_str, "Attribute username does not match in JSON"
    assert '"image_width": 800' in json_str, "Attribute image_width does not match in JSON"
    assert '"image_height": 600' in json_str, "Attribute image_height does not match in JSON"
    assert '"random_feature": "test_value"' not in json_str, "Attribute random_feature does not match in JSON"

def test_dict_to_json_None_features():
    data = {
        'username': 'test_user',
        'image_width': 800,
        'image_height': 600,
        'random_feature': 'test_value',
    }

    json_str = dict_to_json(data, features=None)

    assert isinstance(json_str, str), "Output is not a string"
    assert '"username": "test_user"' in json_str, "Attribute username does not match in JSON"
    assert '"image_width": 800' in json_str, "Attribute image_width does not match in JSON"
    assert '"image_height": 600' in json_str, "Attribute image_height does not match in JSON"
    assert '"random_feature": "test_value"' in json_str, "Attribute random_feature is missing in JSON"

def test_dict_to_json_with_array():
    data = {
        'array': np.array([[1, 0], [0, 1]]),
        'image_width': 800,
    }

    with patch('app.to_base64', return_value='mocked_base64_string') as mock_to_base64:
        array_base64 = base64.b64encode(data['array'].tobytes()).decode('utf-8')
        json_str = dict_to_json(data, features=None)

        assert isinstance(json_str, str), "Output is not a string"
        assert '"image_width": 800' in json_str, "Attribute image_width does not match in JSON"
        assert f'"array": "mocked_base64_string"' in json_str, "Attribute array does not match in JSON"

@pytest.mark.parametrize("client", [True], indirect=["client"])
def test_check_data_ownership_decorator_allows_access(app, client):

    with patch('db_api.get_user_id_of_experiment', return_value='1') as mock_query, \
        patch('flask.flash') as mock_flash, \
        patch('flask.redirect', return_value='redirected') as mock_redirect:
                
        # Perform a real test request (creates its own context)
        response = client.get('/fake_view_own/123', base_url='https://localhost')
        # response = client.get('/fake_view/123', )
        # Assertions
        assert response.status_code == 200
        mock_query.assert_called_once_with(id=123)
        mock_flash.assert_not_called()
        mock_redirect.assert_not_called()
        assert b"Access granted to the user" in response.data

@pytest.mark.parametrize("client", [True], indirect=["client"])
def test_check_data_ownership_decorator_denies_access(app, client):

    with patch('db_api.get_user_id_of_experiment', return_value='2') as mock_query, \
        patch('app.flash') as mock_flash, \
        patch('app.redirect', return_value='redirected') as mock_redirect:

        result = client.get('/fake_view_own/123', base_url='https://localhost')
        # Assertions
        assert result.status_code == 302
        mock_flash.assert_called_once_with("You do not have permission to access this data.", "error")
        mock_redirect.assert_called_once_with('/')
        assert result.data == b'redirected'

@pytest.mark.parametrize("client", [False], indirect=["client"])
def test_check_authentication_decorator_denies_access(app, client):

    with patch('app.flash') as mock_flash, \
        patch('app.redirect', return_value='redirected') as mock_redirect:

        result = client.get('/fake_view_auth/123', base_url='https://localhost')
        # Assertions
        assert result.status_code == 302
        mock_flash.assert_called_once_with("You must be logged in to access this page.", "error")
        mock_redirect.assert_called_once_with('/login')
        assert result.data == b'redirected'

@pytest.mark.parametrize("client", [True], indirect=["client"])
def test_check_authentication_decorator_allows_access(app, client):

    with patch('app.flash') as mock_flash, \
        patch('app.redirect', return_value='redirected') as mock_redirect:

        result = client.get('/fake_view_auth/123', base_url='https://localhost')
        # Assertions
        assert result.status_code == 200
        mock_flash.assert_not_called()
        mock_redirect.assert_not_called()
        assert b"Access granted to the user" in result.data

@pytest.mark.parametrize("client", [True], indirect=["client"])
def test_index(client):

    with patch('app.discover_models', return_value='model_1') as mock, \
         patch('app.render_template', return_value='rendered') as mock_render:
        response = client.get('/', base_url='https://localhost')
        
        assert response.status_code == 200
        mock.assert_called_once()
        mock_render.assert_called_once()

@pytest.mark.parametrize("client", [True], indirect=["client"])
def test_home(client):
    with patch('app.render_template', return_value='rendered_home') as mock_render:
        response = client.get('/home', base_url='https://localhost')
        assert response.status_code == 200
        mock_render.assert_called_once=()
        assert b'rendered_home' in response.data

@pytest.mark.parametrize("client", [True, False], indirect=["client"])
def test_page_not_found_handler(client):
    with patch('app.render_template', return_value='page_not_found') as mock_render:
        result = client.get(f'/non_existent_page', base_url='https://localhost')
        assert result.status_code == 404
        mock_render.assert_called_once()

@pytest.mark.parametrize("app", [{'PROPAGATE_EXCEPTIONS': False}], indirect=["app"])
def test_internal_server_error_handler(app, client):

    # with Exception("Intentional Exception for testing"):
    with patch('app.flash') as mock_flash, \
         patch('app.redirect', return_value='redirected') as mock_redirect:
        #     assert response.status_code == 500
        # with pytest.raises(Exception):
        response = client.get('/internal-server-error-trigger', base_url='https://localhost', follow_redirects=True)
        assert response.status_code == 500
        mock_flash.assert_called_once_with("An internal server error has occured.", "error")
        mock_redirect.assert_called_once_with('/logout')


# -----
#  TESTS for editing personal information, changing email and password
# -----

@pytest.mark.parametrize("client", [False], indirect=["client"])
def test_edit_personal_information_success_unauthenticated_client(client):
    """
    Test editing personal information with unauthenticated client.
    Should redirect to login.
    """
    response = client.post('/edit-personal-information', base_url='https://localhost')
    assert response.status_code == 302
    assert response.headers['Location'] == '/login'

    response = client.get('/edit-personal-information', base_url='https://localhost')
    assert response.status_code == 302
    assert response.headers['Location'] == '/login'

@pytest.mark.parametrize("client", [True], indirect=["client"])
def test_edit_personal_information_get(client):
    """
    Test getting personal information with authenticated client.
    Should succeed.
    """
    with patch('forms.EditPersonalInformationForm') as mock_form:
        response = client.get('/edit-personal-information', base_url='https://localhost')
        assert response.status_code == 200
        mock_form.assert_called_once()

@pytest.mark.parametrize("client, form_validated", [(True, True), (True, False)], indirect=["client"])
def test_edit_personal_information_post(client, form_validated):
    """
    Test editing personal information with authenticated client.
    Should succeed.
    """

    # Create fake fields
    fake_field_1 = MagicMock(name='username', data='new_user')
    fake_field_1.name = 'username'
    fake_field_1.data = 'new_user'
    fake_field_2 = MagicMock(name='email', data='user@example.com')
    fake_field_2.name = 'email'
    fake_field_2.data = 'user@example.com'
    fake_csrf = MagicMock(name='csrf_token', data='token')
    fake_csrf.name = 'csrf_token'
    fake_csrf.data = 'token'

    with patch('forms.EditPersonalInformationForm') as mock_form_class, \
        patch('app.flash') as mock_flash, patch('db_api.update_users_table') as mock_update:
        
        mock_form_instance = MagicMock()
        mock_form_instance.validate_on_submit.return_value = form_validated
        mock_form_instance.__iter__.return_value = iter([fake_field_1, fake_field_2, fake_csrf])

        mock_form_class.return_value = mock_form_instance

        response = client.post('/edit-personal-information', base_url='https://localhost')

        if not form_validated:
            assert response.status_code == 200
            mock_form_instance.validate_on_submit.assert_called_once()
            mock_flash.assert_not_called()
            mock_update.assert_not_called()
        else:
            assert response.status_code == 302
            assert response.headers['Location'] == '/user'
            mock_flash.assert_called_once_with("Personal information updated successfully.", "success")
            mock_form_instance.validate_on_submit.assert_called_once()
            assert mock_update.call_count == 2


@pytest.mark.parametrize("client", [False], indirect=["client"])
def test_change_email_unauthenticated_client(client):
    """
    Test changing email with unauthenticated client.
    Should redirect to login.
    """
    response = client.post('/change-email', base_url='https://localhost')
    assert response.status_code == 302
    assert response.headers['Location'] == '/login'

    response = client.get('/change-email', base_url='https://localhost')
    assert response.status_code == 302
    assert response.headers['Location'] == '/login'

@pytest.mark.parametrize("client", [True], indirect=["client"])
def test_change_email_get(client):
    """
    Test getting change email form with authenticated client.
    Should succeed.
    """
    with patch('forms.ChangeEmailForm') as mock_form:
        mock_form.return_value = MagicMock()
        response = client.get('/change-email', base_url='https://localhost')
        assert response.status_code == 200
        mock_form.assert_called_once()

@pytest.mark.parametrize("client, form_validated", [(True, True), (True, False)], indirect=["client"])
def test_change_email_post(client, form_validated):
    """
    Test changing email with authenticated client.
    Should succeed.
    """

    # Create fake fields
    fake_csrf = MagicMock(name='csrf_token', data='token')
    fake_csrf.name = 'csrf_token'
    fake_csrf.data = 'token'

    with patch('forms.ChangeEmailForm') as mock_form_class, \
        patch('app.flash') as mock_flash, \
        patch('db_api.update_users_table') as mock_update:

        mock_form_instance = MagicMock()
        mock_form_instance.validate_on_submit.return_value = form_validated
        mock_form_instance.e_mail = MagicMock(name='e_mail')
        mock_form_instance.e_mail.data = 'new_email@example.com'     
    
        mock_form_class.return_value = mock_form_instance

        response = client.post('/change-email', base_url='https://localhost')
        
        if not form_validated:
            assert response.status_code == 200
            mock_form_instance.validate_on_submit.assert_called_once()
            mock_flash.assert_not_called()
            mock_update.assert_not_called()
        else:
            assert response.status_code == 302
            assert response.headers['Location'] == '/user'
            mock_form_instance.validate_on_submit.assert_called_once()
            mock_flash.assert_called_once_with('Email changed successfully.','success')
            mock_update.assert_called_once_with(values_dict={'e_mail': mock_form_instance.e_mail.data}, user_id='1')

def test_change_password_unauthenticated_client(client):
    """
    Test changing password with unauthenticated client.
    Should redirect to login.
    """
    response = client.post('/change-password', base_url='https://localhost')
    assert response.status_code == 302
    assert response.headers['Location'] == '/login'

    response = client.get('/change-password', base_url='https://localhost')
    assert response.status_code == 302
    assert response.headers['Location'] == '/login'

@pytest.mark.parametrize("client", [True], indirect=["client"])
def test_change_password_get(client):
    """
    Test getting change password form with authenticated client.
    Should succeed.
    """
    with patch('forms.ChangePasswordForm') as mock_form:
        mock_form.return_value = MagicMock()
        response = client.get('/change-password', base_url='https://localhost')
        assert response.status_code == 200
        mock_form.assert_called_once()

@pytest.mark.parametrize("client, pwd_correct, form_validated", [(True, True, True), (True, True, False), (True, False, True)], indirect=["client"])
def test_change_password_post(client, pwd_correct, form_validated):
    """
    Test changing password with authenticated client.
    Should succeed.
    """
    # Create fake fields
    new_password = MagicMock(name='new_password', data='NewPass123')
    new_password.name = 'new_password'
    new_password.data = 'NewPass123'

    old_password = MagicMock(name='old_password', data='OldPass123')
    old_password.name = 'old_password'
    old_password.data = 'OldPass123'

    with patch('forms.ChangePasswordForm') as mock_form_class, \
        patch('app.flash') as mock_flash, \
        patch('app.is_password_correct', return_value=pwd_correct) as mock_check_password, \
        patch('db_api.update_users_table', return_value=None) as mock_update_password, \
        patch('app.generate_password_hash', return_value=f"hashed_{new_password.data}") as mock_genpwdhash:

        mock_form_instance = MagicMock()
        mock_form_instance.validate_on_submit.return_value = form_validated
        mock_form_instance.new_password = new_password
        mock_form_instance.old_password = old_password

        mock_form_class.return_value = mock_form_instance
        response = client.post('/change-password', base_url='https://localhost')

        # assertations
        if not form_validated:
            assert response.status_code == 200
            mock_form_instance.validate_on_submit.assert_called_once()
            mock_check_password.assert_not_called()
            mock_genpwdhash.assert_not_called()
            mock_update_password.assert_not_called()
            mock_flash.assert_not_called()
        else:
            if pwd_correct:
                assert response.status_code == 302
                assert response.headers['Location'] == '/user'
                mock_flash.assert_called_once_with("Password changed successfully.", "success")
                mock_check_password.assert_called_once_with(password=mock_form_instance.old_password.data, user_id='1')
                mock_genpwdhash.assert_called_once_with(mock_form_instance.new_password.data)
                mock_update_password.assert_called_once_with(values_dict={'pwd': f"hashed_{new_password.data}"}, user_id='1')
            else:
                assert response.status_code == 200
                mock_flash.assert_called_once_with("The old password is incorrect.", "error")
                mock_check_password.assert_called_once_with(password=mock_form_instance.old_password.data, user_id='1')
                mock_genpwdhash.assert_not_called()


# ------
#  UTILITIES TESTS
# ------


def test_is_password_correct():
    test_user_id = 1
    correct_password = 'CorrectPass123'
    incorrect_password = 'WrongPass123'

    with patch('db_api.get_password_hash', return_value='hashed_CorrectPass123') as mock_get_hash, \
         patch('werkzeug.security.check_password_hash', side_effect=lambda pwhash, password: pwhash == f'hashed_{password}') as mock_check_hash:
        
        # Test with correct password
        assert is_password_correct(password=correct_password, user_id=test_user_id) == True
        mock_get_hash.assert_called_with(user_id=test_user_id)

        # Test with incorrect password
        assert is_password_correct(password=incorrect_password, user_id=test_user_id) == False
        assert mock_get_hash.call_count == 2  # Called again for the second test

@pytest.mark.parametrize("client ", [True, False], indirect=["client"])
def test_login_get(client):
    with patch('app.logout') as mock_logout, \
         patch('app.render_template', return_value='login_page') as mock_render, \
         patch('forms.LoginForm') as mock_form_class:
        response = client.get('/login', base_url='https://localhost')
        assert response.status_code == 200
        assert b'login_page' in response.data  # Assuming the login page contains the word 'Login'
        mock_logout.assert_called_once()  # Ensure logout is called to clear any session
        mock_render.assert_called_once()

@pytest.mark.parametrize("client, form_validated, password_correct", [(True, True, True), (True, True, False), (True, False, False)], indirect=["client"])
def test_login_post(client, form_validated, password_correct):
    
    # Create fake fields
    usernameXe_mail = MagicMock(name='username', data='test_user')
    usernameXe_mail.name = 'username'
    usernameXe_mail.data = 'test_user'
    password = MagicMock(name='password', data='TestPass123')
    password.name = 'password'
    password.data = 'TestPass123'

    with patch('forms.LoginForm') as mock_form_class, \
        patch('app.is_password_correct', return_value=password_correct) as mock_check_password, \
        patch('db_api.get_user_id', return_value='1') as mock_get_user_id, \
        patch('app.flash') as mock_flash, \
        patch('app.logout') as mock_logout, \
        patch('app.redirect', return_value='redirected') as mock_redirect:
        
        mock_form_instance = MagicMock()
        mock_form_instance.validate_on_submit.return_value = form_validated
        mock_form_instance.usernameXe_mail = usernameXe_mail
        mock_form_instance.password = password 
        mock_form_class.return_value = mock_form_instance

        response = client.post('/login', base_url='https://localhost')
        if form_validated:
            # Form did validate
            if password_correct:
                # Correct credentials
                assert response.status_code == 302
                mock_redirect.assert_called_once_with('/')
            else:
                # Incorrect credentials
                assert response.status_code == 200
                mock_flash.assert_called_once_with("Invalid username or password.", "error")
            mock_get_user_id.assert_called_once_with(username='test_user', email='test_user')
            mock_check_password.assert_called_once_with(password='TestPass123', user_id='1')
        if not form_validated:
            mock_logout.assert_called_once()  # Ensure logout is called to clear any session
            assert response.status_code == 200
            mock_form_instance.validate_on_submit.assert_called_once()
            mock_get_user_id.assert_not_called()
            mock_check_password.assert_not_called()
            mock_flash.assert_not_called()
            mock_redirect.assert_not_called()

def test_generate_password_hash():
    password = 'TestPass123'

    with patch('werkzeug.security.generate_password_hash', return_value='hashed_TestPass123') as mock_gen_hash,\
         patch('os.environ', new_callable=dict) as mock_environ:

        mock_environ.update(SECRET_KEY_LENGTH='32')
        mock_environ.update(HASH_METHOD='hash_method')
        mock_environ.update(SALT_LENGTH=36)

        hashed = generate_password_hash(password)
        assert hashed == 'hashed_TestPass123'
        mock_gen_hash.assert_called_once_with(password, method='hash_method', salt_length=36)


def test_sort_records():
    records = [
        {'id': 3, 'value': 'B'},
        {'id': 2, 'value': 'A'},
        {'id': 1, 'value': 'C'},
    ]
    sorted_records = sort_records(records, sort_order='asc', sort_by='id', page_limit=2)

    expected = [
        {'id': 1, 'value': 'C'},
        {'id': 2, 'value': 'A'},
    ]

    assert sorted_records == expected, "Records not sorted correctly in ascending order"

    sorted_records = sort_records(records, sort_order='asc', sort_by='value', page_limit=4)
    expected = [
        {'id': 2, 'value': 'A'},
        {'id': 3, 'value': 'B'},
        {'id': 1, 'value': 'C'},
    ]
    assert sorted_records == expected, "Records not sorted correctly in ascending order by value"

    sorted_records = sort_records(records, sort_order='desc', sort_by='id', page_limit=2)
    expected = [
        {'id': 3, 'value': 'B'},
        {'id': 2, 'value': 'A'},
    ]
    assert sorted_records == expected, "Records not sorted correctly in descending order"

@pytest.mark.parametrize("client", [False], indirect=["client"])
def test_user_unathenticated(client):
    "Expect redirect to login page"
    response = client.get('/user', base_url='https://localhost')
    assert response.status_code == 302
    assert response.headers['Location'] == '/login'

@pytest.mark.parametrize("client", [True], indirect=["client"])
def test_user(client):
    with patch('db_api.get_user_info_by_id', return_value={'username': 'test_user', 'e_mail': 'test_user@example.com'}) as mock_get_user_info, \
         patch('app.render_template') as mock_render_template:
        
        response = client.get('/user', base_url='https://localhost')

        assert response.status_code == 200
        mock_get_user_info.assert_called_once_with(user_id='1')
        mock_render_template.assert_called_once()

def test_grayscale_image():
    # Create a sample RGB image (3x3 pixels)
    rgb_image = np.array([[[255, 0, 0], [0, 255, 0], [0, 0, 255]],
                          [[255, 255, 0], [0, 255, 255], [255, 0, 255]],
                          [[192, 192, 192], [128, 128, 128], [64, 64, 64]]], dtype=np.uint8)
    # save image for visual inspection if needed
    img = PIL.Image.fromarray(rgb_image)
    img.save("test_rgb_image.png")

    expected_gray_image = np.array([[76, 150, 29],
                                    [226, 179, 105],
                                    [192, 128, 64]], dtype=np.uint8)
    # save image for visual inspection if needed
    img = PIL.Image.fromarray(expected_gray_image)
    img.save("test_expected_gray_image.png")

    gray_image = grayscale_image(rgb_image)
    img = PIL.Image.fromarray(gray_image)
    img.save("test_gray_image.png")
    np.testing.assert_array_equal(gray_image, expected_gray_image, "Grayscale conversion did not match expected output")

    # Test with already grayscale image
    gray_input = np.array([[100, 150], [200, 250]], dtype=np.uint8)
    gray_output = grayscale_image(gray_input)
    np.testing.assert_array_equal(gray_output, gray_input, "Grayscale function altered an already grayscale image")

    # Test with 4 channels (RGBA)
    rgba_image = np.array([[[255, 0, 0, 255], [0, 255, 0, 255]],
                           [[0, 0, 255, 255], [255, 255, 0, 255]]], dtype=np.uint8)
    img = PIL.Image.fromarray(rgba_image)   
    img.save("test_rgba_image.png")

    expected_gray_rgba = np.array([[76, 150],
                                   [29, 226]], dtype=np.uint8)
    gray_rgba_output = grayscale_image(rgba_image)
    np.testing.assert_array_equal(gray_rgba_output, expected_gray_rgba, "Grayscale conversion for RGBA did not match expected output")
    img = PIL.Image.fromarray(gray_rgba_output)
    img.save("test_gray_rgba_image.png")

    # test with invalid input
    with pytest.raises(ValueError, match="nvalid image shape for grayscaling."):
        invalid_image = (np.random.rand(5, 5, 2) * 255).astype(np.uint8)  # 5 channels
        grayscale_image(invalid_image)

    # test with invalid input
    with pytest.raises(ValueError, match="nvalid image shape for grayscaling."):
        invalid_image = (np.random.rand(5, 5, 1) * 255).astype(np.uint8)  # 5 channels
        grayscale_image(invalid_image)

@pytest.mark.parametrize("client", [True], indirect=["client"])
def test_get_grayscale_image_image_present(client, ts):
    ts['1'] = UserTemporaryStorage(user_id=1, username='test_user')
    ts['1'].color = np.array([[0, 0, 0], [255, 255, 255]], dtype=np.uint8)

    with patch('app.grayscale_image', return_value='grayscaled_image') as mock_grayscale, \
        patch('app.to_base64', return_value='b64g') as mock_to_base64:
        response = client.get('/get-grayscale-image', base_url='https://localhost')
        assert response.status_code == 200
        mock_grayscale.assert_called_once_with(ts['1'].color)
        mock_to_base64.assert_called_once_with('grayscaled_image')

@pytest.mark.parametrize("client", [True], indirect=["client"])
def test_get_grayscale_image_no_color(client, ts):
    ts['1'] = UserTemporaryStorage(user_id=1, username='test_user')
    ts['1'].color = None

    with patch('app.grayscale_image', return_value='grayscaled_image') as mock_grayscale, \
        patch('app.to_base64', return_value='b64g') as mock_to_base64:
        response = client.get('/get-grayscale-image', base_url='https://localhost')
        
        assert response.status_code == 404
        mock_grayscale.assert_not_called()
        mock_to_base64.assert_not_called()


@pytest.mark.parametrize("client", [False, True], indirect=["client"])
def test_register_user_get(client):

    with patch('forms.RegistrationFormUser') as mock_form_class, \
         patch('app.render_template', return_value='registration_page') as mock_render, \
         patch('app.logout', return_value=None) as mock_logout:
        
        response = client.get('/register', base_url='https://localhost')

        assert response.status_code == 200
        assert mock_form_class.call_count == 1
        assert mock_logout.call_count == 1
        assert mock_render.call_count == 1

@pytest.mark.parametrize("client, form_validated, user_saved", [(False, True, None), (False, True, 'str'), (False, False,'str')], indirect=["client"])
def test_register_user_post(client, form_validated, user_saved):
    """
    user_saved: if successful, then None, else ValueError
    """

    # Create fake fields
    username = MagicMock(name='username', data='new_user')
    username.name = 'username'
    username.data = 'new_user'
    e_mail = MagicMock(name='e_mail', data='new_user@example.com')
    e_mail.name = 'e_mail'
    e_mail.data = 'new_user@example.com'
    first_name = MagicMock(name='first_name', data='New')   
    first_name.name = 'first_name'
    first_name.data = 'New'
    last_name = MagicMock(name='last_name', data='User')
    last_name.name = 'last_name'
    last_name.data = 'User'
    password = MagicMock(name='password', data='NewPass123')
    password.name = 'password'
    password.data = 'NewPass123'
    confirm_password = MagicMock(name='confirm_password', data='NewPass123')
    confirm_password.name = 'confirm_password'
    confirm_password.data = 'NewPass123'
    csrf_token = MagicMock(name='csrf_token', data='token')
    csrf_token.name = 'csrf_token'
    csrf_token.data = 'token'
    


    with patch('forms.RegistrationFormUser') as mock_form_class,\
         patch('app.render_template', return_value='registration_page') as mock_render,\
         patch('db_api.save_new_user_db', return_value=user_saved) as mock_save,\
         patch('db_api.get_company_id_by_key', return_value=1) as mock_get_company_id,\
         patch('app.generate_password_hash', return_value='hashed_NewPass123') as mock_generate_password_hash,\
         patch('app.flash') as mock_flash, \
         patch('app.logout', return_value=None) as mock_logout:

        mock_form_instance = MagicMock()
        mock_form_instance.validate_on_submit.return_value = form_validated
        mock_form_instance.username = username
        mock_form_instance.e_mail = e_mail
        mock_form_instance.first_name = first_name
        mock_form_instance.last_name = last_name
        mock_form_instance.password = password
        mock_form_instance.confirm_password = confirm_password
        mock_form_instance.csrf_token = csrf_token

        mock_form_class.return_value = mock_form_instance
        datadict = {
            'username': 'new_user',
            'e_mail': 'new_user@example.com',
            'first_name': 'New',
            'last_name': 'User',
            'company': 1,
            'pwd': 'hashed_NewPass123',
        }
        response = client.post('/register', base_url='https://localhost')

        if form_validated:
            mock_get_company_id.assert_called_once()
            mock_save.assert_called_once_with(values=datadict)
            mock_generate_password_hash.assert_called_once_with('NewPass123')
            if user_saved is None:
                # User successfully saved
                assert response.status_code == 302
                assert response.headers['Location'] == '/login'
                mock_flash.assert_called_once_with(message = "Registration successful. Please log in.", category = "success")
            else:
                # User not saved due to ValueError
                assert response.status_code == 500
                assert mock_form_class.call_count == 1
                assert mock_logout.call_count == 1
                mock_flash.assert_called_once()
                mock_render.assert_called_once()
        else:
            assert response.status_code == 200
            assert mock_form_class.call_count == 1
            assert mock_logout.call_count == 1
            assert mock_render.call_count == 1
            mock_save.assert_not_called()
            mock_flash.assert_not_called()

def test_downscale_image():
    # Create a sample image (4x4 pixels, RGB)
    sample_image = np.array([[[255, 0, 0], [0, 255, 0], [0, 0, 255], [255, 255, 0]],
                             [[0, 255, 255], [255, 0, 255], [192, 192, 192], [128, 128, 128]],
                             [[64, 64, 64], [32, 32, 32], [16, 16, 16], [8, 8, 8]],
                             [[4, 4, 4], [2, 2, 2], [1, 1, 1], [0, 0, 0]]], dtype=np.uint8)


    # Test that the scale factor must be positive
    with pytest.raises(ValueError, match="Scale factor must be greater than 0."):
        downscale_image(sample_image, scale_factor=0)
    with pytest.raises(ValueError, match="Scale factor must be greater than 0."):
        downscale_image(sample_image, scale_factor=-1.2)

    scale_factor = 2
    # Expected downscaled image (2x2 pixels)
    expected_downscaled = cv2.resize(sample_image, (sample_image.shape[1] // scale_factor, sample_image.shape[0] // scale_factor),
                                      interpolation=cv2.INTER_AREA)
    
    downscaled_image = downscale_image(sample_image, scale_factor=scale_factor)
    assert downscaled_image.shape == (2, 2, 3), "Downscaled image has incorrect shape"
    assert downscaled_image.dtype == np.uint8, "Downscaled image has incorrect dtype"
    np.testing.assert_array_equal(downscaled_image, expected_downscaled, "Downscaled image content does not match expected output")

    # Test with grayscale image
    gray_image = np.array([[100, 150], [200, 250]], dtype=np.uint8)
    downscaled_gray = downscale_image(gray_image, scale_factor=2)
    assert downscaled_gray.shape == (1, 1), "Downscaled grayscale image has incorrect shape"
    assert downscaled_gray.dtype == np.uint8, "Downscaled grayscale image has incorrect dtype"
    np.testing.assert_array_equal(downscaled_gray, np.array([[175]], dtype=np.uint8), "Downscaled grayscale image content does not match expected output")

    # test that when no scale factor is provided, it computes the correct one such that the maximum dimension is 1200
    large_image = np.random.randint(0, 256, size=(3000, 1500, 3), dtype=np.uint8)
    downscaled_large = downscale_image(large_image)
    assert downscaled_large.shape[0] <= 1200, "Downscaled large image exceeds maximum dimension of 1200"
    assert downscaled_large.shape[1] == 600, "The second dimension should be scaled proportionally"

    large_image = np.random.randint(0, 256, size=(1100, 980, 3), dtype=np.uint8)
    downscaled_large = downscale_image(large_image)
    assert downscaled_large.shape[0] == 1100, "The image should not be downscaled if within limits"
    assert downscaled_large.shape[1] == 980, "The image should not be downscaled if within limits"

@pytest.mark.parametrize("client", [False], indirect=["client"])
def test_get_current_experiment_unathenticated_client(client):
    """Expect redirect to login page"""
    response = client.get('/get-current-experiment', base_url='https://localhost')
    assert response.status_code == 302
    assert response.headers['Location'] == '/login'

@pytest.mark.parametrize("client", [True], indirect=["client"])
def test_get_current_experiment_present(client, ts):
    ts['1'] = UserTemporaryStorage(user_id=1, username='test_user')
    ts['1'].experiment_id = 123
    ts['1'].to_dict = MagicMock(return_value={'experiment_id': 123, 'other_data': 'value'})

    with patch('app.dict_to_json', return_value='json_response') as mock_dict_to_json:
        response = client.get('/get-current-experiment', base_url='https://localhost')
        assert response.status_code == 200
        mock_dict_to_json.assert_called_once_with({'status': 'success', 'experiment_id': 123, 'other_data': 'value'})

@pytest.mark.parametrize("client", [True], indirect=["client"])
def test_get_current_experiment_no_current_experiment(client, ts):
    """"Expect 404 if no current experiment is set."""
    ts['1'] = UserTemporaryStorage(user_id=1, username='test_user')
    ts['1'].experiment_id = None
    ts['1'].to_dict = MagicMock(return_value={'experiment_id': None, 'other_data': 'value'})

    with patch('app.dict_to_json', return_value='json_response') as mock_dict_to_json:
        response = client.get('/get-current-experiment', base_url='https://localhost')
        assert response.status_code == 404
        mock_dict_to_json.assert_not_called()

def test_polish_input_image_file():
    # Create a sample RGB image (3x3 pixels)
    raise NotImplementedError("Fix the test.")
    
    rgb_image = np.array([[[255, 0, 0], [0, 255, 0], [0, 0, 255]],
                          [[255, 255, 0], [0, 255, 255], [255, 0, 255]],
                          [[192, 192, 192], [128, 128, 128], [64, 64, 64]]], dtype=np.uint8)
    
    img = PIL.Image.fromarray(rgb_image)
    img.save("test_input_image.png")

    polished_image = polish_input_image_file(rgb_image)
    assert polished_image.shape == (3, 3), "Polished image has incorrect shape"
    assert polished_image.dtype == np.uint8, "Polished image has incorrect dtype"
    np.testing.assert_array_equal(polished_image, rgb_image, "Polished image content altered unexpectedly")

    # Test with grayscale image
    gray_image = np.array([[100, 150], [200, 250]], dtype=np.uint8)
    polished_gray = polish_input_image_file(gray_image)
    assert polished_gray.shape == (2, 2), "Polished grayscale image has incorrect shape"
    assert polished_gray.dtype == np.uint8, "Polished grayscale image has incorrect dtype"
    np.testing.assert_array_equal(polished_gray, gray_image, "Polished grayscale image content altered unexpectedly")

    # Test with invalid input (1D array)
    invalid_image = (np.random.rand(10) * 255).astype(np.uint8)  # 1D array
    with pytest.raises(ValueError, match="Input image must be a 2D or 3D numpy array."):
        polish_input_image_file(invalid_image)

    # Test with invalid input (4D array)
    invalid_image_4d = (np.random.rand(5, 5, 5, 5) * 255).astype(np.uint8)  # 4D array
    with pytest.raises(ValueError, match="Input image must be a 2D or 3D numpy array."):
        polish_input_image_file(invalid_image_4d)

# @pytest.mark.parametrize("client", [True], indirect=["client"])
# def test_temporary_store_image(client, ts):
#     user_storage = UserTemporaryStorage(user_id=1, username='test_user')
#     ts['1'] = user_storage

#     # Create a sample image (2x2 pixels, RGB)
#     sample_image = np.array([[[255, 0, 0], [0, 255, 0]],
#                              [[0, 0, 255], [255, 255, 0]]], dtype=np.uint8)
    
#     # Store the image
#     temporary_store_image(sample_image)

    
    
#     np.testing.assert_array_equal(user_storage.color, sample_image, "Image not stored correctly in temporary storage")