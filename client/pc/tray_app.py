"""
Win11 系统托盘客户端。

- 启动后在系统托盘显示一个主图标,右键菜单里有"新建图标"。
- "新建图标"会弹出一个小窗口,输入:
    名称  - 鼠标悬停在新图标上显示的名字
    URL   - 服务端某个文件夹的 API 地址,例如 http://127.0.0.1:5000/api/folders/ToDo/count
- 新图标固定是蓝底白字的方块(不支持自定义颜色),保证数字清楚易读。
- 提交后会新建一个托盘图标,定时轮询该 URL 获取图片数量并显示在悬停提示里,
  左键/默认操作会用浏览器打开对应文件夹的图片浏览页面。
- 右键某个已创建的图标,可以"编辑此图标(E)"修改名称/URL,也可以"删除该图标(D)"、
  "浏览图片(O)"、"立即刷新(S)"、"重启(R,重启整个程序)"。菜单打开时按对应字母键就能触发。
- 右键主图标还有:刷新(&S,重新请求所有图标的数量)、重启(&R,重新拉起一个新进程后自己退出)、
  退出(&X,关闭所有图标并退出程序)。菜单打开时按对应字母键就能触发。
- 所有已创建的图标会保存到 config.json,下次启动自动恢复。
"""

import json
import subprocess
import sys
import threading
import tkinter as tk
import uuid
import webbrowser
from pathlib import Path
from tkinter import messagebox

import pystray
import requests
from PIL import Image, ImageDraw, ImageFont

# 这个工具只请求本机/局域网内的服务端,trust_env=False 让它彻底不理会系统/用户环境变量里
# 配置的 HTTP_PROXY / HTTPS_PROXY / ALL_PROXY,避免这些代理把本地请求绕道劫持导致请求失败。
SESSION = requests.Session()
SESSION.trust_env = False

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"
POLL_INTERVAL_SECONDS = 30
ICON_BG_COLOR = (66, 133, 244)  # 固定蓝色背景
ICON_TEXT_COLOR = (255, 255, 255)  # 固定白色数字
# 示例地址,仅供参考:把 IP、端口换成你自己服务端的实际值,
# key 换成 Small_To_Remember / Large_To_Remember / ToDo 之一。
EXAMPLE_URL = "http://192.168.2.56:5000/api/folders/ToDo/count"


def load_config():
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def save_config(items):
    CONFIG_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def make_icon_image(text):
    # 用更大的画布渲染,缩小到实际托盘尺寸时数字仍然清晰、显得更粗更大。
    # 256 是 Windows ICO 格式支持的最大尺寸,再大也没有意义。
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = 2
    # 方块尽量占满整个图标画布,固定蓝底红字,保证数字始终清楚易读。
    draw.rounded_rectangle(
        (margin, margin, size - margin, size - margin),
        radius=32,
        fill=ICON_BG_COLOR,
    )

    text = str(text)
    font = None
    font_size = 184 if len(text) <= 2 else 128
    for candidate in ("arialbd.ttf", "seguisb.ttf", "arial.ttf"):
        try:
            font = ImageFont.truetype(candidate, font_size)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        ((size - w) / 2 - bbox[0], (size - h) / 2 - bbox[1]),
        text,
        fill=ICON_TEXT_COLOR,
        font=font,
    )
    return img


