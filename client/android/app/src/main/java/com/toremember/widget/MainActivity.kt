package com.toremember.widget

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity

/**
 * 这个 App 本身没有主界面功能,只作为小部件的宿主。
 * 打开它只是提示用户去桌面添加小部件。
 */
class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
    }
}
