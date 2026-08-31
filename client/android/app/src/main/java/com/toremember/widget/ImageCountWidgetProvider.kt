package com.toremember.widget

import android.app.AlarmManager
import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.os.SystemClock
import android.widget.RemoteViews
import java.util.concurrent.Executors

/**
 * 显示"大/小/待"三个分类图片数量的小部件,点击后直接打开编辑设置界面。
 *
 * 系统自带的 updatePeriodMillis 最短只能设到 30 分钟(系统强制下限,设更短也没用),
 * 想做到每分钟刷新一次,只能自己用 AlarmManager 定时唤醒。注意:Doze/省电模式下,
 * 系统仍可能推迟这种"非精确"闹钟——这也是小部件底部要显示"距离上次刷新多久"的原因,
 * 让用户能看出数据是不是因为省电策略变得不够新鲜,而不是假装每分钟都精确刷新到。
 */
class ImageCountWidgetProvider : AppWidgetProvider() {

    companion object {
        private val executor = Executors.newCachedThreadPool()

        private const val ACTION_REFRESH_TICK = "com.toremember.widget.ACTION_REFRESH_TICK"
        private const val REFRESH_INTERVAL_MILLIS = 60_000L
        private const val ALARM_REQUEST_CODE = 1001

        private fun refreshPendingIntent(context: Context): PendingIntent {
            val intent = Intent(context, ImageCountWidgetProvider::class.java).apply {
                action = ACTION_REFRESH_TICK
            }
            return PendingIntent.getBroadcast(
                context,
                ALARM_REQUEST_CODE,
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )
        }

        private fun scheduleRefreshAlarm(context: Context) {
            // setInexactRepeating 在系统看来是"低优先级"的重复闹钟,一旦进入 Doze/省电模式
            // 很容易被系统整个跳过、批量推迟到不知道多久之后。改成每次触发后自己重新预约
            // 下一次的 setAndAllowWhileIdle,能在 Doze 维护窗口也照样醒来,不需要像
            // setExactAndAllowWhileIdle 那样在 Android 12+ 上额外申请"闹钟与提醒"权限
            // (那个权限拿不到会直接抛异常,风险更大,对这种非核心功能不值得)。
            // 即便如此,如果用户没有把这个 App 加入电池优化白名单,深度省电时系统仍会
            // 强制拉长间隔,这是安卓平台本身的限制,不是这段代码能绕开的。
            val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
            val triggerAt = SystemClock.elapsedRealtime() + REFRESH_INTERVAL_MILLIS
            alarmManager.setAndAllowWhileIdle(
                AlarmManager.ELAPSED_REALTIME,
                triggerAt,
                refreshPendingIntent(context)
            )
        }

        private fun cancelRefreshAlarm(context: Context) {
            val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
            alarmManager.cancel(refreshPendingIntent(context))
        }

        /** 第二个返回值表示这一行是不是真的刷新成功了(而不是留空/请求失败)。 */
        private fun fetchRowText(context: Context, url: String?): Pair<String, Boolean> {
            if (url.isNullOrBlank()) {
                return context.getString(R.string.widget_row_empty) to false
            }
            val result = ApiClient.fetchFolderInfo(url)
            return if (result != null) {
                result.count to true
            } else {
                context.getString(R.string.widget_load_failed) to false
            }
        }

        private fun applyRows(context: Context, views: RemoteViews, big: String, small: String, todo: String) {
            views.setTextViewText(
                R.id.widget_count_big,
                context.getString(R.string.widget_row_format, context.getString(R.string.row_label_big), big)
            )
            views.setTextViewText(
                R.id.widget_count_small,
                context.getString(R.string.widget_row_format, context.getString(R.string.row_label_small), small)
            )
            views.setTextViewText(
                R.id.widget_count_todo,
                context.getString(R.string.widget_row_format, context.getString(R.string.row_label_todo), todo)
            )
        }

        /**
         * 用 Chronometer 而不是普通文字:Chronometer 一旦设好 base 并 start,
         * 是由系统/桌面自己按秒重绘的,不需要我们的进程或闹钟一直醒着去更新它,
         * 显示出来就是"距离上次刷新"那个数字自己一直在跳(H:MM:SS)。
         *
         * Chronometer.base 要求是 SystemClock.elapsedRealtime() 时间基准的值,
         * 但我们持久化存的 lastRefreshedAt 是墙上时钟(System.currentTimeMillis()),
         * 这样重启手机后这个时间戳依然有意义。所以每次真正推送 RemoteViews 时,
         * 都用"现在的 elapsedRealtime() 减去已经过去的时长"现算一个等效 base。
         */
        private fun applyLastRefreshChronometer(context: Context, views: RemoteViews, appWidgetId: Int) {
            val lastRefreshedAt = WidgetPrefs.getLastRefreshedAt(context, appWidgetId)
            if (lastRefreshedAt <= 0L) {
                views.setChronometer(R.id.widget_last_refresh, SystemClock.elapsedRealtime(), null, false)
                return
            }
            val elapsedSinceRefresh = System.currentTimeMillis() - lastRefreshedAt
            val base = SystemClock.elapsedRealtime() - elapsedSinceRefresh
            views.setChronometer(R.id.widget_last_refresh, base, null, true)
        }

        fun updateWidget(context: Context, appWidgetManager: AppWidgetManager, appWidgetId: Int) {
            val name = WidgetPrefs.getName(context, appWidgetId) ?: context.getString(R.string.app_name)
            val urlBig = WidgetPrefs.getUrlBig(context, appWidgetId)
            val urlSmall = WidgetPrefs.getUrlSmall(context, appWidgetId)
            val urlTodo = WidgetPrefs.getUrlTodo(context, appWidgetId)

            val editIntent = Intent(context, WidgetConfigureActivity::class.java).apply {
                putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, appWidgetId)
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            }
            val editPendingIntent = PendingIntent.getActivity(
                context,
                appWidgetId,
                editIntent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )

            val loadingText = context.getString(R.string.widget_loading)
            val loadingViews = RemoteViews(context.packageName, R.layout.widget_image_count)
            loadingViews.setTextViewText(R.id.widget_name, name)
            applyRows(
                context,
                loadingViews,
                if (urlBig.isNullOrBlank()) context.getString(R.string.widget_row_empty) else loadingText,
                if (urlSmall.isNullOrBlank()) context.getString(R.string.widget_row_empty) else loadingText,
                if (urlTodo.isNullOrBlank()) context.getString(R.string.widget_row_empty) else loadingText
            )
            // 加载中先照旧显示上一次成功刷新时间起继续计时,别让这一栏在刷新期间空掉/闪烁。
            applyLastRefreshChronometer(context, loadingViews, appWidgetId)
            loadingViews.setOnClickPendingIntent(R.id.widget_root, editPendingIntent)
            appWidgetManager.updateAppWidget(appWidgetId, loadingViews)

            if (urlBig.isNullOrBlank() && urlSmall.isNullOrBlank() && urlTodo.isNullOrBlank()) {
                return
            }

            executor.execute {
                val (bigText, bigOk) = fetchRowText(context, urlBig)
                val (smallText, smallOk) = fetchRowText(context, urlSmall)
                val (todoText, todoOk) = fetchRowText(context, urlTodo)

                // 只有真的成功拿到新数据,才把"距离上次刷新"的计时器清零重记;
                // 全部请求都失败的话不能假装刷新过,得让计时器继续走,让用户能看出
                // 数据其实已经卡了多久没更新,而不是每次重试失败也在悄悄"归零"。
                if (bigOk || smallOk || todoOk) {
                    WidgetPrefs.setLastRefreshedAt(context, appWidgetId, System.currentTimeMillis())
                }

                val views = RemoteViews(context.packageName, R.layout.widget_image_count)
                views.setTextViewText(R.id.widget_name, name)
                applyRows(context, views, bigText, smallText, todoText)
                applyLastRefreshChronometer(context, views, appWidgetId)
                views.setOnClickPendingIntent(R.id.widget_root, editPendingIntent)

                appWidgetManager.updateAppWidget(appWidgetId, views)
            }
        }
    }

    override fun onReceive(context: Context, intent: Intent) {
        super.onReceive(context, intent)
        if (intent.action == ACTION_REFRESH_TICK) {
            val appWidgetManager = AppWidgetManager.getInstance(context)
            val ids = appWidgetManager.getAppWidgetIds(ComponentName(context, ImageCountWidgetProvider::class.java))
            for (appWidgetId in ids) {
                updateWidget(context, appWidgetManager, appWidgetId)
            }
            // setAndAllowWhileIdle 只触发一次,得在这次醒来的时候自己把下一次也约好。
            if (ids.isNotEmpty()) {
                scheduleRefreshAlarm(context)
            }
        }
    }

    override fun onUpdate(
        context: Context,
        appWidgetManager: AppWidgetManager,
        appWidgetIds: IntArray
    ) {
        for (appWidgetId in appWidgetIds) {
            updateWidget(context, appWidgetManager, appWidgetId)
        }
        // 系统每次调用 onUpdate(新加图标、每 30 分钟一次的兜底刷新……)都顺手确认一下
        // 每分钟的闹钟还在,防止某些情况下闹钟被系统清掉后就再也不会自己恢复。
        scheduleRefreshAlarm(context)
    }

    override fun onEnabled(context: Context) {
        super.onEnabled(context)
        scheduleRefreshAlarm(context)
    }

    override fun onDisabled(context: Context) {
        super.onDisabled(context)
        cancelRefreshAlarm(context)
    }

    override fun onDeleted(context: Context, appWidgetIds: IntArray) {
        for (appWidgetId in appWidgetIds) {
            WidgetPrefs.remove(context, appWidgetId)
        }
    }
}
