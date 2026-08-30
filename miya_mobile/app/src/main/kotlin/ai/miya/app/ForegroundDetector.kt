package ai.miya.app

import android.app.Activity
import android.app.Application
import android.os.Bundle
import java.util.concurrent.atomic.AtomicInteger

object ForegroundDetector : Application.ActivityLifecycleCallbacks {

    private val resumedCount = AtomicInteger(0)

    fun init(app: Application) {
        app.registerActivityLifecycleCallbacks(this)
    }

    fun isForeground(): Boolean = resumedCount.get() > 0

    override fun onActivityResumed(activity: Activity) {
        resumedCount.incrementAndGet()
    }

    override fun onActivityPaused(activity: Activity) {
        resumedCount.decrementAndGet()
    }

    override fun onActivityCreated(activity: Activity, savedInstanceState: Bundle?) {}
    override fun onActivityStarted(activity: Activity) {}
    override fun onActivityStopped(activity: Activity) {}
    override fun onActivitySaveInstanceState(activity: Activity, outState: Bundle) {}
    override fun onActivityDestroyed(activity: Activity) {}
}
