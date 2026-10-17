# password protected photo gallery
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

app = Flask(__name__)

# Required for signing cookies/sessions
app.secret_key = os.environ.get("SECRET_KEY", "replace-with-a-secure-random-key")

# Set the password via environment variable (default: 'admin123' for testing)
GALLERY_PASSWORD = os.environ.get("GALLERY_PASSWORD", "admin123")

storage_client = storage.Client()
firestore_client = firestore.Client()

BUCKET_NAME = os.environ.get("BUCKET_NAME")

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
        button:hover {
            background: #0056b3;
        }
        .error {
            color: #d9534f;
            margin-bottom: 15px;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="login-card">
        <h2>🔒 Protected Gallery</h2>
        <p>Please enter the password to view and upload photos.</p>

        {% with messages = get_flashed_messages() %}
          {% if messages %}
            <div class="error">{{ messages[0] }}</div>
          {% endif %}
        {% endwith %}

        <form method="POST">
            <input type="password" name="password" placeholder="Enter password" required autofocus>
            <button type="submit">Access Gallery</button>
        </form>
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

        .logout-link {
            text-decoration: none;
            color: #d9534f;
            font-weight: bold;
            padding: 8px 16px;
            border: 1px solid #d9534f;
            border-radius: 5px;
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

        button:hover {
            background: #218838;
        }

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

        /* Lightbox Modal Styles */
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

        .modal-close:hover {
            color: #bbb;
        }
    </style>
</head>

<body>

<div class="header-bar">
    <h1>📸 Community Photo Gallery</h1>
    <a href="/logout" class="logout-link">Logout</a>
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

<!-- Modal Container -->
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
        if (event.target === modal) {
            modal.style.display = "none";
        }
    }

    function forceCloseModal() {
        modal.style.display = "none";
    }

    document.addEventListener("keydown", function(event) {
        if (event.key === "Escape") {
            modal.style.display = "none";
        }
    });
</script>

</body>
</html>
"""


def login_required(f):
    """Decorator to require login on protected endpoints."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("authenticated"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        submitted_pw = request.form.get("password")
        if submitted_pw == GALLERY_PASSWORD:
            session["authenticated"] = True
            return redirect(url_for("gallery"))
        flash("Incorrect password. Please try again.")

    return render_template_string(LOGIN_HTML)


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

