package com.ohmymeme.app

import android.content.Intent
import android.app.PendingIntent
import android.os.Build
import android.service.quicksettings.Tile
import android.service.quicksettings.TileService

/**
 * 通知栏控制中心快捷按钮：点击打开主界面。
 * 用户需在系统「快捷设置」编辑面板手动添加本磁贴；
 * Android 13+（API 33）可在设置页调用 [android.service.quicksettings.TileService.requestAddTileService] 引导添加。
 */
class QuickTileService : TileService() {

    override fun onStartListening() {
        super.onStartListening()
        updateTile()
    }

    override fun onClick() {
        if (isLocked) {
            unlockAndRun { launchApp() }
        } else {
            launchApp()
        }
    }

    private fun launchApp() {
        try {
            val intent = Intent(this, MainActivity::class.java)
                    .putExtra("collector_qq", true)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED)
            if (Build.VERSION.SDK_INT >= 34) {
                startActivityAndCollapse(PendingIntent.getActivity(
                    this, 0, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
                ))
            } else {
                @Suppress("DEPRECATION")
                startActivityAndCollapse(intent)
            }
        } catch (e: Exception) {
            android.util.Log.w(TAG, "launch failed: $e")
        }
    }

    private fun updateTile() {
        val tile = qsTile ?: return
        tile.state = Tile.STATE_ACTIVE
        tile.updateTile()
    }

    private companion object {
        const val TAG = "OhMyMeme/QuickTile"
    }
}
