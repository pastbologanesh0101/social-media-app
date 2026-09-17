import re

from app.db import get_db
from .conftest import login, register, register_and_login


def get_user_id(app, username):
    with app.app_context():
        row = get_db().execute(
            "SELECT id FROM user WHERE username = ?", (username,)
        ).fetchone()
        return row["id"]


def create_post(client, content):
    return client.post(
        "/post/create", data={"content": content}, follow_redirects=True
    )


def follow(client, username):
    return client.post(f"/user/{username}/follow", follow_redirects=True)


def unfollow(client, username):
    return client.post(f"/user/{username}/unfollow", follow_redirects=True)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_register_and_login(client):
    resp = register(client, "alice")
    assert resp.status_code == 200

    resp = login(client, "alice")
    assert resp.status_code == 200
    assert b"alice" in resp.data
    assert b"Your feed" in resp.data


def test_login_with_wrong_password_fails(client):
    register(client, "bob")
    resp = login(client, "bob", password="wrong-password")
    assert b"Incorrect username or password" in resp.data


def test_duplicate_registration_rejected(client):
    register(client, "carol")
    resp = register(client, "carol")
    assert b"already registered" in resp.data


# ---------------------------------------------------------------------------
# Posts
# ---------------------------------------------------------------------------


def test_create_post_requires_login(client):
    resp = create_post(client, "hello world")
    # Redirected to the login page instead of creating the post.
    assert b"Log in" in resp.data


def test_create_post_appears_in_own_feed(client):
    register_and_login(client, "dave")
    resp = create_post(client, "my first post")
    assert b"my first post" in resp.data


# ---------------------------------------------------------------------------
# Follow / unfollow
# ---------------------------------------------------------------------------


def test_cannot_follow_self(client):
    register_and_login(client, "erin")
    resp = follow(client, "erin")
    assert b"follow yourself" in resp.data

    profile = client.get("/user/erin").data
    assert b"0</strong> follower" in profile


def test_follow_and_unfollow_updates_counts(app):
    with app.test_client() as c1:
        register_and_login(c1, "frank")
    with app.test_client() as c2:
        register_and_login(c2, "grace")
        follow(c2, "frank")

        profile = c2.get("/user/frank").data
        assert b"1</strong> follower" in profile

        grace_profile = c2.get("/user/grace").data
        assert b"1</strong> following" in grace_profile

        unfollow(c2, "frank")
        profile_after = c2.get("/user/frank").data
        assert b"0</strong> follower" in profile_after


def test_duplicate_follow_is_idempotent(app):
    with app.test_client() as c1:
        register_and_login(c1, "heidi")
    with app.test_client() as c2:
        register_and_login(c2, "ivan")
        follow(c2, "heidi")
        follow(c2, "heidi")  # second follow should not error or double count

        profile = c2.get("/user/heidi").data
        assert b"1</strong> follower" in profile


# ---------------------------------------------------------------------------
# Feed
# ---------------------------------------------------------------------------


def test_feed_includes_followed_and_own_posts_excludes_others(app):
    with app.test_client() as author_b:
        register_and_login(author_b, "user_b")
        create_post(author_b, "post from b")

    with app.test_client() as author_c:
        register_and_login(author_c, "user_c")
        create_post(author_c, "post from c")

    with app.test_client() as viewer:
        register_and_login(viewer, "user_a")
        create_post(viewer, "post from a")
        follow(viewer, "user_b")

        feed_html = viewer.get("/").data
        assert b"post from a" in feed_html
        assert b"post from b" in feed_html
        assert b"post from c" not in feed_html


def test_feed_is_reverse_chronological(client):
    register_and_login(client, "judy")
    create_post(client, "first post")
    create_post(client, "second post")
    create_post(client, "third post")

    feed_html = client.get("/").data.decode()
    pos_first = feed_html.find("first post")
    pos_second = feed_html.find("second post")
    pos_third = feed_html.find("third post")

    assert pos_third != -1 and pos_second != -1 and pos_first != -1
    # Most recent post ("third") should appear before older ones in the HTML.
    assert pos_third < pos_second < pos_first


# ---------------------------------------------------------------------------
# Likes
# ---------------------------------------------------------------------------


def test_like_toggle_and_count(app):
    with app.test_client() as author:
        register_and_login(author, "kim")
        create_post(author, "likeable post")

    post_id = None
    with app.app_context():
        row = get_db().execute("SELECT id FROM post WHERE content = ?", ("likeable post",)).fetchone()
        post_id = row["id"]

    with app.test_client() as liker:
        register_and_login(liker, "leo")
        next_url = f"/post/{post_id}/comments"

        resp = liker.post(f"/post/{post_id}/like", data={"next": next_url}, follow_redirects=True)
        assert b"\xe2\x99\xa5 1" in resp.data  # heart-filled with count 1

        resp = liker.post(f"/post/{post_id}/like", data={"next": next_url}, follow_redirects=True)
        assert b"\xe2\x99\xa5 1" not in resp.data
        assert b"\xe2\x99\xa1 0" in resp.data  # empty heart, count back to 0


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------


def test_comment_added_and_listed_chronologically(app):
    with app.test_client() as author:
        register_and_login(author, "mona")
        create_post(author, "commentable post")

    with app.app_context():
        post_id = get_db().execute(
            "SELECT id FROM post WHERE content = ?", ("commentable post",)
        ).fetchone()["id"]

    with app.test_client() as commenter:
        register_and_login(commenter, "nate")
        commenter.post(f"/post/{post_id}/comment", data={"content": "first!"}, follow_redirects=True)
        commenter.post(f"/post/{post_id}/comment", data={"content": "second!"}, follow_redirects=True)

        page = commenter.get(f"/post/{post_id}/comments").data.decode()
        assert page.find("first!") < page.find("second!")


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


def test_profile_shows_follower_and_following_counts(app):
    with app.test_client() as c1:
        register_and_login(c1, "oscar")
    with app.test_client() as c2:
        register_and_login(c2, "penny")
        follow(c2, "oscar")

        oscar_profile = c2.get("/user/oscar").data
        assert b"1</strong> follower" in oscar_profile
        assert b"0</strong> following" in oscar_profile

        penny_profile = c2.get("/user/penny").data
        assert b"0</strong> follower" in penny_profile
        assert b"1</strong> following" in penny_profile


# ---------------------------------------------------------------------------
# Suggested users (2-hop graph query)
# ---------------------------------------------------------------------------


def test_suggested_users_two_hop_excludes_self_and_already_followed(app):
    # quinn -> rex -> sam  (quinn should be suggested "sam", via rex)
    with app.test_client() as c_sam:
        register_and_login(c_sam, "sam")

    with app.test_client() as c_rex:
        register_and_login(c_rex, "rex")
        follow(c_rex, "sam")

    with app.test_client() as c_quinn:
        register_and_login(c_quinn, "quinn")
        follow(c_quinn, "rex")

        feed_html = c_quinn.get("/").data.decode()
        # sam is a 2-hop suggestion (quinn -> rex -> sam)
        assert "sam" in feed_html
        # rex is already followed, must not appear in the suggestions list
        suggestions_section = feed_html.split("Suggested for you")[1] if "Suggested for you" in feed_html else ""
        assert "rex" not in suggestions_section
        assert "quinn" not in suggestions_section
