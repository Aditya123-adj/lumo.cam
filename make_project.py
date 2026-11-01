import os, zlib, struct

def w(path, text):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    open(path, 'w', encoding='utf-8').write(text)

w('settings.gradle', r'''pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.PREFER_SETTINGS)
    repositories {
        google()
        mavenCentral()
    }
}
rootProject.name = "LumoCamera"
include(":app")
''')
w('build.gradle', r'''plugins {
    id 'com.android.application' version '8.5.2' apply false
    id 'org.jetbrains.kotlin.android' version '1.9.24' apply false
}
''')
w('gradle.properties', '''org.gradle.jvmargs=-Xmx3g
android.useAndroidX=true
android.nonTransitiveRClass=true
kotlin.code.style=official
''')
w('app/build.gradle', r'''plugins {
    id 'com.android.application'
    id 'org.jetbrains.kotlin.android'
}
android {
    namespace 'com.lumo.cam'
    compileSdk 34
    defaultConfig {
        applicationId 'com.lumo.cam'
        minSdk 29
        targetSdk 34
        versionCode 2
        versionName '2.0-native'
    }
    compileOptions {
        sourceCompatibility JavaVersion.VERSION_17
        targetCompatibility JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = '17'
    }
}
dependencies {
    def camerax = '1.3.4'
    implementation 'androidx.core:core-ktx:1.13.1'
    implementation 'androidx.activity:activity-ktx:1.9.0'
    implementation "androidx.camera:camera-core:$camerax"
    implementation "androidx.camera:camera-camera2:$camerax"
    implementation "androidx.camera:camera-lifecycle:$camerax"
    implementation "androidx.camera:camera-view:$camerax"
    implementation "androidx.camera:camera-video:$camerax"
    implementation "androidx.camera:camera-extensions:$camerax"
}
''')
w('app/src/main/AndroidManifest.xml', r'''<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-permission android:name="android.permission.CAMERA"/>
    <uses-permission android:name="android.permission.RECORD_AUDIO"/>
    <uses-permission android:name="android.permission.VIBRATE"/>
    <uses-feature android:name="android.hardware.camera" android:required="false"/>
    <application
        android:label="Lumo Camera"
        android:icon="@mipmap/ic_launcher"
        android:allowBackup="true"
        android:hardwareAccelerated="true"
        android:theme="@android:style/Theme.Black.NoTitleBar.Fullscreen">
        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:screenOrientation="portrait"
            android:configChanges="orientation|screenSize|keyboardHidden|smallestScreenSize|screenLayout">
            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
        </activity>
    </application>
</manifest>
''')
w('app/src/main/java/com/lumo/cam/MainActivity.kt', r'''package com.lumo.cam

import android.Manifest
import android.annotation.SuppressLint
import android.content.ContentValues
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.MediaStore
import android.util.Range
import android.util.Size
import android.view.GestureDetector
import android.view.Gravity
import android.view.MotionEvent
import android.view.ScaleGestureDetector
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.SeekBar
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.Camera
import androidx.camera.core.CameraSelector
import androidx.camera.core.FocusMeteringAction
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.Preview
import androidx.camera.extensions.ExtensionMode
import androidx.camera.extensions.ExtensionsManager
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.video.FallbackStrategy
import androidx.camera.video.MediaStoreOutputOptions
import androidx.camera.video.Quality
import androidx.camera.video.QualitySelector
import androidx.camera.video.Recorder
import androidx.camera.video.Recording
import androidx.camera.video.VideoCapture
import androidx.camera.video.VideoRecordEvent
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import kotlin.math.cos
import kotlin.math.ln
import kotlin.math.pow
import kotlin.math.sin

class MainActivity : ComponentActivity() {
    enum class M(val label: String) { PHOTO("PHOTO"), PORTRAIT("PORTRAIT"), NIGHT("NIGHT"), VIDEO("VIDEO"), POSE("POSE") }

    private lateinit var pv: PreviewView
    private lateinit var gridV: View
    private lateinit var poseImg: ImageView
    private lateinit var ring: View
    private lateinit var info: TextView
    private lateinit var count: TextView
    private lateinit var thumb: ImageView
    private lateinit var inner: View
    private lateinit var flashT: TextView
    private lateinit var timerT: TextView
    private lateinit var gridT: TextView
    private lateinit var qT: TextView
    private lateinit var lensRow: LinearLayout
    private lateinit var modeRow: LinearLayout
    private lateinit var poseBar: LinearLayout
    private lateinit var arc: ArcView
    private val main by lazy { ContextCompat.getMainExecutor(this) }
    private val handler = Handler(Looper.getMainLooper())
    private var provider: ProcessCameraProvider? = null
    private var ext: ExtensionsManager? = null
    private var camera: Camera? = null
    private var imageCap: ImageCapture? = null
    private var videoCap: VideoCapture<Recorder>? = null
    private var recording: Recording? = null
    private var mode = M.PHOTO
    private var front = false
    private var flash = 0
    private var timerS = 0
    private var vq = 1
    private var zoom = 1f
    private var minZ = 1f
    private var maxZ = 1f
    private var lastUri: Uri? = null
    private val vqList = listOf(
        Triple("HD 30", Quality.HD, 30), Triple("FHD 30", Quality.FHD, 30), Triple("FHD 60", Quality.FHD, 60),
        Triple("4K 30", Quality.UHD, 30), Triple("4K 60", Quality.UHD, 60)
    )
    private val yellow = Color.rgb(255, 214, 10)

    private val reqPerm = registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { r ->
        if (r[Manifest.permission.CAMERA] == true) startCamera() else info("Camera permission do")
    }
    private val pickPose = registerForActivityResult(ActivityResultContracts.GetContent()) { u ->
        if (u != null) { poseImg.setImageURI(u); poseImg.visibility = View.VISIBLE }
    }

    private fun dp(n: Int) = (n * resources.displayMetrics.density).toInt()

    private fun glass(v: View, r: Int = 40) {
        v.background = GradientDrawable().apply {
            cornerRadius = dp(r).toFloat()
            setColor(Color.argb(55, 255, 255, 255))
            setStroke(dp(1), Color.argb(120, 255, 255, 255))
        }
    }

    private fun tv(t: String, size: Float = 12f) = TextView(this).apply {
        text = t; setTextColor(Color.WHITE); textSize = size; typeface = Typeface.DEFAULT_BOLD
        letterSpacing = 0.08f; gravity = Gravity.CENTER; setPadding(dp(12), dp(8), dp(12), dp(8))
    }

    private fun info(t: String) {
        info.text = t; info.visibility = View.VISIBLE; info.alpha = 1f
        info.animate().cancel()
        info.animate().alpha(0f).setStartDelay(1800).setDuration(400).withEndAction { info.visibility = View.GONE }.start()
    }

    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        window.attributes.layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES
        @Suppress("DEPRECATION")
        window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY or View.SYSTEM_UI_FLAG_FULLSCREEN or
            View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or View.SYSTEM_UI_FLAG_LAYOUT_STABLE or
            View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN or View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
        buildUi()
        val need = arrayOf(Manifest.permission.CAMERA, Manifest.permission.RECORD_AUDIO)
        if (need.all { checkSelfPermission(it) == PackageManager.PERMISSION_GRANTED }) startCamera() else reqPerm.launch(need)
    }

    @SuppressLint("ClickableViewAccessibility")
    private fun buildUi() {
        val root = FrameLayout(this).apply { setBackgroundColor(Color.BLACK) }
        setContentView(root)
        pv = PreviewView(this).apply { scaleType = PreviewView.ScaleType.FILL_CENTER }
        root.addView(pv, FrameLayout.LayoutParams(-1, -1))
        gridV = object : View(this) {
            val p = Paint().apply { color = Color.argb(110, 255, 255, 255); strokeWidth = 2f }
            override fun onDraw(c: Canvas) {
                for (i in 1..2) {
                    c.drawLine(width * i / 3f, 0f, width * i / 3f, height.toFloat(), p)
                    c.drawLine(0f, height * i / 3f, width.toFloat(), height * i / 3f, p)
                }
            }
        }.apply { visibility = View.GONE }
        root.addView(gridV, FrameLayout.LayoutParams(-1, -1))
        poseImg = ImageView(this).apply { alpha = 0.4f; visibility = View.GONE; scaleType = ImageView.ScaleType.FIT_CENTER }
        root.addView(poseImg, FrameLayout.LayoutParams(-1, -1))
        var lx = 0f; var ly = 0f
        poseImg.setOnTouchListener { v, e ->
            when (e.actionMasked) {
                MotionEvent.ACTION_DOWN -> { lx = e.rawX; ly = e.rawY }
                MotionEvent.ACTION_MOVE -> { v.translationX += e.rawX - lx; v.translationY += e.rawY - ly; lx = e.rawX; ly = e.rawY }
            }
            true
        }
        ring = View(this).apply {
            visibility = View.GONE
            background = GradientDrawable().apply { setColor(Color.TRANSPARENT); setStroke(dp(2), yellow); cornerRadius = dp(8).toFloat() }
        }
        root.addView(ring, FrameLayout.LayoutParams(dp(76), dp(76)))
        arc = ArcView().apply { visibility = View.GONE }
        root.addView(arc, FrameLayout.LayoutParams(-1, dp(170)).apply { gravity = Gravity.BOTTOM; bottomMargin = dp(150) })
        info = tv("", 13f).apply { visibility = View.GONE }
        glass(info, 20)
        root.addView(info, FrameLayout.LayoutParams(-2, -2).apply { gravity = Gravity.TOP or Gravity.CENTER_HORIZONTAL; topMargin = dp(100) })
        count = TextView(this).apply { textSize = 110f; setTextColor(Color.WHITE); gravity = Gravity.CENTER; visibility = View.GONE }
        root.addView(count, FrameLayout.LayoutParams(-1, -1))

        val top = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER }
        flashT = tv("FLASH OFF"); timerT = tv("TIMER OFF"); gridT = tv("GRID"); qT = tv("FHD 30"); qT.visibility = View.GONE
        for (t in listOf(flashT, timerT, gridT, qT)) {
            glass(t, 20)
            top.addView(t, LinearLayout.LayoutParams(-2, -2).apply { marginStart = dp(4); marginEnd = dp(4) })
        }
        root.addView(top, FrameLayout.LayoutParams(-1, -2).apply { gravity = Gravity.TOP; topMargin = dp(36) })
        flashT.setOnClickListener {
            flash = (flash + 1) % 3
            flashT.text = listOf("FLASH OFF", "FLASH ON", "FLASH AUTO")[flash]
            imageCap?.flashMode = listOf(ImageCapture.FLASH_MODE_OFF, ImageCapture.FLASH_MODE_ON, ImageCapture.FLASH_MODE_AUTO)[flash]
            if (mode == M.VIDEO) camera?.cameraControl?.enableTorch(flash == 1)
        }
        timerT.setOnClickListener { timerS = when (timerS) { 0 -> 3; 3 -> 10; else -> 0 }; timerT.text = if (timerS == 0) "TIMER OFF" else "TIMER ${timerS}S" }
        gridT.setOnClickListener { gridV.visibility = if (gridV.visibility == View.VISIBLE) View.GONE else View.VISIBLE }
        qT.setOnClickListener { if (recording == null) { vq = (vq + 1) % vqList.size; qT.text = vqList[vq].first; bind() } }

        val bottom = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER_HORIZONTAL }
        poseBar = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; visibility = View.GONE; setPadding(dp(16), dp(8), dp(16), dp(8)) }
        glass(poseBar, 24)
        val add = tv("ADD POSE PHOTO"); add.setOnClickListener { pickPose.launch("image/*") }
        poseBar.addView(add)
        fun seek(init: Int, cb: (Int) -> Unit) = SeekBar(this).apply {
            max = 100; progress = init
            setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
                override fun onProgressChanged(s: SeekBar?, p: Int, u: Boolean) = cb(p)
                override fun onStartTrackingTouch(s: SeekBar?) {}
                override fun onStopTrackingTouch(s: SeekBar?) {}
            })
        }
        poseBar.addView(seek(40) { poseImg.alpha = it / 100f }, LinearLayout.LayoutParams(dp(240), -2))
        poseBar.addView(seek(50) { poseImg.scaleX = 0.4f + it / 60f; poseImg.scaleY = 0.4f + it / 60f }, LinearLayout.LayoutParams(dp(240), -2))
        bottom.addView(poseBar, LinearLayout.LayoutParams(-2, -2).apply { bottomMargin = dp(8) })

        lensRow = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        glass(lensRow, 30)
        for (t in listOf("0.5", "1", "2")) lensRow.addView(tv(t, 12f).apply { setPadding(0, 0, 0, 0) }, LinearLayout.LayoutParams(dp(44), dp(40)))
        bottom.addView(lensRow, LinearLayout.LayoutParams(-2, -2).apply { bottomMargin = dp(14) })
        var arcOn = false
        val lp = Runnable { arcOn = true; arc.visibility = View.VISIBLE; arc.f = fracOf(zoom); arc.invalidate() }
        lensRow.setOnTouchListener { v, e ->
            when (e.actionMasked) {
                MotionEvent.ACTION_DOWN -> { arcOn = false; handler.postDelayed(lp, 300) }
                MotionEvent.ACTION_MOVE -> if (arcOn) {
                    val loc = IntArray(2); arc.getLocationOnScreen(loc)
                    val f = ((e.rawX - loc[0]) / arc.width).coerceIn(0f, 1f)
                    arc.f = f; arc.invalidate(); setZoom(0.5f * 20f.pow(f))
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                    handler.removeCallbacks(lp)
                    if (arcOn) { arc.visibility = View.GONE; arcOn = false }
                    else if (e.actionMasked == MotionEvent.ACTION_UP) {
                        val i = (e.x / (v.width / 3f)).toInt().coerceIn(0, 2)
                        setZoom(listOf(0.5f, 1f, 2f)[i])
                    }
                }
            }
            true
        }

        val cap = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
        thumb = ImageView(this).apply { scaleType = ImageView.ScaleType.CENTER_CROP; clipToOutline = true }
        thumb.background = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(Color.argb(60, 255, 255, 255)) }
        thumb.outlineProvider = object : android.view.ViewOutlineProvider() {
            override fun getOutline(v: View, o: android.graphics.Outline) { o.setOval(0, 0, v.width, v.height) }
        }
        thumb.setOnClickListener { lastUri?.let { u -> startActivity(Intent(Intent.ACTION_VIEW, u).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)) } }
        val tw = FrameLayout(this); tw.addView(thumb, FrameLayout.LayoutParams(dp(52), dp(52), Gravity.START))
        cap.addView(tw, LinearLayout.LayoutParams(0, dp(52), 1f))
        val shutter = FrameLayout(this)
        shutter.background = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(Color.TRANSPARENT); setStroke(dp(4), Color.WHITE) }
        inner = View(this).apply { background = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(Color.WHITE) } }
        shutter.addView(inner, FrameLayout.LayoutParams(dp(60), dp(60), Gravity.CENTER))
        shutter.setOnClickListener { onShutter() }
        cap.addView(shutter, LinearLayout.LayoutParams(dp(78), dp(78)))
        val flip = tv("FLIP"); glass(flip, 26)
        flip.setOnClickListener { front = !front; bind(); refreshModes() }
        val fw = FrameLayout(this); fw.addView(flip, FrameLayout.LayoutParams(dp(60), dp(52), Gravity.END))
        cap.addView(fw, LinearLayout.LayoutParams(0, dp(52), 1f))
        bottom.addView(cap, LinearLayout.LayoutParams(-1, -2).apply { marginStart = dp(24); marginEnd = dp(24); bottomMargin = dp(14) })

        val gdm = GestureDetector(this, object : GestureDetector.SimpleOnGestureListener() {
            override fun onFling(a: MotionEvent?, b: MotionEvent, vx: Float, vy: Float): Boolean {
                val l = visibleModes(); val i = l.indexOf(mode)
                if (vx < -600 && i < l.size - 1) setMode(l[i + 1]) else if (vx > 600 && i > 0) setMode(l[i - 1])
                return true
            }
        })
        modeRow = object : LinearLayout(this) {
            override fun onInterceptTouchEvent(e: MotionEvent): Boolean { gdm.onTouchEvent(e); return false }
        }.apply { orientation = HORIZONTAL; gravity = Gravity.CENTER }
        glass(modeRow, 30)
        bottom.addView(modeRow, LinearLayout.LayoutParams(-2, -2).apply { bottomMargin = dp(26) })
        root.addView(bottom, FrameLayout.LayoutParams(-1, -2).apply { gravity = Gravity.BOTTOM })

        val sg = ScaleGestureDetector(this, object : ScaleGestureDetector.SimpleOnScaleGestureListener() {
            override fun onScale(d: ScaleGestureDetector): Boolean { setZoom(zoom * d.scaleFactor); return true }
        })
        val gd = GestureDetector(this, object : GestureDetector.SimpleOnGestureListener() {
            override fun onDown(e: MotionEvent) = true
            override fun onSingleTapUp(e: MotionEvent): Boolean { focus(e.x, e.y, false); return true }
            override fun onLongPress(e: MotionEvent) { focus(e.x, e.y, true) }
        })
        pv.setOnTouchListener { _, e -> sg.onTouchEvent(e); if (!sg.isInProgress) gd.onTouchEvent(e); true }
        refreshModes()
    }

    private fun fracOf(z: Float) = (ln(z / 0.5f) / ln(20f)).coerceIn(0f, 1f)

    private fun setZoom(z: Float) {
        val c = camera ?: return
        if (z < minZ - 0.01f) info("${if (z < 1f) "0.5x" else "Ye zoom"} is phone me nahi")
        c.cameraControl.setZoomRatio(z.coerceIn(minZ, maxZ))
    }

    private fun focus(x: Float, y: Float, lock: Boolean) {
        val c = camera ?: return
        val p = pv.meteringPointFactory.createPoint(x, y)
        val a = FocusMeteringAction.Builder(p).apply { if (lock) disableAutoCancel() }.build()
        c.cameraControl.startFocusAndMetering(a)
        ring.x = x - dp(38); ring.y = y - dp(38); ring.visibility = View.VISIBLE
        ring.scaleX = 1.5f; ring.scaleY = 1.5f; ring.alpha = 1f
        ring.animate().cancel()
        ring.animate().scaleX(1f).scaleY(1f).setDuration(220).start()
        if (lock) info("AE/AF LOCK")
        else ring.animate().alpha(0f).setStartDelay(1200).setDuration(300).start()
    }

    private fun has(x: Int): Boolean {
        val e = ext ?: return false
        val s = if (front) CameraSelector.DEFAULT_FRONT_CAMERA else CameraSelector.DEFAULT_BACK_CAMERA
        return try { e.isExtensionAvailable(s, x) } catch (t: Throwable) { false }
    }

    private fun visibleModes() = M.values().filter {
        (it != M.PORTRAIT || has(ExtensionMode.BOKEH)) && (it != M.NIGHT || has(ExtensionMode.NIGHT))
    }

    private fun refreshModes() {
        modeRow.removeAllViews()
        for (m in visibleModes()) modeRow.addView(tv(m.label).apply {
            setTextColor(if (m == mode) yellow else Color.WHITE)
            setOnClickListener { setMode(m) }
        })
    }

    private fun setMode(m: M) {
        if (recording != null || m == mode) return
        mode = m
        val pose = m == M.POSE
        poseBar.visibility = if (pose) View.VISIBLE else View.GONE
        poseImg.visibility = if (pose && poseImg.drawable != null) View.VISIBLE else View.GONE
        qT.visibility = if (m == M.VIDEO) View.VISIBLE else View.GONE
        (inner.background as GradientDrawable).setColor(if (m == M.VIDEO) Color.rgb(255, 69, 58) else Color.WHITE)
        refreshModes(); bind()
    }

    private fun startCamera() {
        val f = ProcessCameraProvider.getInstance(this)
        f.addListener({
            provider = f.get()
            val ef = ExtensionsManager.getInstanceAsync(this, provider!!)
            ef.addListener({ ext = ef.get(); refreshModes(); bind() }, main)
        }, main)
    }

    private fun bind() {
        val pr = provider ?: return
        pr.unbindAll()
        var sel = if (front) CameraSelector.DEFAULT_FRONT_CAMERA else CameraSelector.DEFAULT_BACK_CAMERA
        val preview = Preview.Builder().build().also { it.setSurfaceProvider(pv.surfaceProvider) }
        try {
            if (mode == M.VIDEO) {
                val q = vqList[vq]
                val rec = Recorder.Builder().setQualitySelector(QualitySelector.from(q.second, FallbackStrategy.lowerQualityOrHigherThan(q.second))).build()
                videoCap = VideoCapture.Builder(rec).setTargetFrameRate(Range(q.third, q.third)).build()
                camera = pr.bindToLifecycle(this, sel, preview, videoCap!!)
            } else {
                val e = ext
                if (e != null && mode == M.PORTRAIT && has(ExtensionMode.BOKEH)) sel = e.getExtensionEnabledCameraSelector(sel, ExtensionMode.BOKEH)
                if (e != null && mode == M.NIGHT && has(ExtensionMode.NIGHT)) sel = e.getExtensionEnabledCameraSelector(sel, ExtensionMode.NIGHT)
                imageCap = ImageCapture.Builder().setCaptureMode(ImageCapture.CAPTURE_MODE_MAXIMIZE_QUALITY)
                    .setFlashMode(listOf(ImageCapture.FLASH_MODE_OFF, ImageCapture.FLASH_MODE_ON, ImageCapture.FLASH_MODE_AUTO)[flash]).build()
                camera = pr.bindToLifecycle(this, sel, preview, imageCap!!)
            }
        } catch (t: Throwable) {
            info("Camera mode start nahi hua"); return
        }
        val zl = camera!!.cameraInfo.zoomState
        zl.removeObservers(this)
        zl.observe(this) { zs ->
            zoom = zs.zoomRatio; minZ = zs.minZoomRatio; maxZ = zs.maxZoomRatio; paintZoom()
        }
    }

    private fun paintZoom() {
        val presets = listOf(0.5f, 1f, 2f)
        var act = 0
        presets.forEachIndexed { i, p -> if (zoom >= p - 0.01f) act = i }
        for (i in 0 until lensRow.childCount) {
            val t = lensRow.getChildAt(i) as TextView
            val isAct = i == act
            t.text = if (isAct && Math.abs(zoom - presets[i]) > 0.05f) String.format("%.1f", zoom) else listOf("0.5", "1", "2")[i]
            t.setTextColor(if (isAct) yellow else Color.WHITE)
        }
    }

    private fun onShutter() {
        if (mode == M.VIDEO) { toggleRecord(); return }
        if (timerS == 0) { takePhoto(); return }
        var n = timerS
        count.visibility = View.VISIBLE
        val tick = object : Runnable {
            override fun run() {
                if (n > 0) { count.text = n.toString(); n--; handler.postDelayed(this, 1000) }
                else { count.visibility = View.GONE; takePhoto() }
            }
        }
        tick.run()
    }

    private fun takePhoto() {
        val ic = imageCap ?: return
        val cv = ContentValues().apply {
            put(MediaStore.MediaColumns.DISPLAY_NAME, "IMG_" + System.currentTimeMillis())
            put(MediaStore.MediaColumns.MIME_TYPE, "image/jpeg")
            put(MediaStore.MediaColumns.RELATIVE_PATH, "Pictures/Lumo")
        }
        val o = ImageCapture.OutputFileOptions.Builder(contentResolver, MediaStore.Images.Media.EXTERNAL_CONTENT_URI, cv).build()
        pv.animate().alpha(0.3f).setDuration(70).withEndAction { pv.animate().alpha(1f).setDuration(120).start() }.start()
        ic.takePicture(o, main, object : ImageCapture.OnImageSavedCallback {
            override fun onImageSaved(r: ImageCapture.OutputFileResults) { r.savedUri?.let { setThumb(it) } }
            override fun onError(e: ImageCaptureException) { info("Photo save nahi hui") }
        })
    }

    @SuppressLint("MissingPermission")
    private fun toggleRecord() {
        val r = recording
        if (r != null) { r.stop(); return }
        val vc = videoCap ?: return
        val cv = ContentValues().apply {
            put(MediaStore.MediaColumns.DISPLAY_NAME, "VID_" + System.currentTimeMillis())
            put(MediaStore.MediaColumns.MIME_TYPE, "video/mp4")
            put(MediaStore.MediaColumns.RELATIVE_PATH, "Movies/Lumo")
        }
        val mo = MediaStoreOutputOptions.Builder(contentResolver, MediaStore.Video.Media.EXTERNAL_CONTENT_URI).setContentValues(cv).build()
        var p = vc.output.prepareRecording(this, mo)
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) p = p.withAudioEnabled()
        if (flash == 1) camera?.cameraControl?.enableTorch(true)
        inner.animate().scaleX(0.5f).scaleY(0.5f).setDuration(200).start()
        recording = p.start(main) { ev ->
            if (ev is VideoRecordEvent.Finalize) {
                recording = null
                camera?.cameraControl?.enableTorch(false)
                inner.animate().scaleX(1f).scaleY(1f).setDuration(200).start()
                if (!ev.hasError()) setThumb(ev.outputResults.outputUri) else info("Video save nahi hui")
            }
        }
    }

    private fun setThumb(u: Uri) {
        lastUri = u
        try { thumb.setImageBitmap(contentResolver.loadThumbnail(u, Size(220, 220), null)) } catch (t: Throwable) { }
        thumb.animate().scaleX(1.25f).scaleY(1.25f).setDuration(150).withEndAction { thumb.animate().scaleX(1f).scaleY(1f).setDuration(200).start() }.start()
    }

    inner class ArcView : View(this@MainActivity) {
        var f = 0f
        private val p = Paint(Paint.ANTI_ALIAS_FLAG)
        override fun onDraw(c: Canvas) {
            val w = width.toFloat(); val h = height.toFloat()
            val r = w * 0.8f; val cx = w / 2; val cy = h * 0.9f + r - h * 0.5f
            p.style = Paint.Style.FILL; p.color = Color.argb(110, 0, 0, 0); c.drawCircle(cx, cy, r, p)
            p.style = Paint.Style.STROKE; p.strokeWidth = 3f; p.color = Color.argb(170, 255, 255, 255); c.drawCircle(cx, cy, r, p)
            p.textAlign = Paint.Align.CENTER; p.textSize = 30f; p.style = Paint.Style.FILL
            for (z in listOf(0.5f, 1f, 2f, 3f, 5f, 10f)) {
                val a = Math.toRadians(-140.0 + 100.0 * (ln(z / 0.5f) / ln(20f)))
                val x1 = cx + (r * cos(a)).toFloat(); val y1 = cy + (r * sin(a)).toFloat()
                val x2 = cx + ((r - 22) * cos(a)).toFloat(); val y2 = cy + ((r - 22) * sin(a)).toFloat()
                p.strokeWidth = 3f; p.color = Color.WHITE; c.drawLine(x1, y1, x2, y2, p)
                val x3 = cx + ((r - 56) * cos(a)).toFloat(); val y3 = cy + ((r - 56) * sin(a)).toFloat()
                c.drawText(if (z == 0.5f) ".5" else z.toInt().toString(), x3, y3, p)
            }
            val a = Math.toRadians(-140.0 + 100.0 * f)
            p.color = yellow
            c.drawCircle(cx + ((r - 11) * cos(a)).toFloat(), cy + ((r - 11) * sin(a)).toFloat(), 11f, p)
            p.textSize = 44f
            c.drawText(String.format("%.1fx", 0.5f * 20f.pow(f)), w / 2, h * 0.32f, p)
        }
    }
}
''')

def png(n):
    raw = bytearray()
    c = n / 2.0
    for y in range(n):
        raw.append(0)
        for x in range(n):
            d = ((x - c) ** 2 + (y - c) ** 2) ** .5
            if .31 * n <= d <= .37 * n: px = (255, 214, 10, 255)
            elif d <= .09 * n: px = (40, 40, 60, 255)
            elif d <= .2 * n: px = (255, 255, 255, 255)
            else: px = (28, 28, 46, 255)
            raw.extend(px)
    def ch(t, data):
        cc = struct.pack('>I', len(data)) + t + data
        return cc + struct.pack('>I', zlib.crc32(t + data) & 0xffffffff)
    return b'\x89PNG\r\n\x1a\n' + ch(b'IHDR', struct.pack('>IIBBBBB', n, n, 8, 6, 0, 0, 0)) + ch(b'IDAT', zlib.compress(bytes(raw), 9)) + ch(b'IEND', b'')

for d in ('mipmap-xxxhdpi', 'mipmap-xhdpi', 'mipmap-mdpi'):
    os.makedirs('app/src/main/res/' + d, exist_ok=True)
    open('app/src/main/res/' + d + '/ic_launcher.png', 'wb').write(png(192))
print('Native project generated')
