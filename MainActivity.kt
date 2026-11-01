package com.lumora.camera

import android.Manifest
import android.content.ContentValues
import android.content.pm.PackageManager
import android.os.Bundle
import android.provider.MediaStore
import android.view.ViewGroup
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.Camera
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.video.MediaStoreOutputOptions
import androidx.camera.video.Quality
import androidx.camera.video.QualitySelector
import androidx.camera.video.Recorder
import androidx.camera.video.Recording
import androidx.camera.video.VideoCapture
import androidx.camera.video.VideoRecordEvent
import androidx.camera.view.PreviewView
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LocalLifecycleOwner
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = android.graphics.Color.BLACK
        window.navigationBarColor = android.graphics.Color.BLACK
        setContent { LumoraApp() }
    }
}

private enum class CaptureMode { PHOTO, VIDEO }

@Composable
private fun LumoraApp() {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    var permissionGranted by remember {
        mutableStateOf(listOf(Manifest.permission.CAMERA, Manifest.permission.RECORD_AUDIO)
            .all { ContextCompat.checkSelfPermission(context, it) == PackageManager.PERMISSION_GRANTED })
    }
    val permissionRequest = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { result -> permissionGranted = result[Manifest.permission.CAMERA] == true }

    LaunchedEffect(Unit) {
        if (!permissionGranted) permissionRequest.launch(arrayOf(Manifest.permission.CAMERA, Manifest.permission.RECORD_AUDIO))
    }

    var mode by remember { mutableStateOf(CaptureMode.PHOTO) }
    var lens by remember { mutableIntStateOf(CameraSelector.LENS_FACING_BACK) }
    var camera by remember { mutableStateOf<Camera?>(null) }
    var imageCapture by remember { mutableStateOf<ImageCapture?>(null) }
    var videoCapture by remember { mutableStateOf<VideoCapture<Recorder>?>(null) }
    var recording by remember { mutableStateOf<Recording?>(null) }
    var recordingActive by remember { mutableStateOf(false) }
    var zoom by remember { mutableFloatStateOf(1f) }
    var expandedModes by remember { mutableStateOf(false) }
    var status by remember { mutableStateOf("READY") }

    Box(Modifier.fillMaxSize().background(Color.Black)) {
        if (permissionGranted) {
            AndroidView(
                modifier = Modifier.fillMaxSize(),
                factory = { ctx ->
                    PreviewView(ctx).apply {
                        layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
                        scaleType = PreviewView.ScaleType.FILL_CENTER
                        implementationMode = PreviewView.ImplementationMode.COMPATIBLE
                    }
                },
                update = { previewView ->
                    val providerFuture = ProcessCameraProvider.getInstance(context)
                    providerFuture.addListener({
                        val provider = providerFuture.get()
                        val preview = Preview.Builder().build().also { it.surfaceProvider = previewView.surfaceProvider }
                        val capture = ImageCapture.Builder().setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY).build()
                        val recorder = Recorder.Builder().setQualitySelector(QualitySelector.from(Quality.FHD)).build()
                        val video = VideoCapture.withOutput(recorder)
                        val selector = CameraSelector.Builder().requireLensFacing(lens).build()
                        try {
                            provider.unbindAll()
                            camera = provider.bindToLifecycle(lifecycleOwner, selector, preview, capture, video)
                            imageCapture = capture
                            videoCapture = video
                            camera?.cameraControl?.setZoomRatio(zoom)
                        } catch (_: Exception) { status = "CAMERA UNAVAILABLE" }
                    }, ContextCompat.getMainExecutor(context))
                }
            )
        } else {
            Text("Camera permission is required", color = Color.White, modifier = Modifier.align(Alignment.Center))
        }

        // Top glass control strip
        Row(
            Modifier.align(Alignment.TopCenter).fillMaxWidth().padding(horizontal = 18.dp, vertical = 22.dp)
                .clip(RoundedCornerShape(28.dp)).background(Brush.horizontalGradient(listOf(Color.White.copy(.22f), Color.White.copy(.08f))))
                .padding(horizontal = 18.dp, vertical = 13.dp),
            horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically
        ) {
            GlassText("LUMORA", 14, FontWeight.Bold)
            GlassText(status, 10, FontWeight.Medium)
            GlassText("⚙", 22, FontWeight.Normal)
        }

        // Zoom readout and slider
        Column(Modifier.align(Alignment.CenterEnd).padding(end = 12.dp).width(54.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            GlassText(String.format(Locale.US, "%.1fx", zoom), 12, FontWeight.SemiBold)
            Slider(value = zoom, onValueChange = {
                zoom = it
                camera?.cameraControl?.setZoomRatio(it)
            }, valueRange = 1f..(camera?.cameraInfo?.zoomState?.value?.maxZoomRatio ?: 5f))
        }

        // Bottom camera deck: shutter above mode row
        Column(
            Modifier.align(Alignment.BottomCenter).fillMaxWidth()
                .background(Brush.verticalGradient(listOf(Color.Transparent, Color.Black.copy(.82f))))
                .padding(bottom = 28.dp, top = 70.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Row(Modifier.fillMaxWidth().padding(horizontal = 42.dp), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                GlassText("▧", 25, FontWeight.Normal)
                val shutterScale by animateFloatAsState(if (recordingActive) 1.12f else 1f, spring(), label = "shutter")
                Box(
                    Modifier.size(78.dp).scale(shutterScale).clip(CircleShape)
                        .background(Color.White.copy(.18f)).padding(5.dp)
                        .clip(CircleShape).background(if (recordingActive) Color.Red else Color.White)
                        .pointerInput(mode, recordingActive) {
                            detectTapGestures(onTap = {
                                if (mode == CaptureMode.PHOTO) {
                                    val name = "LUMORA_${SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())}.jpg"
                                    val values = ContentValues().apply { put(MediaStore.MediaColumns.DISPLAY_NAME, name); put(MediaStore.MediaColumns.MIME_TYPE, "image/jpeg") }
                                    val output = ImageCapture.OutputFileOptions.Builder(context.contentResolver, MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values).build()
                                    imageCapture?.takePicture(output, ContextCompat.getMainExecutor(context), object : ImageCapture.OnImageSavedCallback {
                                        override fun onImageSaved(result: ImageCapture.OutputFileResults) { status = "PHOTO SAVED" }
                                        override fun onError(exception: ImageCaptureException) { status = "PHOTO ERROR" }
                                    })
                                } else if (!recordingActive) {
                                    val values = ContentValues().apply {
                                        put(MediaStore.MediaColumns.DISPLAY_NAME, "LUMORA_${System.currentTimeMillis()}.mp4")
                                        put(MediaStore.MediaColumns.MIME_TYPE, "video/mp4")
                                    }
                                    val output = MediaStoreOutputOptions.Builder(context.contentResolver, MediaStore.Video.Media.EXTERNAL_CONTENT_URI).setContentValues(values).build()
                                    recording = videoCapture?.output?.prepareRecording(context, output)?.withAudioEnabled()?.start(ContextCompat.getMainExecutor(context)) { event ->
                                        if (event is VideoRecordEvent.Finalize) {
                                            recordingActive = false
                                            status = if (event.hasError()) "VIDEO ERROR" else "VIDEO SAVED"
                                        }
                                    }
                                    recordingActive = recording != null
                                    status = "RECORDING"
                                } else {
                                    recording?.stop(); recording = null
                                }
                            })
                        }
                )
                GlassText("↻", 27, FontWeight.Normal, modifier = Modifier.pointerInput(Unit) {
                    detectTapGestures(onTap = {
                        if (!recordingActive) lens = if (lens == CameraSelector.LENS_FACING_BACK) CameraSelector.LENS_FACING_FRONT else CameraSelector.LENS_FACING_BACK
                    })
                })
            }

            Spacer(Modifier.height(24.dp))
            Row(
                Modifier.clip(RoundedCornerShape(30.dp)).background(Color.White.copy(.13f)).padding(horizontal = 22.dp, vertical = 11.dp),
                horizontalArrangement = Arrangement.spacedBy(30.dp), verticalAlignment = Alignment.CenterVertically
            ) {
                ModeLabel("PHOTO", mode == CaptureMode.PHOTO) { mode = CaptureMode.PHOTO; status = "PHOTO MODE" }
                ModeLabel("VIDEO", mode == CaptureMode.VIDEO) { mode = CaptureMode.VIDEO; status = "VIDEO MODE" }
            }
            Spacer(Modifier.height(10.dp))
            GlassText("Hold mode selector for additional modes · Basic capture engine", 9, FontWeight.Normal)
        }
    }
}

@Composable
private fun ModeLabel(label: String, selected: Boolean, onClick: () -> Unit) {
    val color by animateColorAsState(if (selected) Color.White else Color.White.copy(.55f), label = "modeColor")
    Text(label, color = color, fontSize = 13.sp, fontWeight = if (selected) FontWeight.Bold else FontWeight.Medium,
        modifier = Modifier.pointerInput(label) { detectTapGestures(onTap = { onClick() }, onLongPress = { /* Additional mode tray is a planned next layer. */ }) })
}

@Composable
private fun GlassText(text: String, size: Int, weight: FontWeight, modifier: Modifier = Modifier) {
    Text(text, color = Color.White, fontSize = size.sp, fontWeight = weight, modifier = modifier)
}
