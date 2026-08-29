package com.toremember.widget

import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

data class FolderApiResult(
    val count: String,
    val browseUrl: String?,
)

object ApiClient {
    /** 同步请求,调用方需要自己在后台线程执行。返回 null 表示请求失败。 */
    fun fetchFolderInfo(apiUrl: String): FolderApiResult? {
        return try {
            val connection = URL(apiUrl).openConnection() as HttpURLConnection
            connection.connectTimeout = 5000
            connection.readTimeout = 5000
            connection.requestMethod = "GET"
            connection.inputStream.use { stream ->
                val text = stream.bufferedReader(Charsets.UTF_8).readText()
                val json = JSONObject(text)
                FolderApiResult(
                    count = if (json.has("count")) json.get("count").toString() else "?",
                    browseUrl = if (json.has("browse_url") && !json.isNull("browse_url")) {
                        json.getString("browse_url")
                    } else null,
                )
            }
        } catch (e: Exception) {
            null
        }
    }
}
