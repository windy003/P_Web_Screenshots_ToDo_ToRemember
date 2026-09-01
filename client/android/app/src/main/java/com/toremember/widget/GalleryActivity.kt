package com.toremember.widget

import android.annotation.SuppressLint
import android.app.AlertDialog
import android.os.Bundle
import android.webkit.JsResult
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat

/**
 * 浏览某个文件夹的图片。直接复用服务端网页版画廊(已按从旧到新排序,
 * 并支持点击上一张/下一张、"3天后"),用 WebView 打开即可,不用在客户端重复实现。
 *
 * 网页在进入单张图片的全屏查看页(URL 里带 "/view/")时,这里会同步把系统状态栏/
 * 导航栏也隐藏掉,让照片真正铺满整个屏幕;回到网格列表页时再恢复系统栏。
 */
class GalleryActivity : AppCompatActivity() {

    companion object {
        const val EXTRA_URL = "extra_url"
        const val EXTRA_TITLE = "extra_title"
        private const val FULLSCREEN_PATH_MARKER = "/view/"
    }

    private lateinit var insetsController: WindowInsetsControllerCompat

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        setContentView(R.layout.activity_gallery)

        title = intent.getStringExtra(EXTRA_TITLE) ?: getString(R.string.app_name)
        val url = intent.getStringExtra(EXTRA_URL)

        insetsController = WindowInsetsControllerCompat(window, window.decorView)
        insetsController.systemBarsBehavior =
            WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE

        val webView = findViewById<WebView>(R.id.gallery_web_view)
        webView.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView, finishedUrl: String?) {
                super.onPageFinished(view, finishedUrl)
                setFullscreenMode(finishedUrl?.contains(FULLSCREEN_PATH_MARKER) == true)
            }
        }
        // WebView 默认不会显示 JS 的 alert() 弹窗(比如删除失败提示),
        // 需要自己接管 WebChromeClient 用原生对话框弹出来。
        webView.webChromeClient = object : WebChromeClient() {
            override fun onJsAlert(
                view: WebView,
                url: String?,
                message: String?,
                result: JsResult,
            ): Boolean {
                AlertDialog.Builder(this@GalleryActivity)
                    .setMessage(message)
                    .setPositiveButton(android.R.string.ok) { _, _ -> result.confirm() }
                    .setOnCancelListener { result.cancel() }
                    .setCancelable(true)
                    .show()
                return true
            }
        }

        webView.settings.javaScriptEnabled = true
        // 悬浮控制面板的拖动位置保存在 localStorage 里,需要开启 DOM storage 才能生效。
        webView.settings.domStorageEnabled = true
        // 长按图片(比如拖动悬浮面板时手指压到了图片上)会触发 WebView 自带的
        // "保存图片"菜单,进而跳到系统文件选择器,和我们自己的拖动手势冲突。
        // 这里直接吞掉长按事件,让长按只服务于我们自己的拖动逻辑。
        webView.setOnLongClickListener { true }

        if (!url.isNullOrBlank()) {
            webView.loadUrl(url)
        }
    }

    private fun setFullscreenMode(fullscreen: Boolean) {
        if (fullscreen) {
            insetsController.hide(WindowInsetsCompat.Type.systemBars())
        } else {
            insetsController.show(WindowInsetsCompat.Type.systemBars())
        }
    }

    override fun onBackPressed() {
        val webView = findViewById<WebView>(R.id.gallery_web_view)
        if (webView.canGoBack()) {
            webView.goBack()
        } else {
            super.onBackPressed()
        }
    }
}
