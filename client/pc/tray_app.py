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
- 右键某个图标还有"建立HTTP API服务器(H)":在本机开一个 HTTP 反向代理,监听局域网,
  把请求转发到该图标 URL 所在的远程主机(通常是 Tailscale 地址)。这样手机等设备
  不需要安装 Tailscale,只要和这台电脑在同一个局域网,直接用这台电脑的局域网 IP
  加代理端口就能访问远程服务。同一个远程主机只需建立一次,配置会保存到 config.json,
  下次启动自动恢复。代理建立后这个菜单项会变成"编辑HTTP API服务器(H)",点击可以
  查看/修改端口,或者停止该代理。
- 右键主图标还有:刷新(&S,重新请求所有图标的数量)、重启(&R,重新拉起一个新进程后自己退出)、
  退出(&X,关闭所有图标并退出程序)。菜单打开时按对应字母键就能触发。
- 所有已创建的图标会保存到 config.json,下次启动自动恢复。
"""

import json
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tkinter import messagebox
from urllib.parse import urlsplit

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
    data = {}
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    if isinstance(data, list):
        # 旧版本 config.json 本身就是图标数组,自动迁移成新结构(不丢已有图标)。
        data = {"icons": data, "proxies": []}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("icons", [])
    data.setdefault("proxies", [])
    return data


def save_config(config):
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def get_lan_ip():
    """获取本机在局域网里的 IP,用来提示手机应该访问哪个地址。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # 不需要真的能连通,只是借此拿到出口网卡的局域网 IP
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


# 转发"请求"给远程服务端时,这些是逐跳头,以及 Host/Content-Length 需要
# 由 requests 库根据实际请求内容重新生成,不能照抄客户端发来的原始值。
_REQUEST_STRIP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host", "content-length",
}
# 把远程"响应"传回客户端时,Content-Length 由我们读到的实际字节数重新计算并单独发送,
# 不能沿用远程响应头里的 Content-Length(否则下面会重复发送这个头);
# Content-Encoding/Transfer-Encoding 也要去掉,因为 requests 已经帮我们解压/解码好了。
_RESPONSE_STRIP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
    "content-encoding", "content-length",
}


class _ProxyRequestHandler(BaseHTTPRequestHandler):
    """把收到的请求原样转发给 target_base,再把远程响应原样传回来。"""

    target_base = ""  # 由 LocalProxyServer 在创建子类时注入
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass  # 局域网代理不需要在控制台刷屏

    def _forward(self, method):
        url = self.target_base + self.path
        headers = {
            k: v for k, v in self.headers.items()
            if k.lower() not in _REQUEST_STRIP_HEADERS
        }
        length = self.headers.get("Content-Length")
        body = self.rfile.read(int(length)) if length else None

        try:
            resp = SESSION.request(
                method, url, headers=headers, data=body,
                timeout=15, allow_redirects=False,
            )
        except Exception as exc:
            message = f"代理请求失败: {exc}".encode("utf-8")
            self.send_response(502)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(message)))
            self.end_headers()
            if method != "HEAD":
                self.wfile.write(message)
            return

        content = b"" if method == "HEAD" else resp.content
        self.send_response(resp.status_code)
        for k, v in resp.headers.items():
            if k.lower() not in _RESPONSE_STRIP_HEADERS:
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        if content:
            self.wfile.write(content)
        resp.close()

    def do_GET(self):
        self._forward("GET")

    def do_HEAD(self):
        self._forward("HEAD")

    def do_POST(self):
        self._forward("POST")

    def do_PUT(self):
        self._forward("PUT")

    def do_DELETE(self):
        self._forward("DELETE")

    def do_PATCH(self):
        self._forward("PATCH")


class LocalProxyServer:
    """监听局域网某个端口,把请求转发到一个远程 base URL(比如 Tailscale 地址)。"""

    def __init__(self, target_base, port):
        self.target_base = target_base
        self.port = port
        handler_cls = type(
            "ProxyRequestHandler", (_ProxyRequestHandler,), {"target_base": target_base}
        )
        # 端口被占用时这里会抛 OSError,交给调用方处理提示。
        self._httpd = ThreadingHTTPServer(("0.0.0.0", port), handler_cls)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        try:
            self._httpd.shutdown()
            self._httpd.server_close()
        except Exception:
            pass


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
                pystray.MenuItem(
                    self._proxy_menu_text, self._on_toggle_proxy, checked=self._proxy_checked
                ),
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

    @property
    def target_base(self):
        """从图标 URL 里取出协议+主机+端口,即代理要转发到的远程地址。"""
        parts = urlsplit(self.url)
        return f"{parts.scheme}://{parts.netloc}"

    def _proxy_menu_text(self, item=None):
        proxy = self.app.proxies.get(self.target_base)
        if proxy:
            return f"编辑HTTP API服务器(&H,本机端口{proxy.port})"
        return "建立HTTP API服务器(&H)"

    def _proxy_checked(self, item=None):
        return self.target_base in self.app.proxies

    def _on_toggle_proxy(self, icon=None, item=None):
        self.app.toggle_proxy_for(self)

    def to_config(self):
        return {"id": self.config_id, "name": self.name, "url": self.url}


class TrayApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()  # 只用它来安全地在主线程弹窗,不显示主窗口

        self.config = load_config()
        self.folder_icons = []
        self.proxies = {}  # target_base -> LocalProxyServer

        self.main_icon = pystray.Icon(
            "watch_folders_hub",
            make_icon_image("★"),
            "图片文件夹监视器",
            menu=pystray.Menu(
                pystray.MenuItem("新建图标(&N)", self._on_new_icon_clicked),
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
        name_entry = None
        url_entry = None
        for i, (label_text, var) in enumerate(rows):
            tk.Label(dialog, text=label_text, anchor="w").grid(
                row=i, column=0, sticky="w", padx=10, pady=(10 if i == 0 else 4, 4)
            )
            entry = tk.Entry(dialog, textvariable=var, width=42)
            entry.grid(row=i, column=1, padx=(0, 10), pady=(10 if i == 0 else 4, 4))
            if var is name_var:
                name_entry = entry
            elif var is url_var:
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

        # 从托盘菜单弹出的窗口默认不是系统前台窗口,-topmost 只保证置顶、不保证拿到键盘焦点,
        # 所以要主动抢焦点;稍微延迟一下再抢,避免窗口还没被系统真正建好/换到前台就抢焦点失败。
        # 抢到焦点后再把光标落在第一个该填的框上,这样打开就能直接打字,Tab 键会按创建顺序
        # 在"名称 -> URL -> 确定 -> 取消"之间跳转。
        def _activate():
            dialog.lift()
            dialog.focus_force()
            first_entry = url_entry if initial_name else name_entry
            if first_entry is not None:
                first_entry.focus_set()

        dialog.after(50, _activate)

    # ---- 图标管理 ----

    def add_folder_icon(self, name, url, persist, config_id=None):
        if config_id is None:
            config_id = str(uuid.uuid4())
        fi = FolderIcon(self, config_id, name, url)
        self.folder_icons.append(fi)
        fi.start()
        if persist:
            self.config["icons"].append(fi.to_config())
            save_config(self.config)
        return fi

    def edit_folder_icon(self, fi, name, url):
        fi.name = name
        fi.url = url
        fi.browse_url = None
        fi.icon.title = f"{name}: 加载中..."[:127]
        for c in self.config["icons"]:
            if c.get("id") == fi.config_id:
                c["name"] = name
                c["url"] = url
                break
        else:
            self.config["icons"].append(fi.to_config())
        save_config(self.config)
        fi._on_refresh()

    def remove_folder_icon(self, fi):
        if fi in self.folder_icons:
            self.folder_icons.remove(fi)
        fi.stop()
        self.config["icons"] = [c for c in self.config["icons"] if c.get("id") != fi.config_id]
        save_config(self.config)

    # ---- HTTP API 服务器(局域网 -> Tailscale 反向代理) ----

    def toggle_proxy_for(self, fi):
        target = fi.target_base
        if target in self.proxies:
            self.root.after(0, lambda: self._show_proxy_edit_dialog(target))
            return
        existing = next(
            (e for e in self.config["proxies"] if e.get("target") == target), None
        )
        if existing and existing.get("port"):
            self._start_proxy_and_notify(target, existing["port"])
        else:
            default_port = urlsplit(target).port or 8000
            self.root.after(0, lambda: self._show_proxy_dialog(target, default_port))

    def _show_proxy_edit_dialog(self, target):
        # 代理可能在弹窗排队等待主线程期间被别处(比如另一个指向同一主机的图标)关掉了。
        proxy = self.proxies.get(target)
        if proxy is None:
            return
        current_port = proxy.port
        lan_ip = get_lan_ip()

        dialog = tk.Toplevel(self.root)
        dialog.title("HTTP API服务器设置")
        dialog.resizable(False, False)
        dialog.attributes("-topmost", True)

        tk.Label(
            dialog, text=f"转发到:\n{target}", anchor="w", justify="left"
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 4))
        tk.Label(
            dialog,
            text=f"手机可访问(局域网内):\nhttp://{lan_ip}:{current_port}/",
            anchor="w", justify="left", fg="#1a73e8",
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=10, pady=4)

        port_var = tk.StringVar(value=str(current_port))
        tk.Label(dialog, text="本机监听端口:", anchor="w").grid(
            row=2, column=0, sticky="w", padx=10, pady=4
        )
        entry = tk.Entry(dialog, textvariable=port_var, width=10)
        entry.grid(row=2, column=1, sticky="w", padx=(0, 10), pady=4)
        entry.icursor("end")
        entry.select_range(0, "end")

        btn_frame = tk.Frame(dialog)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=12)

        def save():
            text = port_var.get().strip()
            if not text.isdigit() or not (1 <= int(text) <= 65535):
                messagebox.showerror("错误", "请输入 1-65535 之间的端口号", parent=dialog)
                return
            new_port = int(text)
            if new_port == current_port:
                dialog.destroy()
                return
            self.stop_proxy(target)
            try:
                self.start_proxy(target, new_port, persist=True)
            except OSError as exc:
                # 换端口失败,把原来的端口重新起回来,避免用户彻底失去这个代理。
                try:
                    self.start_proxy(target, current_port, persist=True)
                except OSError:
                    pass
                messagebox.showerror("错误", f"无法监听端口 {new_port}:\n{exc}", parent=dialog)
                return
            dialog.destroy()
            self._notify_proxy_started(target, new_port)

        def stop_and_close():
            self.stop_proxy(target)
            dialog.destroy()

        def cancel():
            dialog.destroy()

        tk.Button(btn_frame, text="保存", width=10, command=save).pack(side="left", padx=6)
        tk.Button(btn_frame, text="停止代理", width=10, command=stop_and_close).pack(
            side="left", padx=6
        )
        tk.Button(btn_frame, text="取消", width=10, command=cancel).pack(side="left", padx=6)

        dialog.grab_set()
        dialog.focus_set()

    def _show_proxy_dialog(self, target, default_port):
        dialog = tk.Toplevel(self.root)
        dialog.title("建立HTTP API服务器")
        dialog.resizable(False, False)
        dialog.attributes("-topmost", True)

        tk.Label(
            dialog, text=f"转发到:\n{target}", anchor="w", justify="left"
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 4))

        port_var = tk.StringVar(value=str(default_port))
        tk.Label(dialog, text="本机监听端口(局域网内手机访问用):", anchor="w").grid(
            row=1, column=0, sticky="w", padx=10, pady=4
        )
        entry = tk.Entry(dialog, textvariable=port_var, width=10)
        entry.grid(row=1, column=1, sticky="w", padx=(0, 10), pady=4)
        entry.icursor("end")
        entry.select_range(0, "end")

        btn_frame = tk.Frame(dialog)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=12)

        def submit():
            text = port_var.get().strip()
            if not text.isdigit() or not (1 <= int(text) <= 65535):
                messagebox.showerror("错误", "请输入 1-65535 之间的端口号", parent=dialog)
                return
            port = int(text)
            try:
                self.start_proxy(target, port, persist=True)
            except OSError as exc:
                messagebox.showerror("错误", f"无法监听端口 {port}:\n{exc}", parent=dialog)
                return
            dialog.destroy()
            self._notify_proxy_started(target, port)

        def cancel():
            dialog.destroy()

        tk.Button(btn_frame, text="确定", width=10, command=submit).pack(side="left", padx=6)
        tk.Button(btn_frame, text="取消", width=10, command=cancel).pack(side="left", padx=6)

        dialog.grab_set()
        dialog.focus_set()

    def _start_proxy_and_notify(self, target, port):
        try:
            self.start_proxy(target, port, persist=True)
        except OSError as exc:
            self.root.after(
                0, lambda: messagebox.showerror("错误", f"无法监听端口 {port}:\n{exc}")
            )
            return
        self._notify_proxy_started(target, port)

    def _notify_proxy_started(self, target, port):
        lan_ip = get_lan_ip()
        message = (
            f"手机和这台电脑在同一局域网时,可以直接访问:\n"
            f"http://{lan_ip}:{port}/\n\n"
            f"该地址会转发到:\n{target}"
        )
        self.root.after(0, lambda: messagebox.showinfo("HTTP API 服务器已启动", message))

    def start_proxy(self, target, port, persist):
        proxy = LocalProxyServer(target, port)  # 端口被占用会在这里抛 OSError
        proxy.start()
        self.proxies[target] = proxy
        if persist:
            for e in self.config["proxies"]:
                if e.get("target") == target:
                    e["port"] = port
                    e["enabled"] = True
                    break
            else:
                self.config["proxies"].append(
                    {"target": target, "port": port, "enabled": True}
                )
            save_config(self.config)

    def stop_proxy(self, target):
        proxy = self.proxies.pop(target, None)
        if proxy:
            proxy.stop()
        for e in self.config["proxies"]:
            if e.get("target") == target:
                e["enabled"] = False
                break
        save_config(self.config)

    def _shutdown_proxies(self):
        for proxy in list(self.proxies.values()):
            proxy.stop()
        self.proxies.clear()

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
        self._shutdown_proxies()
        try:
            self.main_icon.visible = False
            self.main_icon.stop()
        except Exception:
            pass
        self.root.after(0, self.root.quit)

    def run(self):
        needs_save = False
        for item in self.config["icons"]:
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
            save_config(self.config)
        self._autostart_proxies()
        threading.Thread(target=self.main_icon.run, daemon=True).start()
        self.root.mainloop()

    def _autostart_proxies(self):
        # 重启(先起新进程再关旧进程)时旧进程可能还没释放端口,稍微重试几次再放弃。
        for entry in self.config["proxies"]:
            if not entry.get("enabled") or not entry.get("target") or not entry.get("port"):
                continue
            target, port = entry["target"], entry["port"]
            for attempt in range(5):
                try:
                    self.start_proxy(target, port, persist=False)
                    break
                except OSError:
                    time.sleep(0.3)


if __name__ == "__main__":
    TrayApp().run()
