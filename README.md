# Social Media App

A small, fully working social feed built with **Flask** and **SQLite**. No
JavaScript frameworks, no ORM — just server-rendered Jinja2 templates, plain
CSS, and raw SQL, wired together with Flask's application-factory pattern.

## Features

- **Accounts**: register / log in / log out with salted, hashed passwords
  (session-based auth). Post, follow, like, and comment actions require login.
- **Posts**: create short text posts.
- **Follow graph**: follow / unfollow another user. You can't follow
  yourself, and following someone you already follow is a no-op (idempotent)
  rather than an error.
- **Personalized feed**: a paginated, reverse-chronological feed of posts
  from people you follow *plus* your own posts. Posts from users you don't
  follow never appear.
- **Likes**: toggle a like on any post; the like count updates immediately.
- **Comments**: comment on a post; comments are listed oldest-first.
- **Profile page**: shows a user's bio, posts, and follower/following counts.
- **Suggested users**: a simple 2-hop "people followed by people you follow"
  query, excluding yourself and anyone you already follow.

## Project structure

```
social-media-app/
├── app/
│   ├── __init__.py      # create_app() application factory
│   ├── db.py            # SQLite connection handling (per-request)
│   ├── schema.sql        # table definitions
│   ├── auth.py           # register / login / logout blueprint
│   ├── posts.py           # feed, posts, follow, like, comment, profile
│   ├── templates/        # Jinja2 templates
│   └── static/style.css
├── tests/                # pytest test suite (Flask test client)
├── run.py                # dev entry point
└── .github/workflows/tests.yml
```

## Data model

| Table       | Columns                                                        |
|-------------|------------------------------------------------------------------|
| `user`      | id, username (unique), password_hash, bio, created_at            |
| `post`      | id, user_id, content, created_at                                  |
| `follow`    | follower_id, followed_id (composite primary key)                  |
| `post_like` | user_id, post_id, created_at (composite primary key)              |
| `comment`   | id, user_id, post_id, content, created_at                         |

Note: the like table is named `post_like`, not `like`, because `LIKE` is a
reserved SQL keyword in SQLite.

## Running it locally

```bash
git clone https://github.com/pastbologanesh0101/social-media-app.git
cd social-media-app
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python run.py                    # starts the dev server on :5000
```

Then open http://127.0.0.1:5000, register an account, and start posting.

### Example usage (curl)

```bash
# Register and log in (cookies persisted in cookies.txt)
curl -c cookies.txt -X POST http://127.0.0.1:5000/auth/register \
  -d "username=alice&password=secretpw&bio=hello there"
curl -c cookies.txt -b cookies.txt -X POST http://127.0.0.1:5000/auth/login \
  -d "username=alice&password=secretpw"

# Create a post
curl -b cookies.txt -X POST http://127.0.0.1:5000/post/create \
  -d "content=Hello, world!"

# Follow another user, then view your feed
curl -b cookies.txt -X POST http://127.0.0.1:5000/user/bob/follow
curl -b cookies.txt http://127.0.0.1:5000/
```

## Running the tests

```bash
pip install -r requirements.txt pytest
pytest -v
```

The test suite uses `create_app(testing=True)`, which points the app at a
fresh temporary SQLite file per test (created and torn down automatically),
so tests never touch a real database and don't interfere with each other.

Tests also run automatically in GitHub Actions (`.github/workflows/tests.yml`)
on every push and pull request, against Python 3.11 and 3.12.

## License

MIT — see [LICENSE](LICENSE).
