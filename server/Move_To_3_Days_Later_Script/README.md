# 3天到期移动脚本

后台常驻服务,每隔一段时间(默认 60 秒)扫描一次 `server/Web_Server/.env`
里配置的三个文件夹路径,把里面放置满 3 天的图片挪到该文件夹下的
`Reached_3_Days` 子文件夹。Web_Server 的网页/API 和 Android 小部件看到的
图片数量、列表,都是 `Reached_3_Days` 子文件夹的内容。

## 运行

```bat
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python move_to_3_days_later.py
```

启动后会一直挂在前台运行,每 60 秒检查一次,`Ctrl+C` 停止。想在后台/开机自启,
可以用 `pythonw.exe` 替代 `python.exe` 免去控制台窗口,或者配合 Windows
"任务计划程序"设置"登录时启动"来常驻。重复扫描是安全的:已经在
`Reached_3_Days` 里的图片不会被重复处理。

检查间隔可以在 `.env` 里加一行 `CHECK_INTERVAL_SECONDS=60` 覆盖默认值。

## 判断到期的依据

按文件的修改时间(mtime)计算 —— 图片被放进文件夹、或者在 Android App 里点了
"3天后"重新放回上层文件夹时,修改时间都会被重置,从那一刻起满 3 天才会被这个
脚本挪进 `Reached_3_Days`。

默认阈值是 3 天,可以在 `.env` 里加一行 `DAYS_THRESHOLD=3` 来覆盖(比如临时改成
`0.01` 方便测试)。

## 目录结构示意

```
Small_To_Remember/              <- .env 里配置的原始文件夹
├── 新截图.png                  <- 刚放进来,不满 3 天,暂时看不到
└── Reached_3_Days/
    └── 旧截图.png               <- 满 3 天了,网页/App 会显示这张
```

"3天后"按钮(在 Android App 全屏浏览的悬浮操作栏里)的效果正好相反:把图片从
`Reached_3_Days` 挪回上层文件夹,并重置修改时间,相当于"再拖延 3 天",这个脚本
下次运行时会重新计时,3 天后才会又出现在 `Reached_3_Days` 里。
