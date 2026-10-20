package com.ohmymeme.app

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class LanBridgeTest {
    @Test
    fun encryptedDesktopRoundtripPreservesBothAnimations() {
        val args = InstrumentationRegistry.getArguments()
        assumeTrue("使用 scripts/lan_smoke.py 启动隔离的电脑测试服务", args.containsKey("collector_port"))
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        val webp = instrumentation.context.assets.open("collector/animated.webp").use { it.readBytes() }
        val gif = instrumentation.context.assets.open("collector/animated.gif").use { it.readBytes() }
        val connection = LanClient.LanConnection()
        try {
            connection.connect("127.0.0.1", args.getString("collector_port")!!.toInt(),
                args.getString("collector_secret")!!, JSONObject().put("name", "MemeCollectorTest").put("os", "Android"))
            assertTrue(connection.ping())
            assertFalse(connection.allowSecretConfig)
            val before = connection.pullManifest().getJSONArray("memes")
            assertEquals(1, before.length())
            val filename = before.getJSONObject(0).getString("filename")
            val received = connection.pullFile(filename)
            assertArrayEquals(webp, received)
            val result = MemeImporter.importBytes(context, received, "desktop.webp")
            assertTrue(result == MemeImporter.ImportOutcome.IMPORTED || result == MemeImporter.ImportOutcome.DUPLICATE)
            val row = MemeDb.get(context).getByHash(FileUtils.sha256(received.inputStream()))!!
            assertArrayEquals(webp, StoragePaths.cacheDir(context).child(row.filename).readBytes())
            connection.pushFile("return.gif", gif)
            connection.pushFile("return.gif", gif)
            assertEquals(2, connection.pullManifest().getJSONArray("memes").length())
        } finally {
            connection.close()
        }
    }
}
