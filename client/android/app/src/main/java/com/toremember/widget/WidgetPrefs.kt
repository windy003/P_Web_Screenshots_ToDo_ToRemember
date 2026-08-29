package com.toremember.widget

import android.content.Context

/** 保存每个小部件(按 appWidgetId 区分)的名称和 URL。 */
object WidgetPrefs {
    private const val PREFS_NAME = "widget_prefs"

    private fun prefs(context: Context) =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    fun save(context: Context, appWidgetId: Int, name: String, url: String) {
        prefs(context).edit()
            .putString("name_$appWidgetId", name)
            .putString("url_$appWidgetId", url)
            .apply()
    }

    fun getName(context: Context, appWidgetId: Int): String? =
        prefs(context).getString("name_$appWidgetId", null)

    fun getUrl(context: Context, appWidgetId: Int): String? =
        prefs(context).getString("url_$appWidgetId", null)

    fun remove(context: Context, appWidgetId: Int) {
        prefs(context).edit()
            .remove("name_$appWidgetId")
            .remove("url_$appWidgetId")
            .apply()
    }
}
