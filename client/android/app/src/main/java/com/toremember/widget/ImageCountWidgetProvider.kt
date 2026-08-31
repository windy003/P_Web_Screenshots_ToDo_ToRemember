package com.toremember.widget

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.Context
import android.content.Intent
import android.widget.RemoteViews
import java.util.concurrent.Executors

/** 显示"大/小/待"三个分类图片数量的小部件,点击后直接打开编辑设置界面。 */
class ImageCountWidgetProvider : AppWidgetProvider() {

    companion object {
        private val executor = Executors.newCachedThreadPool()

        private fun fetchRowText(context: Context, url: String?): String {
            if (url.isNullOrBlank()) {
                return context.getString(R.string.widget_row_empty)
            }
            val result = ApiClient.fetchFolderInfo(url)
            return result?.count ?: context.getString(R.string.widget_load_failed)
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
            loadingViews.setOnClickPendingIntent(R.id.widget_root, editPendingIntent)
            appWidgetManager.updateAppWidget(appWidgetId, loadingViews)

            if (urlBig.isNullOrBlank() && urlSmall.isNullOrBlank() && urlTodo.isNullOrBlank()) {
                return
            }

            executor.execute {
                val bigText = fetchRowText(context, urlBig)
                val smallText = fetchRowText(context, urlSmall)
                val todoText = fetchRowText(context, urlTodo)

                val views = RemoteViews(context.packageName, R.layout.widget_image_count)
                views.setTextViewText(R.id.widget_name, name)
                applyRows(context, views, bigText, smallText, todoText)
                views.setOnClickPendingIntent(R.id.widget_root, editPendingIntent)

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
