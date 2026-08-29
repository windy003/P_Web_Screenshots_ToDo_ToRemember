# Android 小部件客户端

一个只提供"图片数量小部件"的 Android App。小部件显示某个文件夹当前的图片数量,点击后用内置 WebView 打开服务端的图片浏览页面(已经支持从旧到新排序、点击上一张/下一张)。

## 如何添加小部件

1. 在手机上安装这个 App。
2. 长按桌面空白处 → 选择"小部件" → 找到"图片文件夹小部件" → 拖到桌面。
3. 系统会弹出配置界面,依次填写:
   - **名称**:小部件上显示的名字
   - **URL**:服务端某个文件夹的 API 地址,例如
     `http://<服务端IP>:5000/api/folders/ToDo/count`
   - 点"添加"完成。
4. 小部件会显示该文件夹当前的图片数量,并每 30 分钟自动刷新一次(Android 系统对小部件自动刷新有最短间隔限制)。点击小部件可以打开图片浏览页面。

如果要添加多个文件夹,重复步骤 2-3,拖多个小部件到桌面即可,每个小部件独立配置。

## 用 Android Studio 打开 / 编译

1. 用 Android Studio 打开 `client/android` 目录。
2. 首次打开时 Android Studio 会提示同步 Gradle、下载/生成 Gradle Wrapper(本仓库没有附带 `gradle-wrapper.jar` 二进制文件,Android Studio 首次同步时会自动补全)。
3. 等 Gradle Sync 完成后,选择 `app` 模块运行到真机或模拟器。

> 注意:这部分代码是按 Android 标准工程结构手写的(minSdk 24 / targetSdk 34 / Kotlin),但没有在真实 Android 环境里编译验证过——本机没有 Android SDK/Gradle 环境。如果编译报错,大概率是 Gradle/AGP/Kotlin 版本不匹配,把 `build.gradle.kts` 里的版本号换成你 Android Studio 当前默认的版本即可。

## 目录说明

- `app/src/main/java/.../ImageCountWidgetProvider.kt`:小部件本体,负责请求 API、更新界面、设置点击跳转。
- `app/src/main/java/.../WidgetConfigureActivity.kt`:新建小部件时弹出的"名称/URL"输入界面。
- `app/src/main/java/.../GalleryActivity.kt`:点击小部件后打开的图片浏览页(WebView)。
- `app/src/main/java/.../ApiClient.kt`:请求服务端 API、解析 JSON。
- `app/src/main/java/.../WidgetPrefs.kt`:每个小部件的名称/URL 用 SharedPreferences 持久化。
