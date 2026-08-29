import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, render_template, send_from_directory, url_for

load_dotenv()

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}

# 固定的三个文件夹 key,对应 .env 中的配置项
FOLDER_KEYS = ["Small_To_Remember", "Large_To_Remember", "ToDo"]


def load_folders():
    folders = {}
    for key in FOLDER_KEYS:
        raw = os.environ.get(key)
        if raw:
            path = Path(raw).expanduser()
            folders[key] = path
    return folders


FOLDERS = load_folders()

app = Flask(__name__)


def get_folder_path(key):
    if key not in FOLDER_KEYS:
        abort(404, description=f"未知的文件夹 key: {key}")
    path = FOLDERS.get(key)
    if path is None:
        abort(404, description=f"文件夹 key '{key}' 未在 .env 中配置")
    return path


def list_images(path: Path):
    """列出目录下所有图片,按修改时间从旧到新排序。"""
    if path is None or not path.exists():
        return []
    items = [
        entry
        for entry in path.iterdir()
        if entry.is_file() and entry.suffix.lower() in IMAGE_EXTENSIONS
    ]
    items.sort(key=lambda p: p.stat().st_mtime)  # 旧 -> 新
    return items


@app.route("/")
def index():
    summaries = []
    for key in FOLDER_KEYS:
        path = FOLDERS.get(key)
        configured = path is not None
        count = len(list_images(path)) if configured else 0
        summaries.append({
            "key": key,
            "configured": configured,
            "path": str(path) if configured else None,
            "count": count,
        })
    return render_template("index.html", folders=summaries)


@app.route("/api/folders")
def api_folders():
    result = []
    for key in FOLDER_KEYS:
        path = FOLDERS.get(key)
        configured = path is not None
        count = len(list_images(path)) if configured else 0
        result.append({
            "key": key,
            "name": key,
            "configured": configured,
            "count": count,
            "browse_url": url_for("browse", key=key, _external=True) if configured else None,
        })
    return jsonify(result)


@app.route("/api/folders/<key>/count")
def api_folder_count(key):
    path = get_folder_path(key)
    count = len(list_images(path))
    return jsonify({
        "key": key,
        "name": key,
        "count": count,
        "browse_url": url_for("browse", key=key, _external=True),
    })


@app.route("/browse/<key>")
def browse(key):
    path = get_folder_path(key)
    images = list_images(path)
    return render_template(
        "gallery.html",
        key=key,
        images=[img.name for img in images],
        count=len(images),
    )


@app.route("/view/<key>/<int:index>")
def view_image(key, index):
    path = get_folder_path(key)
    images = list_images(path)
    if not images:
        abort(404, description="该文件夹下没有图片")
    index = max(0, min(index, len(images) - 1))
    prev_index = index - 1 if index > 0 else None
    next_index = index + 1 if index < len(images) - 1 else None
    return render_template(
        "view.html",
        key=key,
        filename=images[index].name,
        index=index,
        total=len(images),
        prev_index=prev_index,
        next_index=next_index,
    )


@app.route("/media/<key>/<path:filename>")
def media(key, filename):
    path = get_folder_path(key)
    return send_from_directory(path, filename)


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5000"))
    app.run(host=host, port=port)
