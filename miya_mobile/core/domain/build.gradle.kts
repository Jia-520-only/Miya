plugins {
    alias(libs.plugins.android.library)
}

android {
    namespace = "ai.miya.domain"
    compileSdk = 35
    defaultConfig { minSdk = 26 }
}

dependencies {
    implementation(project(":core:model"))
    implementation(libs.kotlinx.coroutines.core)
}
