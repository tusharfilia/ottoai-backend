import pytest
from unittest.mock import MagicMock
from app.routes.company import *
from app.models import user
from sqlalchemy.orm import Session

@pytest.fixture
def mock_db_session():
    """Fixture to mock the database session."""
    session = MagicMock(spec=Session)
    return session

@pytest.fixture
def mock_user():
    """Fixture to mock a user."""
    return user.User(
        id=1,
        username="test_user",
        email="test_user@example.com",
        is_active=True
    )

def test_authenticate_user_success(mock_db_session, mock_user):
    """Test the authenticate_user function for successful authentication."""
    mock_db_session.query.return_value.filter_by.return_value.first.return_value = mock_user
    credentials = {"username": "test_user", "password": "correct_password"}

    response = authenticate_user(credentials, db=mock_db_session)

    assert response["status"] == "success"
    assert response["user_id"] == mock_user.id
    mock_db_session.query.assert_called_once()

def test_authenticate_user_invalid_credentials(mock_db_session):
    """Test the authenticate_user function with invalid credentials."""
    mock_db_session.query.return_value.filter_by.return_value.first.return_value = None
    credentials = {"username": "test_user", "password": "wrong_password"}

    with pytest.raises(Exception) as excinfo:
        authenticate_user(credentials, db=mock_db_session)

    assert "Invalid credentials" in str(excinfo.value)

def test_get_user_details_success(mock_db_session, mock_user):
    """Test the get_user_details function for successful retrieval."""
    mock_db_session.query.return_value.filter_by.return_value.first.return_value = mock_user
    user_id = 1

    response = get_user_details(user_id, db=mock_db_session)

    assert response["status"] == "success"
    assert response["user"]["username"] == mock_user.username
    mock_db_session.query.assert_called_once()

def test_get_user_details_user_not_found(mock_db_session):
    """Test the get_user_details function when the user is not found."""
    mock_db_session.query.return_value.filter_by.return_value.first.return_value = None
    user_id = 999

    with pytest.raises(Exception) as excinfo:
        get_user_details(user_id, db=mock_db_session)

    assert "User not found" in str(excinfo.value)

def test_register_user_success(mock_db_session):
    """Test the register_user function for successful registration."""
    mock_db_session.query.return_value.filter_by.return_value.first.return_value = None
    user_data = {"username": "new_user", "email": "new_user@example.com", "password": "secure_password"}

    response = register_user(user_data, db=mock_db_session)

    assert response["status"] == "success"
    assert "user_id" in response
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()

def test_register_user_existing_user(mock_db_session, mock_user):
    """Test the register_user function when the user already exists."""
    mock_db_session.query.return_value.filter_by.return_value.first.return_value = mock_user
    user_data = {"username": "test_user", "email": "test_user@example.com", "password": "secure_password"}

    with pytest.raises(Exception) as excinfo:
        register_user(user_data, db=mock_db_session)

    assert "User already exists" in str(excinfo.value)

def test_deactivate_user_success(mock_db_session, mock_user):
    """Test the deactivate_user function for successful deactivation."""
    mock_db_session.query.return_value.filter_by.return_value.first.return_value = mock_user
    user_id = 1

    response = deactivate_user(user_id, db=mock_db_session)

    assert response["status"] == "success"
    assert mock_user.is_active is False
    mock_db_session.commit.assert_called_once()

def test_deactivate_user_not_found(mock_db_session):
    """Test the deactivate_user function when the user is not found."""
    mock_db_session.query.return_value.filter_by.return_value.first.return_value = None
    user_id = 999

    with pytest.raises(Exception) as excinfo:
        deactivate_user(user_id, db=mock_db_session)

    assert "User not found" in str(excinfo.value)