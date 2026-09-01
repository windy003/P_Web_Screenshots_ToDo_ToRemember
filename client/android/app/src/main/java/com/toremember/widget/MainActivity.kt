package com.toremember.widget

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat

/**
 * 这个 App 本身没有主界面功能,只作为小部件的宿主。
 * 打开它只是提示用户去桌面添加小部件。
 */
class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        // 小部件靠 WidgetRefreshService 的前台服务通知来保证锁屏后也能按时刷新,
        // Android 13+ 上这条通知需要用户授权 POST_NOTIFICATIONS 才会显示;
        // 就算拒绝,服务本身依然会继续运行,只是看不到那条提示通知而已。
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED
        ) {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)
        }
    }
}
