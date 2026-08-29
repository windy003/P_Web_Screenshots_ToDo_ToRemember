# P_Web_Screenshots_ToDo_ToRemember

在 Win11 上跑一个 Flask 服务,把三个本地图片文件夹(`Small_To_Remember` / `Large_To_Remember` / `ToDo`,路径在 `.env` 里自己配置)通过网页 + API 暴露出去;PC 端在系统托盘为每个文件夹建一个蓝底白字的方块图标显示图片数量,点击直接浏览;Android 端做成桌面小部件,同样显示数量,点击浏览。

```
server/        Flask 服务端(图片浏览网页 + 统计 API)
client/pc/     Win11 系统托盘客户端(Python + pystray)
client/android/ Android 桌面小部件(Kotlin)
```

## 快速开始

1. **服务端**:见 `server/README.md`。先复制 `.env.example` 为 `.env` 填好三个文件夹路径,再 `python app.py` 启动。
2. **PC 托盘客户端**:见 `client/pc/README.md`。启动后右键托盘图标 → "新建图标",填名称/URL(填服务端的 `/api/folders/<key>/count` 地址)。
3. **Android 小部件**:见 `client/android/README.md`。用 Android Studio 打开、编译安装后,在桌面长按添加小部件,同样填名称/URL。

图片浏览页面(网页版和 Android WebView 复用同一套)按图片修改时间从旧到新排序,支持点击"上一张/下一张"(网页版还支持键盘左右方向键)。

## 已验证 / 未验证

- 服务端 API 与网页(计数、画廊、单图查看、上一张/下一张、图片文件访问)已经在本机跑通测试。
- PC 托盘客户端的图标生成、配置持久化逻辑已单独测试通过;完整的托盘 UI 交互建议你实际启动一遍确认(不同 Win11 环境下托盘行为可能略有差异)。
- Android 工程是按标准结构手写的,本机没有 Android SDK,**没有实际编译验证过**,需要你用 Android Studio 打开后编译确认。
