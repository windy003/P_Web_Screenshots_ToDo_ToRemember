package com.toremember.widget

import android.content.Context

/** 保存每个小部件(按 appWidgetId 区分)的名称,以及"大/小/待"三个分类各自的 API URL 和浏览地址。 */
object WidgetPrefs {
    private const val PREFS_NAME = "widget_prefs"

    private fun prefs(context: Context) =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    fun save(
        context: Context,
        appWidgetId: Int,
        name: String,
        urlBig: String,
        urlSmall: String,
        urlTodo: String,
        browseBig: String,
        browseSmall: String,
        browseTodo: String
    ) {
        prefs(context).edit()
            .putString("name_$appWidgetId", name)
            .putString("url_big_$appWidgetId", urlBig)
            .putString("url_small_$appWidgetId", urlSmall)
            .putString("url_todo_$appWidgetId", urlTodo)
            .putString("browse_big_$appWidgetId", browseBig)
            .putString("browse_small_$appWidgetId", browseSmall)
            .putString("browse_todo_$appWidgetId", browseTodo)
            .apply()
    }

    fun getName(context: Context, appWidgetId: Int): String? =
        prefs(context).getString("name_$appWidgetId", null)

    fun getUrlBig(context: Context, appWidgetId: Int): String? =
        prefs(context).getString("url_big_$appWidgetId", null)

    fun getUrlSmall(context: Context, appWidgetId: Int): String? =
        prefs(context).getString("url_small_$appWidgetId", null)

    fun getUrlTodo(context: Context, appWidgetId: Int): String? =
        prefs(context).getString("url_todo_$appWidgetId", null)

    fun getBrowseBig(context: Context, appWidgetId: Int): String? =
        prefs(context).getString("browse_big_$appWidgetId", null)

    fun getBrowseSmall(context: Context, appWidgetId: Int): String? =
        prefs(context).getString("browse_small_$appWidgetId", null)

    fun getBrowseTodo(context: Context, appWidgetId: Int): String? =
        prefs(context).getString("browse_todo_$appWidgetId", null)

    /** 记录这个小部件最近一次刷新(尝试拉取数据)的时间,用来在小部件底部显示"多久之前更新的"。 */
    fun setLastRefreshedAt(context: Context, appWidgetId: Int, timeMillis: Long) {
        prefs(context).edit().putLong("last_refreshed_$appWidgetId", timeMillis).apply()
    }

    /** 返回 0 表示从来没有成功刷新过。 */
    fun getLastRefreshedAt(context: Context, appWidgetId: Int): Long =
        prefs(context).getLong("last_refreshed_$appWidgetId", 0L)

    fun remove(context: Context, appWidgetId: Int) {
        prefs(context).edit()
            .remove("name_$appWidgetId")
            .remove("url_big_$appWidgetId")
            .remove("url_small_$appWidgetId")
            .remove("url_todo_$appWidgetId")
            .remove("browse_big_$appWidgetId")
            .remove("browse_small_$appWidgetId")
            .remove("browse_todo_$appWidgetId")
            .remove("last_refreshed_$appWidgetId")
            .apply()
    }
}
