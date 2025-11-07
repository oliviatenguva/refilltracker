from flask import Flask, request, jsonify, render_template
from azure.storage.blob import BlobServiceClient, ContentSettings
from datetime import datetime
import os
from dotenv import load_dotenv

from werkzeug.utils import secure_filename

# Load environment variables
load_dotenv()

# Configuration
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
STORAGE_ACCOUNT_URL = os.getenv("STORAGE_ACCOUNT_URL", "https://refilltrackerstorage.blob.core.windows.net")
CONTAINER_NAME = os.getenv("IMAGES_CONTAINER", "refill-images")
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

# Initialize Blob service client
bsc = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
cc = bsc.get_container_client(CONTAINER_NAME)

# Flask app setup
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE


def is_allowed_file(filename):
    """Return True if filename has an allowed image extension."""
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "bmp", "webp", "tiff"}
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def generate_blob_name(original_filename):
    """Create a sanitized, timestamped blob name."""
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    safe_filename = secure_filename(original_filename)
    return f"{timestamp}-{safe_filename}"


@app.route("/")
def index():
    """Serve the Refill Tracker upload & gallery page."""
    return render_template("index.html")


@app.route("/api/v1/upload", methods=["POST"])
def upload():
    """Upload an image to Azure Blob Storage."""
    try:
        if "file" not in request.files:
            return jsonify(ok=False, error="No file provided"), 400

        f = request.files["file"]

        if f.filename == "":
            return jsonify(ok=False, error="No file selected"), 400

        if not is_allowed_file(f.filename):
            return jsonify(ok=False, error="Invalid file type — only image files allowed."), 400

        if not f.content_type or not f.content_type.startswith("image/"):
            return jsonify(ok=False, error="File must be an image"), 400

        blob_name = generate_blob_name(f.filename)
        blob_client = cc.get_blob_client(blob_name)
        file_content = f.read()

        blob_client.upload_blob(
            file_content,
            overwrite=True,
            content_settings=ContentSettings(content_type=f.content_type),
        )

        blob_url = f"{cc.url}/{blob_name}"
        app.logger.info(f"Uploaded successfully: {blob_name}")
        return jsonify(ok=True, url=blob_url), 200

    except Exception as e:
        app.logger.error(f"Upload error: {e}")
        return jsonify(ok=False, error=str(e)), 500


@app.route("/api/v1/gallery", methods=["GET"])
def gallery():
    """List and return URLs of all uploaded images."""
    try:
        blob_list = cc.list_blobs()
        gallery_urls = [f"{cc.url}/{b.name}" for b in blob_list]
        gallery_urls.sort(reverse=True)
        return jsonify(ok=True, gallery=gallery_urls), 200
    except Exception as e:
        app.logger.error(f"Gallery error: {e}")
        return jsonify(ok=False, error=str(e)), 500


@app.route("/api/v1/health", methods=["GET"])
def health():
    """Simple health-check endpoint."""
    return "OK", 200


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)