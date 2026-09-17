from datetime import datetime, timezone

from flask import (
    Blueprint,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)

from .auth import login_required
from .db import get_db

bp = Blueprint("posts", __name__)

PER_PAGE = 10


def get_user_or_404(username):
    user = (
        get_db()
        .execute("SELECT * FROM user WHERE username = ?", (username,))
        .fetchone()
    )
    if user is None:
        abort(404, f"User {username!r} does not exist.")
    return user


def is_following(follower_id, followed_id):
    row = get_db().execute(
        "SELECT 1 FROM follow WHERE follower_id = ? AND followed_id = ?",
        (follower_id, followed_id),
    ).fetchone()
    return row is not None


def follower_count(user_id):
    return get_db().execute(
        "SELECT COUNT(*) AS c FROM follow WHERE followed_id = ?", (user_id,)
    ).fetchone()["c"]


def following_count(user_id):
    return get_db().execute(
        "SELECT COUNT(*) AS c FROM follow WHERE follower_id = ?", (user_id,)
    ).fetchone()["c"]


def attach_like_info(db, posts, viewer_id):
    """Attach like_count and liked_by_viewer to each post row (as dicts)."""
    result = []
    for post in posts:
        post = dict(post)
        like_count = db.execute(
            "SELECT COUNT(*) AS c FROM post_like WHERE post_id = ?",
            (post["id"],),
        ).fetchone()["c"]
        comment_count = db.execute(
            "SELECT COUNT(*) AS c FROM comment WHERE post_id = ?",
            (post["id"],),
        ).fetchone()["c"]
        liked = False
        if viewer_id is not None:
            liked = db.execute(
                "SELECT 1 FROM post_like WHERE user_id = ? AND post_id = ?",
                (viewer_id, post["id"]),
            ).fetchone() is not None
        post["like_count"] = like_count
        post["comment_count"] = comment_count
        post["liked_by_viewer"] = liked
        result.append(post)
    return result


@bp.route("/")
def feed():
    db = get_db()

    if g.user is None:
        return render_template("feed.html", posts=[], page=1, has_next=False)

    page = request.args.get("page", 1, type=int)
    if page < 1:
        page = 1
    offset = (page - 1) * PER_PAGE

    # Posts from users the viewer follows, plus the viewer's own posts.
    rows = db.execute(
        """
        SELECT post.*, user.username AS author
        FROM post
        JOIN user ON user.id = post.user_id
        WHERE post.user_id = ?
           OR post.user_id IN (
                SELECT followed_id FROM follow WHERE follower_id = ?
           )
        ORDER BY post.created_at DESC, post.id DESC
        LIMIT ? OFFSET ?
        """,
        (g.user["id"], g.user["id"], PER_PAGE + 1, offset),
    ).fetchall()

    has_next = len(rows) > PER_PAGE
    rows = rows[:PER_PAGE]
    posts = attach_like_info(db, rows, g.user["id"])

    suggestions = db.execute(
        """
        SELECT u.id, u.username, COUNT(*) AS mutual
        FROM follow f1
        JOIN follow f2 ON f1.followed_id = f2.follower_id
        JOIN user u ON u.id = f2.followed_id
        WHERE f1.follower_id = ?
          AND f2.followed_id != ?
          AND f2.followed_id NOT IN (
                SELECT followed_id FROM follow WHERE follower_id = ?
          )
        GROUP BY u.id
        ORDER BY mutual DESC, u.username ASC
        LIMIT 5
        """,
        (g.user["id"], g.user["id"], g.user["id"]),
    ).fetchall()

    return render_template(
        "feed.html",
        posts=posts,
        page=page,
        has_next=has_next,
        suggestions=suggestions,
    )


@bp.route("/post/create", methods=("POST",))
@login_required
def create_post():
    content = request.form.get("content", "").strip()
    if not content:
        flash("Post content cannot be empty.", "error")
    else:
        db = get_db()
        db.execute(
            "INSERT INTO post (user_id, content, created_at) VALUES (?, ?, ?)",
            (g.user["id"], content, datetime.now(timezone.utc).isoformat()),
        )
        db.commit()
    return redirect(url_for("posts.feed"))


