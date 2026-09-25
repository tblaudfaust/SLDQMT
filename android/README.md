# Field Monitor tablet app (Android)

Kotlin · Jetpack Compose · Room (SQLCipher) · WorkManager · Retrofit · Hilt · Fused Location.

## Build

Verified on 24 September 2026 with Android Studio 2026.1.4 (bundled JDK 25), Gradle 9.1, AGP 8.13,
Kotlin 2.2.20: `assembleDebug` and `testDebugUnitTest` pass.

1. Install Android Studio and complete its setup wizard so the SDK lands in
   `%LOCALAPPDATA%\Android\Sdk` (`local.properties` points there; adjust if yours differs).
2. Either open the `android` folder in Studio and press Run, or build from a terminal:

```bash
cd android
JAVA_HOME="C:\Program Files\Android\Android Studio\jbr" ./gradlew assembleDebug
```

   The APK lands in `app/build/outputs/apk/debug/app-debug.apk`.
3. Set the server URL in `app/build.gradle.kts` (`API_BASE_URL`). The debug build points at
   `http://localhost:8000/api/v1/` on the device; forward that to the PC's server with
   `adb reverse tcp:8000 tcp:8000` (works for USB tablets and emulators alike). The release build
   uses the VPS URL.
4. Run on an emulator or a tablet with USB debugging. First login needs the server reachable.

Release: Build → Generate Signed Bundle / APK. Side-load the APK or publish on a private
managed Google Play track.

## How it works

- Every screen reads and writes Room. New errors, follow-ups and status changes are saved with
  `pending = true`; `SyncWorker` pushes them and clears the flag only when the server's receipt says
  `applied` or `duplicate`. Rejected records keep a `syncError` and show on the Sync screen.
- Sync runs every 15 minutes, five seconds after any change, and on "Sync now". Pull brings the
  monitor's own records (so a second tablet restores everything) plus reference lists and settings.
- `ReminderWorker` runs every 15 minutes and posts one notification when unresolved errors are past
  their follow-up time, outside quiet hours. The follow-up interval (4 h) and quiet hours come from
  the server's settings and are applied on the tablet with the same rule as the server.
- PIN unlock: after an online login the monitor sets a 6-digit PIN; it is stored as a PBKDF2 hash in
  Keystore-backed EncryptedSharedPreferences. Five wrong PINs wipe the session (data stays encrypted
  on disk until the next online login). Offline sessions expire after `offline_days` (default 14).
- GPS: `LocationHelper` takes one high-accuracy Fused Location fix; under 30 m is marked good.

## Layout

```
app/src/main/java/sl/gov/statistics/fieldmonitor/
  FieldMonitorApp.kt       Hilt app, WorkManager config, notification channels
  MainActivity.kt
  data/SessionStore.kt     tokens, PIN, DB passphrase (encrypted prefs)
  data/local/              Room entities, DAOs, database
  data/remote/             Retrofit API, DTOs, auth interceptor + token refresh
  data/repo/               Auth, Error, Reference repositories
  sync/SyncEngine.kt       push/pull
  sync/Workers.kt          SyncWorker, ReminderWorker, SyncScheduler
  ui/                      theme, navigation, components, screens
  util/                    Time (follow-up rule), LocationHelper
```
