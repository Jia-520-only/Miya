plugins {
    alias(libs.plugins.android.library)
    alias(libs.plugins.kotlin.serialization)
}

android {
    namespace = "ai.miya.model"
    compileSdk = 35
    defaultConfig { minSdk = 26 }
}

dependencies {
    implementation(libs.kotlinx.serialization.json)
}
