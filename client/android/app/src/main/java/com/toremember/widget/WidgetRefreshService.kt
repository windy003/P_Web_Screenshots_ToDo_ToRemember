package com.toremember.widget

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import androidx.core.app.NotificationCompat

/**
 * 用前台服务代替 AlarmManager 自循环闹钟来做"每分钟刷新一次小部件"。
 *
 * 之前的方案是每次闹钟醒来时自己重新预约下一次,一旦某一次因为锁屏后设备休眠/被系统
 * 冻结进程而没送达,后面就再没人把这个链条重新接上,小部件会永久停在最后一次刷新的
 * 状态。前台服务在系统眼里等同于"用户能感知到的进行中任务",不受 Doze 的 CPU 限制,
 * 能持续按时刷新;代价是必须常驻一条通知栏通知,这里做成静音、最低重要度、不发出提示音。
 */
class WidgetRefreshService : Service() {

    companion object {
        private const val CHANNEL_ID = "widget_refresh"
        private const val NOTIFICATION_ID = 1
        private const val REFRESH_INTERVAL_MILLIS = 60_000L
    }

    private val handler = Handler(Looper.getMainLooper())
    private var scheduled = false

    private val refreshRunnable = object : Runnable {
        override fun run() {
            ImageCountWidgetProvider.updateAllWidgets(applicationContext)
            handler.postDelayed(this, REFRESH_INTERVAL_MILLIS)
        }
    }

    override fun onCreate() {
        super.onCreate()
        startForeground(NOTIFICATION_ID, buildNotification())
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        // onStartCommand 可能因为 onEnabled/onUpdate 多次调用 startForegroundService 而被
        // 重复触发,scheduled 保证刷新循环只挂一份,不会越叠越快。
        if (!scheduled) {
            scheduled = true
            handler.post(refreshRunnable)
        }
        return START_STICKY
    }

    override fun onDestroy() {
        super.onDestroy()
        scheduled = false
        handler.removeCallbacks(refreshRunnable)
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun buildNotification(): Notification {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val manager = getSystemService(NotificationManager::class.java)
            val channel = NotificationChannel(
                CHANNEL_ID,
                getString(R.string.widget_refresh_channel_name),
                NotificationManager.IMPORTANCE_MIN
            ).apply {
                setShowBadge(false)
            }
            manager.createNotificationChannel(channel)
        }
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(getString(R.string.widget_refresh_notification_title))
            .setSmallIcon(R.drawable.ic_launcher)
            .setPriority(NotificationCompat.PRIORITY_MIN)
            .setOngoing(true)
            .setSilent(true)
            .build()
    }
}
