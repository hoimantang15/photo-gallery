#enabling users to change password

import io
import os
import uuid
from functools import wraps

from flask import (
    Flask,
    flash,
    redirect,
    render_template_string,
    request,
    send_file,
    session,
    url_for,
)
from google.cloud import firestore, storage
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
import resend
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)

# Required for signing cookies/sessions
app.secret_key = os.environ.get("SECRET_KEY", "replace-with-a-secure-random-key")

DEFAULT_PASSWORD = os.environ.get("GALLERY_PASSWORD", "admin123")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.com")
BUCKET_NAME = os.environ.get("BUCKET_NAME")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")

storage_client = storage.Client()
firestore_client = firestore.Client()

# Token generator for email reset links
token_serializer = URLSafeTimedSerializer(app.secret_key)

# ----------------- Helper Functions -----------------

def get_stored_password_hash():
    """Retrieve the password hash from Firestore or seed it if absent."""
    config_ref = firestore_client.collection("settings").document("auth")
    doc = config_ref.get()
    if doc.exists:
        return doc.to_dict().get("password_hash")

    initial_hash = generate_password_hash(DEFAULT_PASSWORD)
    config_ref.set({"password_hash": initial_hash})
    return initial_hash

def update_stored_password(new_password):
    """Update the stored password hash in Firestore."""
    config_ref = firestore_client.collection("settings").document("auth")
    new_hash = generate_password_hash(new_password)
    config_ref.set({"password_hash": new_hash}, merge=True)

def send_reset_email(to_email, reset_url):
    """Send reset link email via Resend API over HTTPS."""
    resend.api_key = RESEND_API_KEY
    params = {
        "from": "onboarding@resend.dev",  # Resend's free testing sender
        "to": [to_email],
        "subject": "Reset Your Gallery Password",
        "html": f"""
            <h3>Password Reset Request</h3>
            <p>A request was received to reset your gallery password.</p>
            <p><a href="{reset_url}">Click here to set a new password</a> (valid for 15 minutes).</p>
            <p>If you did not request this, you can safely ignore this email.</p>
        """,
    }
    return resend.Emails.send(params)

# ----------------- Templates -----------------

LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Login - Community Photo Gallery</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #f5f7fa;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }
        .login-card {
            background: white;
            padding: 30px 40px;
            border-radius: 10px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            width: 100%;
            max-width: 360px;
            text-align: center;
        }
        input[type="password"] {
            width: 100%;
            padding: 12px;
            margin: 15px 0 10px 0;
            box-sizing: border-box;
            border: 1px solid #ccc;
            border-radius: 5px;
            font-size: 14px;
        }
        button {
            width: 100%;
            padding: 12px;
            background: #007bff;
            color: white;
            border: none;
            border-radius: 5px;
            font-size: 15px;
            cursor: pointer;
            margin-top: 10px;
        }
        button:hover { background: #0056b3; }
        .error { color: #d9534f; margin-bottom: 15px; font-size: 14px; }
        .success { color: #28a745; margin-bottom: 15px; font-size: 14px; }
        .forgot-link {
            display: block;
            margin-top: 15px;
            font-size: 13px;
            color: #6c757d;
            text-decoration: none;
        }
        .forgot-link:hover { text-decoration: underline; color: #007bff; }
    </style>
</head>
<body>
    <div class="login-card">
        <h2>🔒 Protected Gallery</h2>
        <p>Please enter the password to view and upload photos.</p>

        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div class="{{ category }}">{{ message }}</div>
            {% endfor %}
          {% endif %}
        {% endwith %}

        <form method="POST">
            <input type="password" name="password" placeholder="Enter password" required autofocus>
            <button type="submit">Access Gallery</button>
        </form>
        <a href="/forgot-password" class="forgot-link">Forgot password?</a>
    </div>
</body>
</html>
"""

FORGOT_PASSWORD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Forgot Password - Gallery</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #f5f7fa;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }
        .card {
            background: white;
            padding: 30px 40px;
            border-radius: 10px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            width: 100%;
            max-width: 360px;
            text-align: center;
        }
        input[type="email"] {
            width: 100%;
            padding: 12px;
            margin: 15px 0;
            box-sizing: border-box;
            border: 1px solid #ccc;
            border-radius: 5px;
            font-size: 14px;
        }
        button {
            width: 100%;
            padding: 12px;
            background: #007bff;
            color: white;
            border: none;
            border-radius: 5px;
            font-size: 15px;
            cursor: pointer;
        }
        button:hover { background: #0056b3; }
        .error { color: #d9534f; margin-bottom: 12px; font-size: 14px; }
        .success { color: #28a745; margin-bottom: 12px; font-size: 14px; }
        .back-link { display: inline-block; margin-top: 15px; color: #007bff; text-decoration: none; font-size: 14px; }
    </style>
</head>
<body>
    <div class="card">
        <h2>Forgot Password</h2>
        <p>Enter the recovery email address associated with this gallery.</p>

        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div class="{{ category }}">{{ message }}</div>
            {% endfor %}
          {% endif %}
        {% endwith %}

        <form method="POST">
            <input type="email" name="email" placeholder="admin@example.com" required autofocus>
            <button type="submit">Send Reset Link</button>
        </form>
        <a href="/login" class="back-link">Back to Login</a>
    </div>
</body>
</html>
"""

RESET_TOKEN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Set New Password - Gallery</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #f5f7fa;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }
        .card {
            background: white;
            padding: 30px 40px;
            border-radius: 10px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            width: 100%;
            max-width: 360px;
            text-align: center;
        }
        input[type="password"] {
            width: 100%;
            padding: 12px;
            margin: 10px 0;
            box-sizing: border-box;
            border: 1px solid #ccc;
            border-radius: 5px;
            font-size: 14px;
        }
        button {
            width: 100%;
            padding: 12px;
            background: #28a745;
            color: white;
            border: none;
            border-radius: 5px;
            font-size: 15px;
            cursor: pointer;
            margin-top: 10px;
        }
        button:hover { background: #218838; }
        .error { color: #d9534f; margin-bottom: 12px; font-size: 14px; }
    </style>
</head>
<body>
    <div class="card">
        <h2>Set New Password</h2>

        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div class="{{ category }}">{{ message }}</div>
            {% endfor %}
          {% endif %}
        {% endwith %}

        <form method="POST">
            <input type="password" name="new_password" placeholder="New password" required autofocus>
            <input type="password" name="confirm_password" placeholder="Confirm new password" required>
            <button type="submit">Save New Password</button>
        </form>
    </div>
</body>
</html>
"""

CHANGE_PASSWORD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Change Password - Gallery</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #f5f7fa;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }
        .card {
            background: white;
            padding: 30px 40px;
            border-radius: 10px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            width: 100%;
            max-width: 360px;
            text-align: center;
        }
        input[type="password"] {
            width: 100%;
            padding: 12px;
            margin: 10px 0;
            box-sizing: border-box;
            border: 1px solid #ccc;
            border-radius: 5px;
            font-size: 14px;
        }
        button {
            width: 100%;
            padding: 12px;
            background: #28a745;
            color: white;
            border: none;
            border-radius: 5px;
            font-size: 15px;
            cursor: pointer;
            margin-top: 10px;
        }
        button:hover { background: #218838; }
        .error { color: #d9534f; margin-bottom: 12px; font-size: 14px; }
        .back-link { display: inline-block; margin-top: 15px; color: #007bff; text-decoration: none; }
    </style>
</head>
<body>
    <div class="card">
        <h2>🔑 Change Password</h2>

        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div class="{{ category }}">{{ message }}</div>
            {% endfor %}
          {% endif %}
        {% endwith %}

        <form method="POST">
            <input type="password" name="current_password" placeholder="Current password" required autofocus>
            <input type="password" name="new_password" placeholder="New password" required>
            <input type="password" name="confirm_password" placeholder="Confirm new password" required>
            <button type="submit">Update Password</button>
        </form>
        <a href="/" class="back-link">Back to Gallery</a>
    </div>
</body>
</html>
"""

GALLERY_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Community Photo Gallery</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 1000px;
            margin: 40px auto;
            padding: 20px;
            background: #f5f7fa;
        }
        .header-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        .nav-links { display: flex; gap: 10px; }
        .nav-link {
            text-decoration: none;
            padding: 8px 16px;
            border-radius: 5px;
            font-weight: bold;
        }
        .change-pw-link {
            color: #007bff;
            border: 1px solid #007bff;
        }
        .change-pw-link:hover {
            background: #007bff;
            color: white;
        }
        .logout-link {
            color: #d9534f;
            border: 1px solid #d9534f;
        }
        .logout-link:hover {
            background: #d9534f;
            color: white;
        }
        .upload-box {
            background: white;
            padding: 25px;
            border-radius: 10px;
            margin-bottom: 30px;
        }
        input[type="text"], input[type="file"] {
            margin: 10px 0;
            padding: 8px;
        }
        button {
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            background: #28a745;
            color: white;
            cursor: pointer;
        }
        button:hover { background: #218838; }
        .gallery {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 20px;
        }
        .photo {
            background: white;
            padding: 10px;
            border-radius: 10px;
        }
        .photo img {
            width: 100%;
            height: 220px;
            object-fit: cover;
            border-radius: 8px;
            cursor: pointer;
            transition: transform 0.2s ease, opacity 0.2s ease;
        }
        .photo img:hover {
            opacity: 0.9;
            transform: scale(1.02);
        }
        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.85);
            justify-content: center;
            align-items: center;
            flex-direction: column;
        }
        .modal-content {
            max-width: 90vw;
            max-height: 80vh;
            border-radius: 6px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.6);
            object-fit: contain;
        }
        .modal-caption {
            color: #fff;
            margin-top: 15px;
            font-size: 1.1rem;
            text-align: center;
        }
        .modal-close {
            position: absolute;
            top: 20px;
            right: 30px;
            color: #fff;
            font-size: 35px;
            font-weight: bold;
            cursor: pointer;
            user-select: none;
        }
        .modal-close:hover { color: #bbb; }
    </style>
</head>
<body>

<div class="header-bar">
    <h1>📸 Community Photo Gallery</h1>
    <div class="nav-links">
        <a href="/change-password" class="nav-link change-pw-link">Change Password</a>
        <a href="/logout" class="nav-link logout-link">Logout</a>
    </div>
</div>

<div class="upload-box">
    <h2>Upload a photo</h2>
    <form method="POST" enctype="multipart/form-data">
        <input type="hidden" name="upload_id" value="{{ upload_id }}">
        <input type="text" name="uploader" placeholder="Your name" required><br>
        <input type="text" name="caption" placeholder="Photo caption" required><br>
        <input type="file" name="photo" accept="image/*" required><br>
        <button type="submit">Upload Photo</button>
    </form>
</div>

<h2>Gallery</h2>

<div class="gallery">
{% for photo in photos %}
    <div class="photo">
        <img src="/image/{{ photo.filename }}" alt="{{ photo.caption }}" onclick="openModal(this)">
        <h3>{{ photo.caption }}</h3>
        <p>Uploaded by: {{ photo.uploader }}</p>
    </div>
{% endfor %}
</div>

<div id="imageModal" class="modal" onclick="closeModal(event)">
    <span class="modal-close" onclick="forceCloseModal()">&times;</span>
    <img class="modal-content" id="modalImg">
    <div id="modalCaption" class="modal-caption"></div>
</div>

<script>
    const modal = document.getElementById("imageModal");
    const modalImg = document.getElementById("modalImg");
    const modalCaption = document.getElementById("modalCaption");

    function openModal(imgElement) {
        modal.style.display = "flex";
        modalImg.src = imgElement.src;
        modalCaption.textContent = imgElement.alt;
    }

    function closeModal(event) {
        if (event.target === modal) modal.style.display = "none";
    }

    function forceCloseModal() { modal.style.display = "none"; }

    document.addEventListener("keydown", function(event) {
        if (event.key === "Escape") modal.style.display = "none";
    });
</script>

</body>
</html>
"""

# ----------------- Routes & Decorators -----------------

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("authenticated"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        submitted_pw = request.form.get("password", "")
        stored_hash = get_stored_password_hash()

        if check_password_hash(stored_hash, submitted_pw):
            session["authenticated"] = True
            return redirect(url_for("gallery"))
        flash("Incorrect password. Please try again.", "error")

    return render_template_string(LOGIN_HTML)

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        submitted_email = request.form.get("email", "").strip().lower()

        if submitted_email == ADMIN_EMAIL.lower():
            token = token_serializer.dumps(submitted_email, salt="password-reset-salt")
            reset_url = url_for("reset_with_token", token=token, _external=True)

            try:
                send_reset_email(submitted_email, reset_url)
            except Exception as e:
                app.logger.error(f"Failed to send email: {e}")
                flash(f"Failed to send email: {e}", "error")
                return render_template_string(FORGOT_PASSWORD_HTML)

        # Generic flash message to prevent email enumeration
        flash("If that email address matches our records, a reset link has been sent.", "success")
        return redirect(url_for("login"))

    return render_template_string(FORGOT_PASSWORD_HTML)

@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_with_token(token):
    try:
        # Link valid for 15 minutes (900 seconds)
        email = token_serializer.loads(token, salt="password-reset-salt", max_age=900)
    except SignatureExpired:
        flash("The password reset link has expired. Please request a new one.", "error")
        return redirect(url_for("forgot_password"))
    except BadSignature:
        flash("Invalid reset link.", "error")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        new_pw = request.form.get("new_password", "")
        confirm_pw = request.form.get("confirm_password", "")

        if len(new_pw) < 6:
            flash("Password must be at least 6 characters long.", "error")
        elif new_pw != confirm_pw:
            flash("Passwords do not match.", "error")
        else:
            update_stored_password(new_pw)
            flash("Password reset successfully. You can now log in.", "success")
            return redirect(url_for("login"))

    return render_template_string(RESET_TOKEN_HTML)

@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current_pw = request.form.get("current_password", "")
        new_pw = request.form.get("new_password", "")
        confirm_pw = request.form.get("confirm_password", "")

        stored_hash = get_stored_password_hash()

        if not check_password_hash(stored_hash, current_pw):
            flash("Current password is incorrect.", "error")
        elif len(new_pw) < 6:
            flash("New password must be at least 6 characters long.", "error")
        elif new_pw != confirm_pw:
            flash("New passwords do not match.", "error")
        else:
            update_stored_password(new_pw)
            flash("Password updated successfully! Please log in again.", "success")
            session.clear()
            return redirect(url_for("login"))

    return render_template_string(CHANGE_PASSWORD_HTML)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/", methods=["GET", "POST"])
@login_required
def gallery():
    bucket = storage_client.bucket(BUCKET_NAME)

    if request.method == "POST":
        photo = request.files.get("photo")
        uploader = request.form.get("uploader", "").strip()
        caption = request.form.get("caption", "").strip()
        upload_id = request.form.get("upload_id", "").strip()

        if photo and photo.filename and upload_id:
            photo_ref = firestore_client.collection("photos").document(upload_id)
            existing = photo_ref.get()

            if not existing.exists:
                extension = os.path.splitext(photo.filename)[1].lower()
                filename = f"{upload_id}{extension}"

                blob = bucket.blob(filename)
                blob.upload_from_file(photo, content_type=photo.content_type)

                photo_ref.set({
                    "filename": filename,
                    "caption": caption,
                    "uploader": uploader,
                    "bucket": BUCKET_NAME,
                    "content_type": photo.content_type,
                    "uploaded_at": firestore.SERVER_TIMESTAMP,
                })

            return redirect("/")

    photos = []
    photos_ref = (
        firestore_client.collection("photos")
        .order_by("uploaded_at", direction=firestore.Query.DESCENDING)
    )

    for doc in photos_ref.stream():
        photos.append(doc.to_dict())

    return render_template_string(
        GALLERY_HTML,
        photos=photos,
        upload_id=str(uuid.uuid4()),
    )

@app.route("/image/<filename>")
@login_required
def image(filename):
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(filename)
    image_data = blob.download_as_bytes()

    return send_file(io.BytesIO(image_data), mimetype=blob.content_type)

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8080)),
    )

