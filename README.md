🏈 NFL BETTING PREDICTOR

Android app that connects to a Python Flask API to get NFL game predictions.

## 📱 Features
- Test connection to server
- Get NFL game predictions
- Real-time API communication

## 🔧 Tech Stack
- **Android App**: Kotlin, Coroutines, HTTPURLConnection
- **Backend API**: Python, Flask, Flask-CORS
- **Build Tools**: Gradle, Android SDK

## 🚀 How to Run

### 1. Start the Python API
```bash
python betting_api.py
```


cd C:\Users\Bestg\AndroidStudioProjects\BettingPredictor; python betting_api.py


### 2. Install the Android app
```bash
cd NFL-Betting-Predictor
./gradlew installDebug
```

### 3. Connect from phone
- Phone and PC must be on same WiFi
- Update IP address in `MainActivity.kt` if needed
- API runs on port 5000

## 📡 API Endpoints
- `GET /test` - Test connection
- `GET /predict` - Get NFL predictions

## 🛠️ Build Requirements
- Android Studio Hedgehog | 2023.1.1+
- JDK 17
- Android SDK 34
- Python 3.8+ with Flask

## 📱 Phone Requirements
- Android 7.0 (API 24) or higher
- WiFi connection (same network as server)

## 📁 Project Structure
```
NFL-Betting-Predictor/
├── app/
│   └── src/
│       └── main/
│           ├── java/com/bestg/betting/
│           │   ├── MainActivity.kt
│           │   └── Prediction.kt
│           ├── res/
│           │   └── layout/
│           │       └── activity_main.xml
│           └── AndroidManifest.xml
├── betting_api.py
├── build.gradle.kts
└── README.md
```

## 🎯 Quick Start
1. Clone the repo: `git clone https://github.com/ObviousSatire/NFL-Betting-Predictor.git`
2. Start API: `cd C:\Users\Bestg\AndroidStudioProjects\BettingPredictor; python betting_api.py`
3. Build app: `./gradlew assembleDebug`
4. Install on phone: `adb install app/build/outputs/apk/debug/app-debug.apk`

## 🔗 Links
- **Repository**: https://github.com/ObviousSatire/NFL-Betting-Predictor
- **Issues**: https://github.com/ObviousSatire/NFL-Betting-Predictor/issues

---
⭐ Star this repo if you find it useful!

## **Share Commands:**

**To share with others:**
```bash
# Clone your project
git clone https://github.com/ObviousSatire/NFL-Betting-Predictor.git

# Enter directory
cd NFL-Betting-Predictor

# Run the API
python betting_api.py

# Build Android app
./gradlew assembleDebug
```

**Your GitHub repo is live at:** https://github.com/ObviousSatire/NFL-Betting-Predictor

# NFL Betting Predictor

Android app for NFL team stats, player stats, weather, injuries, news, and win predictions.

## Download
[Download Latest APK](NFL-Betting-Predictor.apk)

## Setup
Requires Python Flask server (betting_api.py) running on same network.