class FolderIcon:
    """代表用户新建的一个"文件夹"托盘图标。"""

    def __init__(self, app, config_id, name, url):
        self.app = app
        self.config_id = config_id
        self.name = name
        self.url = url
        self.browse_url = None
        self._stop_event = threading.Event()

        self.icon = pystray.Icon(
            f"folder-{id(self)}",
            make_icon_image("?"),
            f"{self.name}: 加载中...",
            menu=pystray.Menu(
                pystray.MenuItem("浏览图片(&O)", self._on_open, default=True),
                pystray.MenuItem("编辑此图标(&E)", self._on_edit),
                pystray.MenuItem("立即刷新(&S)", self._on_refresh),
                pystray.MenuItem("删除该图标(&D)", self._on_remove),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("新建图标(&N)", self._on_new_icon),
                pystray.MenuItem("重启(&R)", self._on_restart),
            ),
        )
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)

    def start(self):
        threading.Thread(target=self.icon.run, daemon=True).start()
        self._poll_thread.start()

    def stop(self):
        self._stop_event.set()
        try:
            self.icon.visible = False
            self.icon.stop()
        except Exception:
            pass

    def _poll_loop(self):
        while not self._stop_event.is_set():
            self._fetch_once()
            self._stop_event.wait(POLL_INTERVAL_SECONDS)

    def _fetch_once(self):
        try:
            resp = SESSION.get(self.url, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            count = data.get("count", "?")
            self.browse_url = data.get("browse_url")
            self.icon.icon = make_icon_image(count)
            self.icon.title = f"{self.name}: {count} 张图片"[:127]
        except Exception:
            self.icon.icon = make_icon_image("!")
            self.icon.title = f"{self.name}: 获取失败,请检查服务端和 URL"[:127]

    def _on_refresh(self, icon=None, item=None):
        threading.Thread(target=self._fetch_once, daemon=True).start()

    def _on_open(self, icon=None, item=None):
        target = self.browse_url or self.url
        webbrowser.open(target)

    def _on_edit(self, icon=None, item=None):
        self.app.request_edit(self)

    def _on_new_icon(self, icon=None, item=None):
        self.app._on_new_icon_clicked(icon, item)

    def _on_restart(self, icon=None, item=None):
        # 重启整个程序(所有图标一起重开),和主图标的"重启"是同一套逻辑。
        self.app._on_restart_clicked(icon, item)

    def _on_remove(self, icon=None, item=None):
        self.app.remove_folder_icon(self)

    def to_config(self):
        return {"id": self.config_id, "name": self.name, "url": self.url}


class TrayApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()  # 只用它来安全地在主线程弹窗,不显示主窗口

        self.config_items = load_config()
        self.folder_icons = []

        self.main_icon = pystray.Icon(
            "watch_folders_hub",
            make_icon_image("★"),
            "图片文件夹监视器",
            menu=pystray.Menu(
                pystray.MenuItem("新建图标", self._on_new_icon_clicked),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("刷新(&S)", self._on_refresh_all_clicked),
                pystray.MenuItem("重启(&R)", self._on_restart_clicked),
                pystray.MenuItem("退出(&X)", self._on_quit_clicked),
            ),
        )

    # ---- 新建 / 编辑图标对话框 ----

    def _on_new_icon_clicked(self, icon=None, item=None):
        # pystray 的菜单回调运行在后台线程,tkinter 窗口必须在主线程创建,
        # 用 root.after 把弹窗操作调度回 tkinter 的主循环线程。
        self.root.after(
            0,
            lambda: self._show_icon_dialog(
                "新建图标",
                "",
                EXAMPLE_URL,
                lambda name, url: self.add_folder_icon(name, url, persist=True),
            ),
        )

    def request_edit(self, fi):
        self.root.after(
            0,
            lambda: self._show_icon_dialog(
                "编辑图标",
                fi.name,
                fi.url,
                lambda name, url: self.edit_folder_icon(fi, name, url),
            ),
        )

    def _show_icon_dialog(self, title, initial_name, initial_url, on_submit):
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.resizable(False, False)
        dialog.attributes("-topmost", True)

        name_var = tk.StringVar(value=initial_name)
        url_var = tk.StringVar(value=initial_url)

        rows = [
            ("名称(悬停显示):", name_var),
            ("URL(文件夹的 API 地址):", url_var),
        ]
        url_entry = None
        for i, (label_text, var) in enumerate(rows):
            tk.Label(dialog, text=label_text, anchor="w").grid(
                row=i, column=0, sticky="w", padx=10, pady=(10 if i == 0 else 4, 4)
            )
            entry = tk.Entry(dialog, textvariable=var, width=42)
            entry.grid(row=i, column=1, padx=(0, 10), pady=(10 if i == 0 else 4, 4))
            if var is url_var:
                url_entry = entry

        # URL 框预填了内容(新建时是示例地址,编辑时是当前地址),默认全选中,方便直接输入覆盖。
        if url_entry is not None:
            url_entry.icursor("end")
            url_entry.select_range(0, "end")

        button_row = len(rows)
        btn_frame = tk.Frame(dialog)
        btn_frame.grid(row=button_row, column=0, columnspan=2, pady=12)

        def submit():
            name = name_var.get().strip()
            url = url_var.get().strip()
            if not name or not url:
                messagebox.showerror("错误", "名称和 URL 不能为空", parent=dialog)
                return
            on_submit(name, url)
            dialog.destroy()

        def cancel():
            dialog.destroy()

        tk.Button(btn_frame, text="确定", width=10, command=submit).pack(side="left", padx=6)
        tk.Button(btn_frame, text="取消", width=10, command=cancel).pack(side="left", padx=6)

        dialog.grab_set()
        dialog.focus_set()

    # ---- 图标管理 ----

    def add_folder_icon(self, name, url, persist, config_id=None):
        if config_id is None:
            config_id = str(uuid.uuid4())
        fi = FolderIcon(self, config_id, name, url)
        self.folder_icons.append(fi)
        fi.start()
        if persist:
            self.config_items.append(fi.to_config())
            save_config(self.config_items)
        return fi

    def edit_folder_icon(self, fi, name, url):
        fi.name = name
        fi.url = url
        fi.browse_url = None
        fi.icon.title = f"{name}: 加载中..."[:127]
        for c in self.config_items:
            if c.get("id") == fi.config_id:
                c["name"] = name
                c["url"] = url
                break
        else:
            self.config_items.append(fi.to_config())
        save_config(self.config_items)
        fi._on_refresh()

    def remove_folder_icon(self, fi):
        if fi in self.folder_icons:
            self.folder_icons.remove(fi)
        fi.stop()
        self.config_items = [c for c in self.config_items if c.get("id") != fi.config_id]
        save_config(self.config_items)

    # ---- 生命周期 ----

    def _on_refresh_all_clicked(self, icon=None, item=None):
        for fi in list(self.folder_icons):
            fi._on_refresh()

    def _on_restart_clicked(self, icon=None, item=None):
        self._launch_new_instance()
        self._on_quit_clicked(icon, item)

    def _launch_new_instance(self):
        # 开发模式下 sys.executable 是 python.exe,脚本路径在 sys.argv 里,要一起带上;
        # 打包成 exe(pyinstaller --onefile)后 sys.executable 就是那个 exe 本身,argv[0] 与它重复,要去掉。
        if getattr(sys, "frozen", False):
            cmd = [sys.executable] + sys.argv[1:]
        else:
            cmd = [sys.executable] + sys.argv
        subprocess.Popen(cmd, cwd=str(Path(__file__).resolve().parent))

    def _on_quit_clicked(self, icon=None, item=None):
        for fi in list(self.folder_icons):
            fi.stop()
        try:
            self.main_icon.visible = False
            self.main_icon.stop()
        except Exception:
            pass
        self.root.after(0, self.root.quit)

    def run(self):
        needs_save = False
        for item in self.config_items:
            if "id" not in item:
                item["id"] = str(uuid.uuid4())
                needs_save = True
            self.add_folder_icon(
                item.get("name", "未命名"),
                item.get("url", ""),
                persist=False,
                config_id=item["id"],
            )
        if needs_save:
            save_config(self.config_items)
        threading.Thread(target=self.main_icon.run, daemon=True).start()
        self.root.mainloop()


if __name__ == "__main__":
    TrayApp().run()
