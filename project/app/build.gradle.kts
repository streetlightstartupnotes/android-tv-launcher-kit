plugins { id("com.android.application") }
android {
    namespace = "org.example.tvlauncher"
    compileSdk = 34
    defaultConfig {
        applicationId = "org.example.tvlauncher"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "1.0.0"
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_1_8
        targetCompatibility = JavaVersion.VERSION_1_8
    }
}
