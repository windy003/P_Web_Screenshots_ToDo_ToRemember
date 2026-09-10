import os
import time
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, render_template, send_from_directory, url_for

load_dotenv()

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}

# server/Move_To_3_Days_Later_Script 里的常驻脚本负责这两步:
#   1) 每天 8:00 把放满 3 天的图片从 .env 配置的文件夹挪进 Reached_3_Days;
#   2) 8:00-16:00 之间把 Reached_3_Days 里的图片匀速挪进 releasing。
# 网页/App 浏览、计数用到的都是 releasing 子文件夹的内容。
RELEASING_DIR_NAME = "releasing"

# 固定的三个文件夹 key,对应 .env 中的配置项
FOLDER_KEYS = ["Small_To_Remember", "Large_To_Remember", "ToDo"]

# ToDo 不走"放满 3 天才放出"的流程:文件夹里一有图片就要立刻在网页/小部件里
# 看到。跟 Move_To_3_Days_Later_Script 那边保持一致(那边也会跳过这些 key)。
IMMEDIATE_FOLDER_KEYS = {"ToDo"}

# "删除"/"3天后"支持撤销:被删除的图片先挪进各自文件夹下的这个隐藏子目录
# (而不是直接从磁盘抹掉),撤销时再挪回 releasing。撤销栈最多记录这么多步,
# 超出的最老一步会被"finalize"——如果是删除操作,这时才真正把文件从磁盘删掉。
TRASH_DIR_NAME = ".trash"
UNDO_MAX_STEPS = 5
UNDO_STACK = []


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


@app.context_processor
def inject_asset_version():
    # WebView 对静态资源缓存比较激进,style.css 改了内容却不改文件名的话
    # 客户端可能还在用旧样式。这里拿文件的修改时间当版本号拼到 URL 后面,
    # 内容一变 URL 就变,强制客户端重新拉取。
    try:
        mtime = os.path.getmtime(os.path.join(app.static_folder, "style.css"))
        version = str(int(mtime))
    except OSError:
        version = "0"
    return {"asset_version": version}


def get_folder_path(key):
    if key not in FOLDER_KEYS:
        abort(404, description=f"未知的文件夹 key: {key}")
    path = FOLDERS.get(key)
    if path is None:
        abort(404, description=f"文件夹 key '{key}' 未在 .env 中配置")
    return path


def flush_immediate_folder(key, base_path: Path) -> None:
    """对 IMMEDIATE_FOLDER_KEYS 里的文件夹(目前是 ToDo):把根目录下新出现的
    图片直接搬进 releasing 子文件夹,不经过 Reached_3_Days 和放出窗口,做到
    "一放进去就能立刻看到"。"""
    if not base_path.exists():
        return
    releasing_path = base_path / RELEASING_DIR_NAME
    for entry in list_images(base_path):
        releasing_path.mkdir(parents=True, exist_ok=True)
        dest = releasing_path / entry.name
        if dest.exists():
            stem, suffix = dest.stem, dest.suffix
            dest = releasing_path / f"{stem}_{int(time.time())}{suffix}"
        entry.rename(dest)


def get_releasing_path(key):
    """浏览/展示用的目录:每天匀速放出的图片会被移动脚本放进这个子文件夹。"""
    base_path = get_folder_path(key)
    if key in IMMEDIATE_FOLDER_KEYS:
        flush_immediate_folder(key, base_path)
    return base_path / RELEASING_DIR_NAME


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
        count = len(list_images(get_releasing_path(key))) if configured else 0
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
        count = len(list_images(get_releasing_path(key))) if configured else 0
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
    count = len(list_images(get_releasing_path(key)))
    return jsonify({
        "key": key,
        "name": key,
        "count": count,
        "browse_url": url_for("browse", key=key, _external=True),
    })


@app.route("/browse/<key>")
def browse(key):
    path = get_releasing_path(key)
    images = list_images(path)
    return render_template(
        "gallery.html",
        key=key,
        images=[img.name for img in images],
        count=len(images),
    )


@app.route("/view/<key>/<int:index>")
def view_image(key, index):
    path = get_releasing_path(key)
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
        show_postpone=key not in IMMEDIATE_FOLDER_KEYS,
    )


@app.route("/media/<key>/<path:filename>")
def media(key, filename):
    path = get_releasing_path(key)
    return send_from_directory(path, filename)


def _is_plain_filename(filename: str) -> bool:
    """只允许普通文件名,不允许路径分隔符/上跳,防止越权访问其它目录。"""
    return filename not in ("", ".", "..") and "/" not in filename and "\\" not in filename


def _unique_name(dir_path: Path, filename: str) -> str:
    """如果 dir_path 下已经有同名文件,拼上时间戳避免覆盖。"""
    if not (dir_path / filename).exists():
        return filename
    stem, suffix = Path(filename).stem, Path(filename).suffix
    return f"{stem}_{int(time.time())}{suffix}"


