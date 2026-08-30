package ai.miya.app

import ai.miya.domain.AppEvent
import ai.miya.domain.AppEventBus
import ai.miya.domain.ServiceRegistry
import ai.miya.domain.WebSocketProvider
import ai.miya.domain.WsEvent
import ai.miya.network.MiyaApiClient
import ai.miya.network.MiyaWebSocket
import android.app.*
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import androidx.core.app.NotificationCompat
import kotlinx.coroutines.*
import java.util.concurrent.atomic.AtomicBoolean

class ChatNotificationService : Service() {

    private val scope = CoroutineScope(Dispatchers.Main + SupervisorJob())
    private var pollingJob: Job? = null
    private var wsCollectJob: Job? = null
    private var lastMessageText: String = ""

    private val isDestroyed = AtomicBoolean(false)

    private var wakeLock: PowerManager.WakeLock? = null

    companion object {
        const val CHANNEL_ID = "miya_chat_notifications"
        const val CHANNEL_NAME = "弥娅消息"
        const val FOREGROUND_CHANNEL_ID = "miya_foreground_service"
        const val FOREGROUND_CHANNEL_NAME = "弥娅后台服务"
        const val FOREGROUND_NOTIFICATION_ID = 1001
        const val MESSAGE_NOTIFICATION_BASE = 1002
        const val EXTRA_SESSION_ID = "miya_session_id"

        fun start(context: Context) {
            val intent = Intent(context, ChatNotificationService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, ChatNotificationService::class.java))
        }

        fun showDirectNotification(context: Context, message: String, sessionId: String?) {
            val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            createChannelIfNeeded(context)

            val intent = context.packageManager.getLaunchIntentForPackage(context.packageName)
            if (intent != null) {
                intent.putExtra(EXTRA_SESSION_ID, sessionId)
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
            }
            val pendingIntent = if (intent != null) {
                PendingIntent.getActivity(
                    context, System.currentTimeMillis().toInt(), intent,
                    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
                )
            } else null

            val builder = NotificationCompat.Builder(context, CHANNEL_ID)
                .setSmallIcon(android.R.drawable.ic_dialog_info)
                .setContentTitle("弥娅")
                .setContentText(message.take(100))
                .setStyle(NotificationCompat.BigTextStyle().bigText(message))
                .setPriority(NotificationCompat.PRIORITY_HIGH)
                .setCategory(NotificationCompat.CATEGORY_MESSAGE)
                .setAutoCancel(true)
                .setDefaults(NotificationCompat.DEFAULT_VIBRATE or NotificationCompat.DEFAULT_LIGHTS or NotificationCompat.DEFAULT_SOUND)
                .setVibrate(longArrayOf(0, 250, 200, 250))
            if (pendingIntent != null) {
                builder.setContentIntent(pendingIntent)
                builder.setFullScreenIntent(pendingIntent, false)
            }
            manager.notify(
                (System.currentTimeMillis() % Int.MAX_VALUE).toInt(),
                builder.build()
            )
        }

