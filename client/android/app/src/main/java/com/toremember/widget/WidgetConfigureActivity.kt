package com.toremember.widget

import android.app.Activity
import android.appwidget.AppWidgetManager
import android.content.Intent
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.RadioButton
import android.widget.TextView
import android.widget.Toast

/**
 * 新建小部件或编辑已有小部件时弹出的配置界面:输入"名称",以及"大/小/待"三个分类
 * 各自的 API URL 和浏览地址。底部的三个单选按钮用于直接跳转到对应分类的浏览页面。
 * 提交后保存到 SharedPreferences,并立即触发一次小部件刷新。
 */
class WidgetConfigureActivity : Activity() {

    private var appWidgetId = AppWidgetManager.INVALID_APPWIDGET_ID

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setResult(RESULT_CANCELED)
        setContentView(R.layout.activity_widget_configure)

        appWidgetId = intent?.extras?.getInt(
            AppWidgetManager.EXTRA_APPWIDGET_ID,
            AppWidgetManager.INVALID_APPWIDGET_ID
        ) ?: AppWidgetManager.INVALID_APPWIDGET_ID

        if (appWidgetId == AppWidgetManager.INVALID_APPWIDGET_ID) {
            finish()
            return
        }

        val editName = findViewById<EditText>(R.id.edit_name)
        val editUrlBig = findViewById<EditText>(R.id.edit_url_big)
        val editUrlSmall = findViewById<EditText>(R.id.edit_url_small)
        val editUrlTodo = findViewById<EditText>(R.id.edit_url_todo)
        val editBrowseBig = findViewById<EditText>(R.id.edit_browse_big)
        val editBrowseSmall = findViewById<EditText>(R.id.edit_browse_small)
        val editBrowseTodo = findViewById<EditText>(R.id.edit_browse_todo)

        val existingName = WidgetPrefs.getName(this, appWidgetId)
        val isEditing = existingName != null

        if (isEditing) {
            editName.setText(existingName)
            editUrlBig.setText(WidgetPrefs.getUrlBig(this, appWidgetId))
            editUrlSmall.setText(WidgetPrefs.getUrlSmall(this, appWidgetId))
            editUrlTodo.setText(WidgetPrefs.getUrlTodo(this, appWidgetId))
            editBrowseBig.setText(WidgetPrefs.getBrowseBig(this, appWidgetId))
            editBrowseSmall.setText(WidgetPrefs.getBrowseSmall(this, appWidgetId))
            editBrowseTodo.setText(WidgetPrefs.getBrowseTodo(this, appWidgetId))
            findViewById<TextView>(R.id.title_text).setText(R.string.edit_title)
            findViewById<Button>(R.id.btn_add).setText(R.string.btn_save)
        }

        findViewById<Button>(R.id.btn_cancel).setOnClickListener { finish() }

        findViewById<Button>(R.id.btn_add).setOnClickListener {
            val name = editName.text.toString().trim()
            val urlBig = editUrlBig.text.toString().trim()
            val urlSmall = editUrlSmall.text.toString().trim()
            val urlTodo = editUrlTodo.text.toString().trim()
            val browseBig = editBrowseBig.text.toString().trim()
            val browseSmall = editBrowseSmall.text.toString().trim()
            val browseTodo = editBrowseTodo.text.toString().trim()
            if (name.isEmpty()) {
                Toast.makeText(this, R.string.error_empty, Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            WidgetPrefs.save(
                this, appWidgetId, name,
                urlBig, urlSmall, urlTodo,
                browseBig, browseSmall, browseTodo
            )

            val appWidgetManager = AppWidgetManager.getInstance(this)
            ImageCountWidgetProvider.updateWidget(this, appWidgetManager, appWidgetId)

            val resultValue = Intent().putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, appWidgetId)
            setResult(RESULT_OK, resultValue)
            finish()
        }

        val openBrowse = { browseUrl: String, title: String ->
            if (browseUrl.isBlank()) {
                Toast.makeText(this, R.string.error_browse_empty, Toast.LENGTH_SHORT).show()
            } else {
                startActivity(Intent(this, GalleryActivity::class.java).apply {
                    putExtra(GalleryActivity.EXTRA_URL, browseUrl)
                    putExtra(GalleryActivity.EXTRA_TITLE, title)
                })
            }
        }

        findViewById<RadioButton>(R.id.radio_browse_big).setOnClickListener {
            openBrowse(editBrowseBig.text.toString().trim(), getString(R.string.row_label_big))
        }
        findViewById<RadioButton>(R.id.radio_browse_small).setOnClickListener {
            openBrowse(editBrowseSmall.text.toString().trim(), getString(R.string.row_label_small))
        }
        findViewById<RadioButton>(R.id.radio_browse_todo).setOnClickListener {
            openBrowse(editBrowseTodo.text.toString().trim(), getString(R.string.row_label_todo))
        }
    }
}
