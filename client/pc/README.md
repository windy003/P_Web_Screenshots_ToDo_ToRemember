# PC 托盘客户端(Win11)

## 运行(开发模式)

```bat
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python tray_app.py
```

启动后系统托盘会出现一个星形图标。右键它:

- **新建图标**:弹出输入框,依次填写
  - 名称:鼠标悬停在新图标上显示的文字
  - URL:服务端某个文件夹的 API 地址,例如
    `http://<服务端IP>:5000/api/folders/ToDo/count`
  - 新图标固定是蓝底白字的方块,不支持自定义颜色,保证数字清楚易读
- **刷新(S)**:立即重新请求所有图标的图片数量
- **重启(R)**:拉起一个新的程序进程,再让自己退出(相当于重启)
- **退出(X)**:关闭所有图标并退出程序

菜单展开时直接按 S / R / X 键就能触发对应操作,不用移动鼠标。

新建的每个图标会每 30 秒自动请求一次对应 URL,把返回的图片数量显示在图标数字和悬停提示上。左键(默认操作)/右键菜单里的"浏览图片(O)"会用浏览器打开该文件夹的图片浏览页面。右键菜单里还可以:

- **编辑此图标(E)**:重新弹出输入框(预填当前的名称/URL),改完点确定立即生效并保存。
- **立即刷新(S)**:马上重新请求一次数量。
- **删除该图标(D)**:从托盘移除并从配置里删掉。
- **重启(R)**:和主图标的"重启"是同一个功能——重启整个程序(所有图标一起重开)。

同样,菜单展开时按对应字母键就能触发,不用点鼠标。

所有新建的图标会保存到同目录下的 `config.json`,下次启动自动恢复,不需要重新添加。

## 打包成 exe(可选)

```bat
.venv\Scripts\pip install pyinstaller
.venv\Scripts\pyinstaller --noconsole --onefile --name WatchFoldersTray tray_app.py
```

打包完成后,exe 在 `dist\WatchFoldersTray.exe`。可以把它的快捷方式放进 Win11 的启动文件夹(`shell:startup`)实现开机自启。