@bp.route("/post/<int:post_id>/like", methods=("POST",))
@login_required
def toggle_like(post_id):
    db = get_db()
    post = db.execute("SELECT * FROM post WHERE id = ?", (post_id,)).fetchone()
    if post is None:
        abort(404)

    existing = db.execute(
        "SELECT 1 FROM post_like WHERE user_id = ? AND post_id = ?",
        (g.user["id"], post_id),
    ).fetchone()

    if existing is None:
        db.execute(
            "INSERT INTO post_like (user_id, post_id, created_at) VALUES (?, ?, ?)",
            (g.user["id"], post_id, datetime.now(timezone.utc).isoformat()),
        )
    else:
        db.execute(
            "DELETE FROM post_like WHERE user_id = ? AND post_id = ?",
            (g.user["id"], post_id),
        )
    db.commit()

    next_url = request.form.get("next") or url_for("posts.feed")
    return redirect(next_url)


@bp.route("/post/<int:post_id>/comment", methods=("POST",))
@login_required
def add_comment(post_id):
    db = get_db()
    post = db.execute("SELECT * FROM post WHERE id = ?", (post_id,)).fetchone()
    if post is None:
        abort(404)

    content = request.form.get("content", "").strip()
    if content:
        db.execute(
            "INSERT INTO comment (user_id, post_id, content, created_at)"
            " VALUES (?, ?, ?, ?)",
            (g.user["id"], post_id, content, datetime.now(timezone.utc).isoformat()),
        )
        db.commit()
    else:
        flash("Comment cannot be empty.", "error")

    next_url = request.form.get("next") or url_for("posts.feed")
    return redirect(next_url)


@bp.route("/post/<int:post_id>/comments")
def post_comments(post_id):
    db = get_db()
    post = db.execute(
        "SELECT post.*, user.username AS author FROM post"
        " JOIN user ON user.id = post.user_id WHERE post.id = ?",
        (post_id,),
    ).fetchone()
    if post is None:
        abort(404)

    comments = db.execute(
        "SELECT comment.*, user.username AS author FROM comment"
        " JOIN user ON user.id = comment.user_id"
        " WHERE comment.post_id = ?"
        " ORDER BY comment.created_at ASC, comment.id ASC",
        (post_id,),
    ).fetchall()

    viewer_id = g.user["id"] if g.user else None
    post = attach_like_info(db, [post], viewer_id)[0]

    return render_template("post_detail.html", post=post, comments=comments)


@bp.route("/user/<username>/follow", methods=("POST",))
@login_required
def follow(username):
    target = get_user_or_404(username)

    if target["id"] == g.user["id"]:
        flash("You can't follow yourself.", "error")
        return redirect(url_for("posts.profile", username=username))

    db = get_db()
    # INSERT OR IGNORE makes repeated follow requests idempotent instead of
    # raising a duplicate-key error.
    db.execute(
        "INSERT OR IGNORE INTO follow (follower_id, followed_id) VALUES (?, ?)",
        (g.user["id"], target["id"]),
    )
    db.commit()
    return redirect(url_for("posts.profile", username=username))


@bp.route("/user/<username>/unfollow", methods=("POST",))
@login_required
def unfollow(username):
    target = get_user_or_404(username)

    db = get_db()
    db.execute(
        "DELETE FROM follow WHERE follower_id = ? AND followed_id = ?",
        (g.user["id"], target["id"]),
    )
    db.commit()
    return redirect(url_for("posts.profile", username=username))


@bp.route("/user/<username>")
def profile(username):
    user = get_user_or_404(username)
    db = get_db()

    rows = db.execute(
        "SELECT post.*, user.username AS author FROM post"
        " JOIN user ON user.id = post.user_id"
        " WHERE post.user_id = ?"
        " ORDER BY post.created_at DESC, post.id DESC",
        (user["id"],),
    ).fetchall()
    viewer_id = g.user["id"] if g.user else None
    posts = attach_like_info(db, rows, viewer_id)

    viewer_follows = False
    if g.user is not None:
        viewer_follows = is_following(g.user["id"], user["id"])

    return render_template(
        "profile.html",
        profile_user=user,
        posts=posts,
        followers=follower_count(user["id"]),
        following=following_count(user["id"]),
        viewer_follows=viewer_follows,
    )
