package ai.miya.app

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.mutableStateOf
import androidx.core.content.ContextCompat

class MainActivity : ComponentActivity() {

    private val deepLinkSessionId = mutableStateOf<String?>(null)

    private val notificationPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) {
            ChatNotificationService.start(this)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        deepLinkSessionId.value = intent?.getStringExtra(ChatNotificationService.EXTRA_SESSION_ID)
        enableEdgeToEdge()
        setContent {
            MainScreen(deepLinkSessionId = deepLinkSessionId.value, onSessionConsumed = {
                deepLinkSessionId.value = null
            })
        }
        requestNotificationPermission()
    }

    override fun onNewIntent(intent: android.content.Intent) {
        super.onNewIntent(intent)
        val sessionId = intent.getStringExtra(ChatNotificationService.EXTRA_SESSION_ID)
        if (sessionId != null) {
            deepLinkSessionId.value = sessionId
        }
    }

    private fun requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            when {
                ContextCompat.checkSelfPermission(
                    this, Manifest.permission.POST_NOTIFICATIONS
                ) == PackageManager.PERMISSION_GRANTED -> {
                    ChatNotificationService.start(this)
                }
                else -> {
                    notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                }
            }
        } else {
            ChatNotificationService.start(this)
        }
    }
}
