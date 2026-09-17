import os
import tempfile

from flask import Flask


def create_app(testing=False, test_config=None):
    """Application factory.

    When ``testing=True`` the app is configured with a fresh temporary
    SQLite database file (created fresh for every call), so each test
    gets an isolated database.
    """
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY="dev",
        DATABASE=os.path.join(app.instance_path, "social.sqlite"),
        TESTING=False,
    )

    if testing:
        db_fd, db_path = tempfile.mkstemp(suffix=".sqlite")
        app.config.update(
            TESTING=True,
            DATABASE=db_path,
            DB_FD=db_fd,
            WTF_CSRF_ENABLED=False,
        )

    if test_config:
        app.config.update(test_config)

    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass

    from . import db

    db.init_app(app)

    with app.app_context():
        db.init_db()

    from . import auth

    app.register_blueprint(auth.bp)

    from . import posts

    app.register_blueprint(posts.bp)

    return app
