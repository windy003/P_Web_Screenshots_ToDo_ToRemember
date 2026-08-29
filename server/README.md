# 服务端(Flask)

在 Win11 上运行,把三个本地文件夹通过网页和 API 暴露出去。

## 配置

复制 `.env.example` 为 `.env`,把三个 key 的值改成你自己的文件夹路径(某一项留空/删除表示不启用该分类):

```
Small_To_Remember=D:\Pictures\Small_To_Remember
Large_To_Remember=D:\Pictures\Large_To_Remember
ToDo=D:\Pictures\ToDo
```

## 运行

```bat
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python app.py
```

默认监听 `0.0.0.0:5000`(局域网内其它设备,比如手机,也能通过电脑的局域网 IP 访问)。

## 接口

- `GET /` 网页首页,显示三个文件夹卡片和各自的图片数量。
- `GET /api/folders` 返回三个文件夹的 `{key, count, browse_url, configured}` 列表。
- `GET /api/folders/<key>/count` 返回单个文件夹的图片数量,`key` 是 `Small_To_Remember` / `Large_To_Remember` / `ToDo` 之一。
- `GET /browse/<key>` 图片网格浏览页,按图片修改时间从旧到新排序。
- `GET /view/<key>/<index>` 单张图片查看页,支持"上一张/下一张"(也支持键盘左右方向键)。
- `GET /media/<key>/<filename>` 图片原始文件。

PC 托盘客户端和 Android 小部件都是通过 `/api/folders/<key>/count` 拿到数量和浏览地址的。