        private fun createChannelIfNeeded(context: Context) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                val manager = context.getSystemService(NotificationManager::class.java)
                manager.deleteNotificationChannel(CHANNEL_ID)
                val channel = NotificationChannel(
                    CHANNEL_ID, CHANNEL_NAME, NotificationManager.IMPORTANCE_HIGH
                ).apply {
                    description = "弥娅的新消息提醒"
                    enableLights(true)
                    enableVibration(true)
                    vibrationPattern = longArrayOf(0, 250, 200, 250)
                    setBypassDnd(true)
                    lockscreenVisibility = Notification.VISIBILITY_PUBLIC
                }
                manager.createNotificationChannel(channel)
            }
        }
    }

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        acquireWakeLock()
        startForegroundNotification()
        subscribeToWebSocket()
        startPolling()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        isDestroyed.set(true)
        pollingJob?.cancel()
        wsCollectJob?.cancel()
        scope.cancel()
        releaseWakeLock()
        super.onDestroy()
    }

    override fun onTaskRemoved(rootIntent: Intent?) {
        val restartIntent = Intent(applicationContext, ChatNotificationService::class.java)
        val pendingIntent = PendingIntent.getService(
            applicationContext, 0, restartIntent,
            PendingIntent.FLAG_ONE_SHOT or PendingIntent.FLAG_IMMUTABLE
        )
        val manager = getSystemService(AlarmManager::class.java)
        if (manager != null) {
            manager.set(AlarmManager.RTC_WAKEUP, System.currentTimeMillis() + 500, pendingIntent)
        }
        super.onTaskRemoved(rootIntent)
    }

    private fun acquireWakeLock() {
        try {
            val powerManager = getSystemService(Context.POWER_SERVICE) as? PowerManager
            if (powerManager != null) {
                wakeLock = powerManager.newWakeLock(
                    PowerManager.PARTIAL_WAKE_LOCK,
                    "Miya:ChatNotificationWakeLock"
                )
                wakeLock?.acquire(30 * 60 * 1000L)
            }
        } catch (_: Exception) {}
    }

    private fun releaseWakeLock() {
        try {
            if (wakeLock?.isHeld == true) {
                wakeLock?.release()
            }
        } catch (_: Exception) {}
        wakeLock = null
    }

    private fun createNotificationChannel() {
        createChannelIfNeeded(this)
        createForegroundChannel(this)
    }

    private fun createForegroundChannel(context: Context) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val manager = context.getSystemService(NotificationManager::class.java)
            manager.deleteNotificationChannel(FOREGROUND_CHANNEL_ID)
            val channel = NotificationChannel(
                FOREGROUND_CHANNEL_ID, FOREGROUND_CHANNEL_NAME, NotificationManager.IMPORTANCE_MIN
            ).apply {
                description = "弥娅后台消息监听"
                setShowBadge(false)
                setSound(null, null)
                enableVibration(false)
            }
            manager.createNotificationChannel(channel)
        }
    }

    private fun startForegroundNotification() {
        val notification = createForegroundNotification("弥娅在线")
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            startForeground(FOREGROUND_NOTIFICATION_ID, notification, android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
        } else {
            startForeground(FOREGROUND_NOTIFICATION_ID, notification)
        }
    }

    private fun createForegroundNotification(text: String): Notification {
        val intent = packageManager.getLaunchIntentForPackage(packageName)
        val pendingIntent = if (intent != null) {
            PendingIntent.getActivity(
                this, 0, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )
        } else null

        val builder = NotificationCompat.Builder(this, FOREGROUND_CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle("弥娅")
            .setContentText(text)
            .setPriority(NotificationCompat.PRIORITY_MIN)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .setOngoing(true)
            .setSilent(true)
            .setForegroundServiceBehavior(NotificationCompat.FOREGROUND_SERVICE_IMMEDIATE)
        if (pendingIntent != null) {
            builder.setContentIntent(pendingIntent)
        }
        return builder.build()
    }

    private fun subscribeToWebSocket() {
        wsCollectJob = scope.launch {
            delay(2000)
            if (isDestroyed.get()) return@launch

            try {
                val provider = ServiceRegistry.get(WebSocketProvider::class.java)
                    ?: ServiceRegistry.get(MiyaWebSocket::class.java)

                if (provider == null) {
                    android.util.Log.w("ChatNotificationService", "No WebSocket provider available")
                    return@launch
                }

                val events = if (provider is WebSocketProvider) provider.events
                else (provider as MiyaWebSocket).events

                events.collect { event ->
                    if (isDestroyed.get()) return@collect
                    when (event) {
                        is WsEvent.Notification -> handleIncomingMessage(event.body)
                        else -> {}
                    }
                }
            } catch (e: CancellationException) {
                // expected on service destroy
            } catch (e: Exception) {
                android.util.Log.e("ChatNotificationService", "WebSocket subscription error", e)
                if (!isDestroyed.get()) {
                    delay(5000)
                    subscribeToWebSocket()
                }
            }
        }
    }

    private fun handleIncomingMessage(text: String) {
        if (text.isEmpty() || text == lastMessageText) return
        lastMessageText = text

        scope.launch {
            try {
                AppEventBus.emit(AppEvent.ProactiveMessage(text))
            } catch (_: CancellationException) {
            } catch (e: Exception) {
                android.util.Log.e("ChatNotificationService", "Failed to emit proactive message", e)
            }
        }

        if (!ForegroundDetector.isForeground()) {
            showDirectNotification(this, text, null)
        }
    }

    private fun startPolling() {
        pollingJob = scope.launch {
            delay(8000)
            while (isActive && !isDestroyed.get()) {
                delay(15_000)
                if (isDestroyed.get()) return@launch
                try {
                    val api = ServiceRegistry.get(MiyaApiClient::class.java) ?: continue
                    val msgs = api.getPendingMessages("default")
                    for (msg in msgs) {
                        val text = msg["message"] ?: continue
                        if (text == lastMessageText) continue
                        lastMessageText = text

                        try {
                            AppEventBus.emit(AppEvent.ProactiveMessage(text))
                        } catch (_: Exception) {}
                        if (!ForegroundDetector.isForeground()) {
                            showDirectNotification(this@ChatNotificationService, text, null)
                        }
                    }
                } catch (_: CancellationException) {
                    return@launch
                } catch (_: Exception) {}
            }
        }
    }
}
