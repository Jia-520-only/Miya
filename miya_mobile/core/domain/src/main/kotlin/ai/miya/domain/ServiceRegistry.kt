package ai.miya.domain

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import java.util.concurrent.ConcurrentHashMap

object ServiceRegistry {

    private val singletonFactories = ConcurrentHashMap<Class<*>, () -> Any>()
    private val singletons = ConcurrentHashMap<Class<*>, Any>()
    private val factories = ConcurrentHashMap<Class<*>, () -> Any>()

    private val _initialized = MutableStateFlow(false)
    val initialized: StateFlow<Boolean> = _initialized

    fun <T : Any> registerSingleton(type: Class<T>, factory: () -> T) {
        singletonFactories[type] = factory as () -> Any
    }

    fun <T : Any> register(type: Class<T>, factory: () -> T) {
        factories[type] = factory as () -> Any
    }

    fun markInitialized() {
        _initialized.value = true
    }

    @Suppress("UNCHECKED_CAST")
    fun <T : Any> get(type: Class<T>): T? {
        singletons[type]?.let { return it as T }
        singletonFactories[type]?.let { factory ->
            val instance = singletons.computeIfAbsent(type) {
                factory.invoke() ?: throw NullPointerException("Singleton factory returned null for ${type.name}")
            }
            return instance as T
        }
        return factories[type]?.invoke() as? T
    }

    fun <T : Any> getOrThrow(type: Class<T>): T {
        return get(type) ?: throw IllegalStateException("${type.name} not registered")
    }

    fun <T : Any> unregister(type: Class<T>) {
        factories.remove(type)
        singletonFactories.remove(type)
        singletons.remove(type)
    }

    fun clear() {
        factories.clear()
        singletonFactories.clear()
        singletons.clear()
    }
}
