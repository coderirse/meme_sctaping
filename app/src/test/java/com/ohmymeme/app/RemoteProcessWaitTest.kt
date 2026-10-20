package com.ohmymeme.app

import org.junit.Assert.assertEquals
import org.junit.Test
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream

class RemoteProcessWaitTest {
    @Test
    fun legacyRemoteProcessDoesNotUseDefaultExitPolling() {
        val remote = object : Process() {
            override fun getOutputStream() = ByteArrayOutputStream()
            override fun getInputStream() = ByteArrayInputStream(byteArrayOf())
            override fun getErrorStream() = ByteArrayInputStream(byteArrayOf())
            override fun waitFor(): Int = 7
            override fun exitValue(): Int = throw IllegalArgumentException("process hasn't exited")
            override fun destroy() = Unit
        }
        assertEquals(7, ShizukuBridge.waitForRemote(remote, 2))
    }
}
