"""
后台常驻服务(需要一直运行,Ctrl+C 停止),负责 server/Web_Server/.env 里
配置的文件夹(Small_To_Remember / Large_To_Remember)的"到期 -> 匀速放出"流程。
ToDo 文件夹不走这套流程(见 IMMEDIATE_FOLDER_KEYS),一有图片就由
Web_Server/app.py 立即搬进 releasing 展示,不等 3 天:

1. 每天 RELEASE_START_HOUR 点(默认 8:00)扫描一次该文件夹,把已经放置满
   DAYS_THRESHOLD 天(默认 3 天)的图片挪进 Reached_3_Days 子文件夹。
2. 用 (Reached_3_Days 里的图片数) / (RELEASE_WINDOW_HOURS 小时 * 60) 算出
   平均每分钟要放几张,在 RELEASE_START_HOUR 到
   RELEASE_START_HOUR + RELEASE_WINDOW_HOURS 之间(默认 8:00-16:00)把这些
   图片匀速地从 Reached_3_Days 挪到 releasing 子文件夹。

Web_Server 的网页/API、以及 Android 小部件看到的图片数量和列表,都是
releasing 子文件夹里的内容 —— 也就是"已经到期、并且已经轮到今天放出"的图片。
Android 端点"3天后",会把图片从 releasing 挪回最上层文件夹并重置时间,回到
流程的最开始。

用法:
    python move_to_3_days_later.py

放出进度按文件夹分别保存在同目录下的 release_state.json 里,脚本重启后能
从中断的地方继续,不会重复放出或漏放。
"""
import json
import os
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
ENV_PATH = SCRIPT_DIR.parent / "Web_Server" / ".env"
STATE_PATH = SCRIPT_DIR / "release_state.json"

# 固定的三个文件夹 key,跟 Web_Server/app.py 保持一致。
FOLDER_KEYS = ["Small_To_Remember", "Large_To_Remember", "ToDo"]

