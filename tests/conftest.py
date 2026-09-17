import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from app import create_app


@pytest.fixture
def app():
    app = create_app(testing=True)
    yield app
    db_fd = app.config.get("DB_FD")
    if db_fd is not None:
        os.close(db_fd)
    db_path = app.config.get("DATABASE")
    if db_path and os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


def register(client, username, password="password123", bio=""):
    return client.post(
        "/auth/register",
        data={"username": username, "password": password, "bio": bio},
        follow_redirects=True,
    )


def login(client, username, password="password123"):
    return client.post(
        "/auth/login",
        data={"username": username, "password": password},
        follow_redirects=True,
    )


def register_and_login(client, username, password="password123", bio=""):
    register(client, username, password, bio)
    return login(client, username, password)
