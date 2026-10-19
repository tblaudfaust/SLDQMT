import org.jetbrains.kotlin.gradle.dsl.JvmTarget

// SLPHC M&E Field Tool: a small Android app that opens the M&E field tool of censusme.statistics.sl in
// field mode (sign-in, then only the KPI form and the reports on the device). The web app itself is
// offline-capable; this wrapper gives it an icon, GPS permission handling and a locked-down navigation.
plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
}

android {
    namespace = "sl.gov.statistics.mefieldtool"
    compileSdk = 36

    defaultConfig {
        applicationId = "sl.gov.statistics.mefieldtool"
        minSdk = 26
        targetSdk = 36
        versionCode = 2
        versionName = "1.1.0"
        // The site the app opens: -PfieldToolUrl=... or the FIELD_TOOL_URL environment variable.
        val url = (project.findProperty("fieldToolUrl") as String?) ?: System.getenv("FIELD_TOOL_URL") ?: "https://censusme.statistics.sl"
        buildConfigField("String", "APP_URL", "\"$url\"")
    }

    signingConfigs {
        create("release") {
            val keystorePath = System.getenv("ANDROID_KEYSTORE_PATH")
            if (keystorePath != null && file(keystorePath).exists()) {
                storeFile = file(keystorePath)
                storePassword = System.getenv("ANDROID_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("ANDROID_KEY_ALIAS")
                keyPassword = System.getenv("ANDROID_KEY_PASSWORD")
            } else {
                initWith(getByName("debug"))
            }
        }
    }

    buildTypes {
        debug {
            // the dashboard dev server on this PC, reached through: adb reverse tcp:5173 tcp:5173 (localhost keeps the service worker, a secure context)
            buildConfigField("String", "APP_URL", "\"http://localhost:5173\"")
        }
        release {
            signingConfig = signingConfigs.getByName("release")
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    buildFeatures {
        buildConfig = true
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(JvmTarget.JVM_17)
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.ktx)
    implementation(libs.androidx.webkit)
}
