package ai.miya.app

import ai.miya.domain.AppEvent
import ai.miya.domain.AppEventBus
import ai.miya.domain.ServiceRegistry
import ai.miya.network.MiyaApiClient
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

class MiyaFirebaseService : FirebaseMessagingService() {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onMessageReceived(remoteMessage: RemoteMessage) {
        super.onMessageReceived(remoteMessage)

        val data = remoteMessage.data
        val message = data["message"]
        val sessionId = data["session_id"]

        if (message == null) return

        scope.launch {
            try {
                AppEventBus.emit(AppEvent.ProactiveMessage(message))
            } catch (_: Exception) {}
        }

        if (!ForegroundDetector.isForeground()) {
            ChatNotificationService.showDirectNotification(this, message, sessionId)
        }
    }

    override fun onNewToken(token: String) {
        super.onNewToken(token)
        scope.launch {
            try {
                val api = ServiceRegistry.get(MiyaApiClient::class.java)
                if (api != null) {
                    api.registerFcmToken(token)
                }
            } catch (_: Exception) {}
        }
    }
}