def _finalize_undo_entry(entry: dict) -> None:
    """一步操作被挤出撤销栈(超过 UNDO_MAX_STEPS)后彻底定型:
    删除操作这时才真正从磁盘上抹掉暂存的文件;3天后操作本来就已经是
    最终状态,不用处理。"""
    if entry["action"] == "delete":
        base_path = get_folder_path(entry["key"])
        trash_file = base_path / TRASH_DIR_NAME / entry["trash_name"]
        if trash_file.is_file():
            trash_file.unlink()


def _push_undo(entry: dict) -> None:
    UNDO_STACK.append(entry)
    while len(UNDO_STACK) > UNDO_MAX_STEPS:
        _finalize_undo_entry(UNDO_STACK.pop(0))


@app.route("/api/postpone/<key>/<path:filename>", methods=["POST"])
def postpone(key, filename):
    """"3天后"按钮:把图片从 releasing 挪回最上层文件夹,重置修改时间,
    回到流程最开始 —— 等再放满 3 天、且轮到当天的放出窗口,才会又出现在 releasing 里。"""
    if not _is_plain_filename(filename):
        abort(400, description="非法文件名")
    if key in IMMEDIATE_FOLDER_KEYS:
        abort(400, description=f"'{key}' 不使用 3 天后机制,无法推迟")

    releasing_path = get_releasing_path(key)
    base_path = get_folder_path(key)

    src = releasing_path / filename
    if not src.is_file():
        abort(404, description="图片不存在或已被处理")

    original_mtime = src.stat().st_mtime

    base_path.mkdir(parents=True, exist_ok=True)
    dest_name = _unique_name(base_path, filename)
    dest = base_path / dest_name

    src.rename(dest)
    now = time.time()
    os.utime(dest, (now, now))  # 重置修改时间,让 3 天计时重新开始

    _push_undo({
        "action": "postpone",
        "key": key,
        "filename": filename,
        "postponed_name": dest_name,
        "mtime": original_mtime,
    })

    return jsonify({"ok": True, "undo_count": len(UNDO_STACK)})


@app.route("/api/delete/<key>/<path:filename>", methods=["POST"])
def delete_image(key, filename):
    """删除按钮:把图片挪进 .trash 暂存(而不是立刻从磁盘抹掉),这样撤销栈里
    还留着这一步时可以恢复;真正的永久删除发生在这一步被挤出撤销栈的时候。"""
    if not _is_plain_filename(filename):
        abort(400, description="非法文件名")

    releasing_path = get_releasing_path(key)
    target = releasing_path / filename
    if not target.is_file():
        abort(404, description="图片不存在或已被处理")

    base_path = get_folder_path(key)
    trash_dir = base_path / TRASH_DIR_NAME
    trash_dir.mkdir(parents=True, exist_ok=True)

    original_mtime = target.stat().st_mtime
    trash_name = _unique_name(trash_dir, filename)
    target.rename(trash_dir / trash_name)

    _push_undo({
        "action": "delete",
        "key": key,
        "filename": filename,
        "trash_name": trash_name,
        "mtime": original_mtime,
    })

    return jsonify({"ok": True, "undo_count": len(UNDO_STACK)})


@app.route("/api/undo/status")
def undo_status():
    return jsonify({"count": len(UNDO_STACK)})


@app.route("/api/undo", methods=["POST"])
def undo():
    """撤销栈顶的一步操作(删除或3天后),把图片挪回 releasing。"""
    if not UNDO_STACK:
        abort(400, description="没有可撤销的操作")

    entry = UNDO_STACK.pop()
    key = entry["key"]
    base_path = get_folder_path(key)
    releasing_path = get_releasing_path(key)
    releasing_path.mkdir(parents=True, exist_ok=True)

    if entry["action"] == "delete":
        src = base_path / TRASH_DIR_NAME / entry["trash_name"]
    else:  # postpone
        src = base_path / entry["postponed_name"]

    if not src.is_file():
        abort(404, description="要撤销的图片已不存在,可能已被其它流程处理")

    dest_name = _unique_name(releasing_path, entry["filename"])
    dest = releasing_path / dest_name
    src.rename(dest)
    os.utime(dest, (entry["mtime"], entry["mtime"]))

    # 撤销后直接跳到这张图在画廊里现在的位置,而不是退回到网格页。
    images = list_images(releasing_path)
    index = next((i for i, img in enumerate(images) if img.name == dest_name), 0)

    return jsonify({
        "ok": True,
        "action": entry["action"],
        "key": key,
        "filename": dest_name,
        "index": index,
        "remaining": len(UNDO_STACK),
    })


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5000"))
    app.run(host=host, port=port)
