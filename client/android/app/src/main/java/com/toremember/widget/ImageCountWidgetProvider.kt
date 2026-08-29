package com.toremember.widget

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.Context
import android.content.Intent
import android.widget.RemoteViews
import java.util.concurrent.Executors

/** 显示某个文件夹图片数量的小部件,点击后打开图片浏览页面。 */
class ImageCountWidgetProvider : AppWidgetProvider() {

    companion object {
        private val executor = Executors.newCachedThreadPool()

        fun updateWidget(context: Context, appWidgetManager: AppWidgetManager, appWidgetId: Int) {
            val name = WidgetPrefs.getName(context, appWidgetId) ?: context.getString(R.string.app_name)
            val url = WidgetPrefs.getUrl(context, appWidgetId)

            val loadingViews = RemoteViews(context.packageName, R.layout.widget_image_count)
            loadingViews.setTextViewText(R.id.widget_name, name)
            loadingViews.setTextViewText(R.id.widget_count, context.getString(R.string.widget_loading))
            appWidgetManager.updateAppWidget(appWidgetId, loadingViews)

            if (url.isNullOrBlank()) {
                return
            }

            executor.execute {
                val result = ApiClient.fetchFolderInfo(url)
                val views = RemoteViews(context.packageName, R.layout.widget_image_count)
                views.setTextViewText(R.id.widget_name, name)

                if (result != null) {
                    views.setTextViewText(
                        R.id.widget_count,
                        context.getString(R.string.widget_count_format, result.count)
                    )
                    val browseUrl = result.browseUrl ?: url
                    val intent = Intent(context, GalleryActivity::class.java).apply {
                        putExtra(GalleryActivity.EXTRA_URL, browseUrl)
                        putExtra(GalleryActivity.EXTRA_TITLE, name)
                        flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
                    }
                    val pendingIntent = PendingIntent.getActivity(
                        context,
                        appWidgetId,
                        intent,
                        PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
                    )
                    views.setOnClickPendingIntent(R.id.widget_count, pendingIntent)
                    views.setOnClickPendingIntent(R.id.widget_name, pendingIntent)
                } else {
                    views.setTextViewText(R.id.widget_count, context.getString(R.string.widget_load_failed))
                }

                appWidgetManager.updateAppWidget(appWidgetId, views)
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
    }

    override fun onDeleted(context: Context, appWidgetIds: IntArray) {
        for (appWidgetId in appWidgetIds) {
            WidgetPrefs.remove(context, appWidgetId)
        }
    }
}