# ToDo 不走"放满 3 天才放出"的流程,这里完全跳过,由 Web_Server/app.py
# 在每次访问时把 ToDo 根目录下的新图片直接搬进 releasing。
IMMEDIATE_FOLDER_KEYS = {"ToDo"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
REACHED_DIR_NAME = "Reached_3_Days"
RELEASING_DIR_NAME = "releasing"

# 下面几个都可以在 .env 里加同名的一行来覆盖默认值。
DEFAULT_CHECK_INTERVAL_SECONDS = 60
DEFAULT_DAYS_THRESHOLD = 3
DEFAULT_RELEASE_START_HOUR = 8      # 每天几点开始扫描 + 放出
DEFAULT_RELEASE_WINDOW_HOURS = 8    # 放出窗口长度(小时),默认 8:00-16:00


def log(message: str) -> None:
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")


def load_folders():
    folders = {}
    for key in FOLDER_KEYS:
        raw = os.environ.get(key)
        if raw:
            folders[key] = Path(raw).expanduser()
    return folders


def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def list_images(path: Path):
    if not path.exists():
        return []
    items = [
        entry
        for entry in path.iterdir()
        if entry.is_file() and entry.suffix.lower() in IMAGE_EXTENSIONS
    ]
    items.sort(key=lambda p: p.stat().st_mtime)  # 旧 -> 新
    return items


def move_file(src: Path, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    if dest.exists():
        stem, suffix = dest.stem, dest.suffix
        dest = dest_dir / f"{stem}_{int(time.time())}{suffix}"
    shutil.move(str(src), str(dest))
    return dest


def scan_reached(key: str, base_path: Path, seconds_threshold: float) -> int:
    """把 base_path 下放满 seconds_threshold 的图片挪到 Reached_3_Days 子文件夹。"""
    if not base_path.exists():
        log(f"[{key}] 文件夹不存在,跳过: {base_path}")
        return 0

    reached_path = base_path / REACHED_DIR_NAME
    now = time.time()
    moved = 0
    for entry in list(base_path.iterdir()):
        if not entry.is_file() or entry.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        age_seconds = now - entry.stat().st_mtime
        if age_seconds < seconds_threshold:
            continue
        move_file(entry, reached_path)
        moved += 1
        log(f"[{key}] 已到期({age_seconds / 86400:.1f} 天),移动: {entry.name} -> {REACHED_DIR_NAME}/")
    return moved


def release_batch(key: str, base_path: Path, count: int) -> int:
    """从 Reached_3_Days 里挑最老的 count 张图片放到 releasing 文件夹。"""
    if count <= 0:
        return 0
    reached_path = base_path / REACHED_DIR_NAME
    releasing_path = base_path / RELEASING_DIR_NAME
    to_release = list_images(reached_path)[:count]
    for entry in to_release:
        move_file(entry, releasing_path)
        log(f"[{key}] 定时放出: {entry.name} -> {RELEASING_DIR_NAME}/")
    return len(to_release)


def run_tick(
    state: dict,
    release_start_hour: float,
    release_window_hours: float,
    seconds_threshold: float,
    now_dt: datetime = None,
) -> None:
    """跑一轮检查:该扫描的扫描,该放出的放出。会原地修改并保存 state。"""
    now_dt = now_dt or datetime.now()
    today_str = now_dt.strftime("%Y-%m-%d")

    start_hour_int = int(release_start_hour)
    start_minute = int(round((release_start_hour - start_hour_int) * 60))
    window_start = now_dt.replace(hour=start_hour_int, minute=start_minute, second=0, microsecond=0)
    window_minutes = release_window_hours * 60

    folders = load_folders()
    for key, base_path in folders.items():
        if key in IMMEDIATE_FOLDER_KEYS:
            continue  # 交给 Web_Server/app.py 立即放出,这里不处理

        key_state = state.get(key, {})

        # 到了今天的开始时间、且今天还没扫描过 -> 做一次"到 3 天就挪进 Reached_3_Days",
        # 并把 Reached_3_Days 当前的图片总数定为今天的放出计划基数。
        if now_dt >= window_start and key_state.get("date") != today_str:
            scan_reached(key, base_path, seconds_threshold)
            total = len(list_images(base_path / REACHED_DIR_NAME))
            key_state = {"date": today_str, "total": total, "released": 0}
            state[key] = key_state
            per_minute = total / window_minutes if window_minutes else 0
            log(
                f"[{key}] 今日 {today_str} 放出计划:Reached_3_Days 共 {total} 张,"
                f"{release_window_hours:.0f} 小时内匀速放出(约每分钟 {per_minute:.2f} 张)。"
            )

        if key_state.get("date") != today_str:
            continue  # 今天的开始时间还没到(比如现在是凌晨),先不放出

        total = key_state.get("total", 0)
        released = key_state.get("released", 0)
        if total <= 0 or released >= total:
            continue

        elapsed_minutes = (now_dt - window_start).total_seconds() / 60
        elapsed_minutes = max(0.0, min(elapsed_minutes, window_minutes))
        target = round(total * elapsed_minutes / window_minutes) if window_minutes else total
        target = max(0, min(target, total))

        if target > released:
            newly_released = release_batch(key, base_path, target - released)
            key_state["released"] = released + newly_released
            state[key] = key_state

    save_state(state)


def main():
    load_dotenv(dotenv_path=ENV_PATH)
    interval_seconds = float(os.environ.get("CHECK_INTERVAL_SECONDS", str(DEFAULT_CHECK_INTERVAL_SECONDS)))

    state = load_state()
    log(
        f"服务启动,每 {interval_seconds:.0f} 秒检查一次;"
        f"每天到点扫描到期图片并在放出窗口内匀速放出。.env: {ENV_PATH}"
    )

    try:
        while True:
            load_dotenv(dotenv_path=ENV_PATH, override=True)
            days_threshold = float(os.environ.get("DAYS_THRESHOLD", str(DEFAULT_DAYS_THRESHOLD)))
            release_start_hour = float(os.environ.get("RELEASE_START_HOUR", str(DEFAULT_RELEASE_START_HOUR)))
            release_window_hours = float(
                os.environ.get("RELEASE_WINDOW_HOURS", str(DEFAULT_RELEASE_WINDOW_HOURS))
            )
            run_tick(
                state,
                release_start_hour,
                release_window_hours,
                days_threshold * 24 * 60 * 60,
            )
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        log("收到停止信号,服务退出。")


if __name__ == "__main__":
    main()
