plugins {
    id("com.android.application")
}

android {
    namespace = "com.bestg.betting"
    compileSdk = 30
    
    defaultConfig {
        applicationId = "com.bestg.betting"
        minSdk = 21
        targetSdk = 30
        versionCode = 1
        versionName = "1.0"
    }
    
    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }
}

dependencies {
    // NO DEPENDENCIES AT ALL - bare minimum
}
