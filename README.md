# LUMORA CAMERA — Android source project

Native Android project using Kotlin, Jetpack Compose and CameraX.

## Included in this starter foundation
- Native CameraX live preview
- Photo capture to MediaStore
- Video recording to MediaStore (with audio permission)
- Front/back lens switching
- Camera zoom control
- PHOTO / VIDEO mode selector below the shutter
- Animated basic glass-like control surfaces

## Important implementation status
This is an initial source foundation, not a finished release APK. It has not been compiled or tested on a Vivo T4 5G in this environment. Advanced features from the agreed specification (true Night processing, Portrait segmentation, Panorama, Super Moon, Pro controls, slow motion/time-lapse, pose overlay, gallery browser, filter pipeline, curved long-press zoom arc, and full Liquid Glass interaction system) are not implemented yet. They require additional Camera2 capability checks and device testing; this project intentionally does not pretend they are already functional.

## Build
Open this folder in Android Studio with Android SDK 35 installed, allow Gradle sync, then Build > Build APK(s). The environment used to create this source archive did not contain Android SDK, Gradle, or adb, so no APK could be compiled or verified here.
