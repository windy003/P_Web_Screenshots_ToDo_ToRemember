package com.toremember.widget

import android.annotation.SuppressLint
import android.os.Bundle
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.appcompat.app.AppCompatActivity

/**
 * 浏览某个文件夹的图片。直接复用服务端网页版画廊(已按从旧到新排序,
 * 并支持点击上一张/下一张),用 WebView 打开即可,不用在客户端重复实现。
 */
class GalleryActivity : AppCompatActivity() {

    companion object {
        const val EXTRA_URL = "extra_url"
        const val EXTRA_TITLE = "extra_title"
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_gallery)

        title = intent.getStringExtra(EXTRA_TITLE) ?: getString(R.string.app_name)
        val url = intent.getStringExtra(EXTRA_URL)

        val webView = findViewById<WebView>(R.id.gallery_web_view)
        webView.webViewClient = WebViewClient()
        webView.settings.javaScriptEnabled = true

        if (!url.isNullOrBlank()) {
            webView.loadUrl(url)
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
