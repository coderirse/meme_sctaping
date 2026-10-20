package com.ohmymeme.app

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class CollectorImportTest {
    @Test
    fun originalAnimationBytesAndMagicSurviveImport() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        for (name in listOf("static.png", "static.jpg", "animated.gif", "animated.webp")) {
            val bytes = instrumentation.context.assets.open("collector/$name").use { it.readBytes() }
            val result = MemeImporter.importBytes(context, bytes, "wrong.jpg", ".jpg")
            assertTrue(result == MemeImporter.ImportOutcome.IMPORTED || result == MemeImporter.ImportOutcome.DUPLICATE)
            val hash = FileUtils.sha256(bytes.inputStream())
            val meme = MemeDb.get(context).getByHash(hash)!!
            assertTrue(meme.filename.endsWith(FileUtils.detectExt(bytes)))
            val saved = StoragePaths.cacheDir(context).child(meme.filename)
            assertArrayEquals(bytes, saved.readBytes())
            assertEquals(MemeImporter.ImportOutcome.DUPLICATE, MemeImporter.importBytes(context, bytes, name))
            if (name.startsWith("animated")) assertTrue(FileUtils.isAnimatedFile(saved))
        }
    }

    @Test
    fun unsupportedContentNeverBecomesAnImage() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        assertEquals(MemeImporter.ImportOutcome.INVALID,
            MemeImporter.importBytes(context, "wxgf unsupported".toByteArray(), "fake.gif", ".gif"))
        assertEquals(MemeImporter.ImportOutcome.INVALID,
            MemeImporter.importBytes(context, byteArrayOf(), "empty.png"))
    }

    @Test
    fun boundedReadDoesNotConsumeArbitraryStream() {
        val source = ByteArray(4096) { 7 }
        assertEquals(65, FileUtils.readLimited(source.inputStream(), 64).size)
        assertArrayEquals(source, FileUtils.readLimited(source.inputStream(), 4096))
    }
}
