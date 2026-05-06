<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  ArrowLeft,
  ArrowRight,
  Camera,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Expand,
  FileUp,
  Hand,
  Loader2,
  Maximize2,
  Mic,
  Minus,
  Monitor,
  Pause,
  PenLine,
  Settings,
  Square,
  UploadCloud,
  Video,
  X,
} from 'lucide-vue-next'

type Slide = {
  index: number
  url: string
  width: number
  height: number
}

type PresentationManifest = {
  id: string
  filename: string
  slideCount: number
  conversionMode: 'powerpoint' | 'text-fallback' | string
  slides: Slide[]
}

type ToolMode = 'pointer' | 'pen' | 'zoom'

type Point = {
  x: number
  y: number
}

type AnnotationLine = {
  id: number
  points: Point[]
}

type VisionResult = {
  status: string
  latencyMs: number
  face?: {
    box: { x: number; y: number; width: number; height: number }
    center: Point
    confidence: number
    distanceMeters: number
  } | null
  hand?: {
    center: Point
    box: { x: number; y: number; width: number; height: number }
    pose: string
    confidence: number
    source?: string
    fingers?: Record<string, boolean>
  } | null
  gesture?: {
    name: string
    action: 'next' | 'previous' | 'pointer' | 'open_hand'
    confidence: number
  } | null
  debug?: {
    mediapipeAvailable?: boolean
    mediapipeError?: string | null
    opencvAvailable?: boolean
    opencvError?: string | null
    handSource?: string | null
    pageTurnCooldownSeconds?: number
    pageTurnPoseMatched?: boolean
    pageTurnHoldProgress?: number
    pageTurnHoldSeconds?: number
    pageTurnArmed?: boolean
    pageTurnCooldownRemaining?: number
  } | null
}

type VisionSettings = {
  cooldownSeconds: number
  swipeThreshold: number
  confidenceThreshold: number
}

type SpeechRecognitionLike = {
  lang: string
  continuous: boolean
  interimResults: boolean
  onresult: ((event: any) => void) | null
  onend: (() => void) | null
  onerror: (() => void) | null
  start: () => void
  stop: () => void
}

declare global {
  interface Window {
    SpeechRecognition?: new () => SpeechRecognitionLike
    webkitSpeechRecognition?: new () => SpeechRecognitionLike
  }
}

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

const fileInput = ref<HTMLInputElement | null>(null)
const stageRef = ref<HTMLElement | null>(null)
const videoRef = ref<HTMLVideoElement | null>(null)
const debugVideoRef = ref<HTMLVideoElement | null>(null)
const frameCanvasRef = ref<HTMLCanvasElement | null>(null)
const cameraStream = ref<MediaStream | null>(null)
const deck = ref<PresentationManifest | null>(null)
const currentIndex = ref(0)
const demoIndex = ref(7)
const activeMode = ref<ToolMode>('pointer')
const elapsedSeconds = ref(522)
const isUploading = ref(false)
const isDragging = ref(false)
const recognitionPaused = ref(false)
const cameraEnabled = ref(false)
const cameraError = ref('')
const errorMessage = ref('')
const visionResult = ref<VisionResult | null>(null)
const visionStatus = ref('视觉待机')
const pointerPosition = ref<Point>({ x: 0.72, y: 0.58 })
const zoomPoint = ref<Point>({ x: 0.72, y: 0.55 })
const annotations = ref<AnnotationLine[]>([])
const drawingLine = ref<AnnotationLine | null>(null)
const voiceEnabled = ref(false)
const voiceSupported = ref(true)
const lastVoiceText = ref('等待语音')
const speechRecognition = ref<SpeechRecognitionLike | null>(null)
const showEndConfirm = ref(false)
const pendingEndByVoice = ref(false)
const showSettings = ref(false)
const externalControlEnabled = ref(false)
const visionSettings = ref<VisionSettings>({
  cooldownSeconds: 5,
  swipeThreshold: 0.14,
  confidenceThreshold: 0.45,
})

let timerId: number | undefined
let visionTimerId: number | undefined
let annotationId = 0
let lastCommandAt = 0

const currentSlide = computed(() => deck.value?.slides[currentIndex.value] ?? null)
const hasDeck = computed(() => Boolean(deck.value?.slides.length))
const filename = computed(() => deck.value?.filename || '人工智能进展与未来趋势.pptx')
const slideCount = computed(() => deck.value?.slideCount ?? 13)
const displayIndex = computed(() => (hasDeck.value ? currentIndex.value + 1 : demoIndex.value + 1))
const progress = computed(() => (displayIndex.value / slideCount.value) * 100)
const conversionLabel = computed(() => {
  if (!deck.value) return '原型演示'
  return deck.value.conversionMode === 'powerpoint' ? '原始放映页' : '文本预览页'
})
const elapsedText = computed(() => {
  const hours = Math.floor(elapsedSeconds.value / 3600)
  const minutes = Math.floor((elapsedSeconds.value % 3600) / 60)
  const seconds = elapsedSeconds.value % 60
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
})
const modeText = computed(() => {
  if (activeMode.value === 'pen') return '标注模式'
  if (activeMode.value === 'zoom') return '区域放大'
  return '空气指针'
})
const cameraStatusText = computed(() => {
  if (cameraEnabled.value) return '摄像头已开启'
  if (cameraError.value) return '摄像头模拟中'
  return '点击开启摄像头'
})
const faceStatusText = computed(() => {
  if (!cameraEnabled.value && !cameraError.value) return '等待摄像头'
  if (cameraError.value) return '模拟人脸锁定 96%'
  return '人脸锁定 96%'
})
const distanceText = computed(() => {
  const distance = visionResult.value?.face?.distanceMeters
  return `距离 ${distance ? distance.toFixed(1) : '2.8'}m`
})
const gestureText = computed(() => {
  const gesture = visionResult.value?.gesture
  if (gesture?.action === 'next') return '激活手势挥动：下一页'
  if (visionResult.value?.debug?.pageTurnArmed) return '翻页模式已激活：挥手下一页'
  if (visionResult.value?.debug?.pageTurnPoseMatched) return '保持 1 秒后进入翻页模式'
  if (gesture?.action === 'pointer') return '指向：空气指针'
  if (!cameraEnabled.value) return '点击顶部摄像头后识别手势'
  if (activeMode.value === 'pen') return '标注模式：拖动画笔'
  if (activeMode.value === 'zoom') return '区域放大：移动定位'
  return '食指中指伸出、无名指小指收起，保持 1 秒后挥手翻页'
})
const voiceText = computed(() => {
  if (!voiceSupported.value) return '语音：浏览器不支持'
  if (!voiceEnabled.value) return '语音：点击麦克风开启'
  return `语音：${lastVoiceText.value}`
})
const latencyText = computed(() => {
  if (recognitionPaused.value) return '识别已暂停'
  return `延迟 ${visionResult.value?.latencyMs ?? 38}ms`
})
const faceFrameStyle = computed(() => {
  const box = visionResult.value?.face?.box
  if (!box) return {}

  return {
    left: `${Math.max(6, box.x * 58)}%`,
    top: `${Math.max(8, box.y * 100)}%`,
    width: `${Math.max(18, box.width * 58)}%`,
    height: `${Math.max(34, box.height * 100)}%`,
  }
})
const pointerStyle = computed(() => ({
  left: `${pointerPosition.value.x * 100}%`,
  top: `${pointerPosition.value.y * 100}%`,
}))
const zoomWindowStyle = computed(() => ({
  left: `${Math.min(78, Math.max(8, zoomPoint.value.x * 100 - 11))}%`,
  top: `${Math.min(72, Math.max(12, zoomPoint.value.y * 100 - 8))}%`,
}))
const zoomImageStyle = computed(() => {
  if (!currentSlide.value) return {}

  return {
    backgroundImage: `url(${slideUrl(currentSlide.value)})`,
    backgroundPosition: `${zoomPoint.value.x * 100}% ${zoomPoint.value.y * 100}%`,
  }
})
const handFrameStyle = computed(() => {
  const box = visionResult.value?.hand?.box
  if (!box) return {}

  return {
    left: `${box.x * 100}%`,
    top: `${box.y * 100}%`,
    width: `${box.width * 100}%`,
    height: `${box.height * 100}%`,
  }
})
const handCenterStyle = computed(() => {
  const center = visionResult.value?.hand?.center
  if (!center) return {}

  return {
    left: `${center.x * 100}%`,
    top: `${center.y * 100}%`,
  }
})
const fingerStates = computed(() => {
  const fingers = visionResult.value?.hand?.fingers
  return [
    { key: 'thumb', label: '拇指', active: Boolean(fingers?.thumb) },
    { key: 'index', label: '食指', active: Boolean(fingers?.index) },
    { key: 'middle', label: '中指', active: Boolean(fingers?.middle) },
    { key: 'ring', label: '无名指', active: Boolean(fingers?.ring) },
    { key: 'pinky', label: '小指', active: Boolean(fingers?.pinky) },
  ]
})
const debugStatusText = computed(() => {
  const debug = visionResult.value?.debug
  if (!cameraEnabled.value) return '摄像头未开启'
  if (debug?.mediapipeAvailable === false) return 'MediaPipe 未加载'
  if (!visionResult.value?.hand) return '未检测到手'
  if (debug?.pageTurnArmed) return '翻页模式'
  if (debug?.pageTurnPoseMatched) return '保持姿势中'
  return '手部已检测'
})
const debugDetailText = computed(() => {
  const debug = visionResult.value?.debug
  const hand = visionResult.value?.hand
  if (debug?.mediapipeAvailable === false) return debug.mediapipeError || '请安装 mediapipe 后重启后端'
  if (!cameraEnabled.value) return '开启摄像头后显示识别结果'
  if (!hand) return '把手放进摄像头画面，尽量保持掌心清晰'
  const holdText = debug?.pageTurnPoseMatched
    ? ` · 保持 ${Math.round((debug.pageTurnHoldProgress ?? 0) * 100)}%`
    : ''
  const cooldownText = (debug?.pageTurnCooldownRemaining ?? 0) > 0
    ? ` · 冷却 ${debug?.pageTurnCooldownRemaining?.toFixed(1)}s`
    : ''
  return `${hand.source || debug?.handSource || 'unknown'} · ${hand.pose} · ${(hand.confidence * 100).toFixed(0)}%${holdText}${cooldownText}`
})

const processSteps = [
  {
    index: '01',
    title: '摄像头采集手部图像',
    desc: ['实时采集演讲者手部', '视频流'],
    icon: 'camera',
  },
  {
    index: '02',
    title: '手部检测与关键点提取',
    desc: ['检测手部区域并提取', '21 个关键点坐标'],
    icon: 'joints',
  },
  {
    index: '03',
    title: '手势识别',
    desc: ['基于深度学习模型', '识别静态 / 动态手势'],
    icon: 'gesture',
  },
  {
    index: '04',
    title: '时序稳定与误判抑制',
    desc: ['结合时间窗口与滤波算法', '提升稳定性与鲁棒性'],
    icon: 'shield',
  },
  {
    index: '05',
    title: '交互映射',
    desc: ['将识别结果映射为', '演示控制指令'],
    icon: 'monitor',
  },
]

function slideUrl(slide: Slide) {
  if (/^https?:\/\//.test(slide.url)) return slide.url
  return `${apiBase}${slide.url}`
}

function pickFile() {
  fileInput.value?.click()
}

function validateFile(file: File) {
  if (!/\.(ppt|pptx)$/i.test(file.name)) {
    throw new Error('请上传 .ppt 或 .pptx 文件')
  }
}

async function uploadFile(file: File) {
  validateFile(file)
  isUploading.value = true
  errorMessage.value = ''

  try {
    const formData = new FormData()
    formData.append('file', file)

    const response = await fetch(`${apiBase}/api/presentations`, {
      method: 'POST',
      body: formData,
    })

    if (!response.ok) {
      let message = 'PPT 载入失败'
      try {
        const payload = await response.json()
        message = payload.detail || message
      } catch {
        message = response.statusText || message
      }
      throw new Error(message)
    }

    deck.value = (await response.json()) as PresentationManifest
    currentIndex.value = 0
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'PPT 载入失败'
  } finally {
    isUploading.value = false
    isDragging.value = false
  }
}

function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) void uploadFile(file)
  input.value = ''
}

function onDrop(event: DragEvent) {
  event.preventDefault()
  const file = event.dataTransfer?.files?.[0]
  if (file) void uploadFile(file)
}

function goToSlide(index: number) {
  if (!deck.value) {
    demoIndex.value = Math.min(Math.max(index, 0), slideCount.value - 1)
    return
  }
  currentIndex.value = Math.min(Math.max(index, 0), deck.value.slideCount - 1)
}

function previousSlide() {
  goToSlide(currentIndex.value - 1)
}

function nextSlide() {
  goToSlide(currentIndex.value + 1)
}

function executeCommand(action: string, source: 'gesture' | 'voice' | 'button' = 'button') {
  const now = Date.now()
  const needsCooldown = action === 'next' || action === 'previous'
  const commandCooldownMs = source === 'gesture' ? 5000 : 950
  if (needsCooldown && now - lastCommandAt < commandCooldownMs) return
  if (needsCooldown) lastCommandAt = now

  if (action === 'next') nextSlide()
  if (action === 'previous') previousSlide()
  if (action === 'pointer') activeMode.value = 'pointer'
  if (action === 'pen') activeMode.value = 'pen'
  if (action === 'zoom') activeMode.value = 'zoom'
  if (action === 'pause') recognitionPaused.value = true
  if (action === 'resume') recognitionPaused.value = false
  if (action === 'end') {
    showEndConfirm.value = true
    pendingEndByVoice.value = source === 'voice'
  }
  if (action === 'confirm-end') confirmEndPresentation()

  if (externalControlEnabled.value && ['next', 'previous', 'start', 'end', 'pause'].includes(action)) {
    void sendExternalControl(action)
  }
}

async function sendExternalControl(action: string) {
  try {
    await fetch(`${apiBase}/api/presentation/control`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action }),
    })
  } catch {
    errorMessage.value = '外部 PowerPoint 控制暂不可用'
  }
}

async function enterFullscreen() {
  if (!stageRef.value || document.fullscreenElement) return
  await stageRef.value.requestFullscreen()
}

function startVisionLoop() {
  window.clearInterval(visionTimerId)
  visionStatus.value = '视觉识别中'
  visionTimerId = window.setInterval(() => {
    void captureVisionFrame()
  }, 180)
}

function stopVisionLoop() {
  window.clearInterval(visionTimerId)
  visionTimerId = undefined
  visionStatus.value = '视觉待机'
  visionResult.value = null
}

async function loadVisionSettings() {
  try {
    const response = await fetch(`${apiBase}/api/vision/settings`)
    if (!response.ok) return
    visionSettings.value = (await response.json()) as VisionSettings
  } catch {
    // Keep local defaults when backend settings are unavailable.
  }
}

async function saveVisionSettings() {
  try {
    const response = await fetch(`${apiBase}/api/vision/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(visionSettings.value),
    })
    if (!response.ok) throw new Error('settings failed')
    visionSettings.value = (await response.json()) as VisionSettings
    errorMessage.value = ''
    showSettings.value = false
  } catch {
    errorMessage.value = '视觉参数保存失败'
  }
}

async function captureVisionFrame() {
  if (recognitionPaused.value || !cameraEnabled.value || !videoRef.value || !frameCanvasRef.value) return
  if (videoRef.value.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) return

  const canvas = frameCanvasRef.value
  const context = canvas.getContext('2d')
  if (!context) return

  canvas.width = 360
  canvas.height = 202
  context.save()
  context.scale(-1, 1)
  context.drawImage(videoRef.value, -canvas.width, 0, canvas.width, canvas.height)
  context.restore()

  const data = canvas.toDataURL('image/jpeg', 0.58)
  const startedAt = performance.now()
  try {
    const response = await fetch(`${apiBase}/api/vision/frame`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ clientId: 'browser-main', data }),
    })
    if (!response.ok) throw new Error('vision request failed')

    const payload = (await response.json()) as VisionResult
    payload.latencyMs = payload.latencyMs || Math.round(performance.now() - startedAt)
    applyVisionResult(payload)
  } catch {
    visionStatus.value = '视觉连接失败'
  }
}

function applyVisionResult(payload: VisionResult) {
  visionResult.value = payload
  visionStatus.value = payload.status === 'detected' ? '视觉识别中' : '未检测到有效手势'

  if (payload.hand?.center) {
    pointerPosition.value = payload.hand.center
    zoomPoint.value = payload.hand.center
  }

  const action = payload.gesture?.action
  if (action === 'next' || action === 'previous') {
    executeCommand(action, 'gesture')
  }
}

async function startCamera() {
  cameraError.value = ''
  visionStatus.value = '正在请求摄像头权限'
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: 640, height: 360, facingMode: 'user' },
      audio: false,
    })
    cameraStream.value = stream
    cameraEnabled.value = true
    await nextTick()
    if (videoRef.value) {
      videoRef.value.srcObject = stream
      await videoRef.value.play()
    }
    if (debugVideoRef.value) {
      debugVideoRef.value.srcObject = stream
      await debugVideoRef.value.play()
    }
    startVisionLoop()
  } catch {
    cameraEnabled.value = false
    cameraError.value = '摄像头未授权'
    visionStatus.value = '摄像头未授权，无法识别手势'
  }
}

function stopCamera() {
  cameraStream.value?.getTracks().forEach((track) => track.stop())
  cameraStream.value = null
  cameraEnabled.value = false
  if (videoRef.value) videoRef.value.srcObject = null
  if (debugVideoRef.value) debugVideoRef.value.srcObject = null
  stopVisionLoop()
}

function toggleCamera() {
  if (cameraEnabled.value) {
    stopCamera()
  } else {
    void startCamera()
  }
}

function toggleVoice() {
  if (voiceEnabled.value) {
    stopVoice()
  } else {
    startVoice()
  }
}

function startVoice() {
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!Recognition) {
    voiceSupported.value = false
    lastVoiceText.value = '浏览器不支持语音识别'
    return
  }

  const recognition = new Recognition()
  recognition.lang = 'zh-CN'
  recognition.continuous = true
  recognition.interimResults = false
  recognition.onresult = (event: any) => {
    const results = Array.from(event.results ?? []) as any[]
    const lastResult = results[results.length - 1]
    const transcript = lastResult?.[0]?.transcript?.trim()
    if (!transcript) return
    lastVoiceText.value = transcript
    handleVoiceCommand(transcript)
  }
  recognition.onerror = () => {
    lastVoiceText.value = '语音识别异常'
  }
  recognition.onend = () => {
    if (voiceEnabled.value) {
      try {
        recognition.start()
      } catch {
        voiceEnabled.value = false
      }
    }
  }

  speechRecognition.value = recognition
  voiceEnabled.value = true
  lastVoiceText.value = '正在聆听'
  recognition.start()
}

function stopVoice() {
  voiceEnabled.value = false
  speechRecognition.value?.stop()
  speechRecognition.value = null
  lastVoiceText.value = '等待语音'
}

function handleVoiceCommand(text: string) {
  const command = text.replace(/\s/g, '')
  if (showEndConfirm.value && (command.includes('确认结束') || command.includes('确认'))) {
    executeCommand('confirm-end', 'voice')
    return
  }
  if (command.includes('下一页') || command.includes('下页')) executeCommand('next', 'voice')
  if (command.includes('上一页') || command.includes('上页')) executeCommand('previous', 'voice')
  if (command.includes('空气指针') || command.includes('打开指针') || command.includes('指针')) executeCommand('pointer', 'voice')
  if (command.includes('标注') || command.includes('画笔')) executeCommand('pen', 'voice')
  if (command.includes('放大') || command.includes('区域')) executeCommand('zoom', 'voice')
  if (command.includes('暂停')) executeCommand('pause', 'voice')
  if (command.includes('继续')) executeCommand('resume', 'voice')
  if (command.includes('结束演示') || command.includes('结束放映')) executeCommand('end', 'voice')
}

function stagePoint(event: PointerEvent): Point {
  const rect = stageRef.value?.getBoundingClientRect()
  if (!rect) return { x: 0.5, y: 0.5 }
  return {
    x: Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width)),
    y: Math.min(1, Math.max(0, (event.clientY - rect.top) / rect.height)),
  }
}

function pointList(points: Point[]) {
  return points.map((point) => `${point.x * 100},${point.y * 100}`).join(' ')
}

function handleStagePointerMove(event: PointerEvent) {
  if (activeMode.value === 'zoom') {
    zoomPoint.value = stagePoint(event)
  }
}

function startAnnotation(event: PointerEvent) {
  if (activeMode.value !== 'pen') return
  const target = event.currentTarget as HTMLElement
  target.setPointerCapture?.(event.pointerId)
  const line = { id: annotationId++, points: [stagePoint(event)] }
  drawingLine.value = line
  annotations.value.push(line)
}

function moveAnnotation(event: PointerEvent) {
  if (activeMode.value !== 'pen' || !drawingLine.value) return
  drawingLine.value.points.push(stagePoint(event))
}

function stopAnnotation(event: PointerEvent) {
  const target = event.currentTarget as HTMLElement
  target.releasePointerCapture?.(event.pointerId)
  drawingLine.value = null
}

function clearAnnotations() {
  annotations.value = []
}

function requestEndPresentation() {
  showEndConfirm.value = true
}

function confirmEndPresentation() {
  deck.value = null
  currentIndex.value = 0
  activeMode.value = 'pointer'
  recognitionPaused.value = false
  annotations.value = []
  showEndConfirm.value = false
  pendingEndByVoice.value = false
}

function cancelEndPresentation() {
  showEndConfirm.value = false
  pendingEndByVoice.value = false
}

function handleKeydown(event: KeyboardEvent) {
  const target = event.target as HTMLElement | null
  if (target?.tagName === 'INPUT' || target?.tagName === 'TEXTAREA') return

  if (event.key === 'ArrowRight' || event.key === 'PageDown' || event.key === ' ') {
    event.preventDefault()
    nextSlide()
  }
  if (event.key === 'ArrowLeft' || event.key === 'PageUp') {
    event.preventDefault()
    previousSlide()
  }
  if (event.key === 'Home') {
    event.preventDefault()
    goToSlide(0)
  }
  if (event.key === 'End' && deck.value) {
    event.preventDefault()
    goToSlide(deck.value.slideCount - 1)
  }
  if (event.key.toLowerCase() === 'f') {
    event.preventDefault()
    void enterFullscreen()
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
  void loadVisionSettings()
  timerId = window.setInterval(() => {
    if (!recognitionPaused.value) elapsedSeconds.value += 1
  }, 1000)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKeydown)
  if (timerId) window.clearInterval(timerId)
  stopVoice()
  stopCamera()
})
</script>

<template>
  <main class="prototype-shell">
    <input
      ref="fileInput"
      class="sr-only"
      type="file"
      accept=".ppt,.pptx,application/vnd.ms-powerpoint,application/vnd.openxmlformats-officedocument.presentationml.presentation"
      @change="onFileChange"
    />
    <canvas ref="frameCanvasRef" class="sr-only" aria-hidden="true"></canvas>

    <header class="top-bar">
      <section class="brand-zone">
        <div class="app-logo">
          <span></span>
          <span></span>
          <span></span>
          <span></span>
          <span></span>
        </div>
        <h1>智能演讲辅助系统</h1>
        <div class="divider"></div>
        <div class="live-state">
          <i></i>
          <span>演示中 {{ elapsedText }}</span>
        </div>
      </section>

      <button class="file-title" type="button" @click="pickFile">
        <span>{{ filename }}</span>
        <ChevronDown :size="16" />
      </button>

      <section class="device-zone">
        <button class="icon-status" :class="{ active: voiceEnabled }" type="button" title="语音控制" @click="toggleVoice">
          <Mic :size="22" />
          <span class="level-bars"><i></i><i></i><i></i></span>
        </button>
        <div class="divider"></div>
        <button class="camera-toggle" type="button" @click="toggleCamera">
          <Video :size="22" />
          <span>{{ cameraStatusText }}</span>
        </button>
        <div class="divider"></div>
        <button class="settings-button" type="button" @click="showSettings = true">
          <Settings :size="22" />
          <span>设置</span>
        </button>
        <button class="upload-button" type="button" :disabled="isUploading" @click="pickFile">
          <Loader2 v-if="isUploading" :size="18" class="spin" />
          <FileUp v-else :size="18" />
          <span>{{ isUploading ? '转换中' : '上传 PPT' }}</span>
        </button>
        <div class="window-actions">
          <Minus :size="20" />
          <Maximize2 :size="18" />
          <X :size="21" />
        </div>
      </section>
    </header>

    <section class="stage-area">
      <article
        ref="stageRef"
        class="presentation-stage"
        :class="{ dragging: isDragging }"
        @dragenter.prevent="isDragging = true"
        @dragover.prevent="isDragging = true"
        @dragleave.prevent="isDragging = false"
        @drop="onDrop"
        @pointermove="handleStagePointerMove"
      >
        <template v-if="currentSlide">
          <img class="real-slide" :src="slideUrl(currentSlide)" :alt="`PPT 第 ${currentSlide.index} 页`" />
        </template>

        <template v-else>
          <section class="demo-slide">
            <div class="slide-bg-line line-one"></div>
            <div class="slide-bg-line line-two"></div>
            <div class="slide-heading">
              <h2>手势识别模块</h2>
              <span></span>
              <p>通过计算机视觉与深度学习技术，识别演讲者的手势并映射为演示控制指令，实现自然、无接触的交互体验。</p>
            </div>

            <div class="process-row">
              <article v-for="(step, index) in processSteps" :key="step.index" class="process-step">
                <div v-if="index < processSteps.length - 1" class="step-arrow">
                  <span></span>
                  <ArrowRight :size="28" />
                </div>
                <div class="step-icon">
                  <b>{{ step.index }}</b>
                  <Camera v-if="step.icon === 'camera'" :size="68" />
                  <div v-else-if="step.icon === 'joints'" class="hand-points">
                    <i v-for="point in 11" :key="point" :class="`point-${point}`"></i>
                    <em v-for="line in 5" :key="line" :class="`line-${line}`"></em>
                  </div>
                  <Hand v-else-if="step.icon === 'gesture'" :size="72" />
                  <CheckCircle2 v-else-if="step.icon === 'shield'" :size="76" />
                  <Monitor v-else :size="76" />
                </div>
                <h3>{{ step.title }}</h3>
                <p>
                  <span v-for="line in step.desc" :key="line">{{ line }}</span>
                </p>
              </article>
            </div>

            <svg class="pointer-path" viewBox="0 0 230 160" aria-hidden="true">
              <path d="M12 22 C 44 60, 82 24, 102 60 S 124 128, 214 134" />
              <circle cx="12" cy="22" r="14" />
            </svg>
          </section>
        </template>

        <svg
          class="annotation-layer"
          :class="{ drawable: activeMode === 'pen' }"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          @pointerdown="startAnnotation"
          @pointermove="moveAnnotation"
          @pointerup="stopAnnotation"
          @pointerleave="stopAnnotation"
        >
          <polyline
            v-for="line in annotations"
            :key="line.id"
            :points="pointList(line.points)"
            vector-effect="non-scaling-stroke"
          />
        </svg>

        <div v-if="activeMode === 'pointer'" class="air-pointer" :style="pointerStyle">
          <span></span>
        </div>

        <div v-if="activeMode === 'zoom'" class="zoom-window" :style="zoomWindowStyle">
          <div class="zoom-surface" :style="zoomImageStyle">
            <span v-if="!currentSlide">区域放大</span>
          </div>
          <b>2.2x</b>
        </div>

        <aside class="camera-preview">
          <span class="camera-dot"></span>
          <video v-show="cameraEnabled" ref="videoRef" muted playsinline></video>
          <div v-if="!cameraEnabled" class="mock-face">
            <div class="hair"></div>
            <div class="head"></div>
            <div class="glasses left"></div>
            <div class="glasses right"></div>
            <div class="bridge"></div>
            <span class="eye eye-left"></span>
            <span class="eye eye-right"></span>
            <span class="mouth"></span>
          </div>
          <div class="face-frame" :style="faceFrameStyle"></div>
          <div class="camera-copy">
            <strong>{{ faceStatusText }}</strong>
            <span>{{ distanceText }}</span>
          </div>
        </aside>

        <aside class="hand-debug-panel">
          <header>
            <span>手指调试</span>
            <b :class="{ ready: visionResult?.debug?.pageTurnArmed }">{{ debugStatusText }}</b>
          </header>
          <div class="debug-video-box">
            <video v-show="cameraEnabled" ref="debugVideoRef" muted playsinline></video>
            <div v-if="!cameraEnabled" class="debug-video-placeholder">
              <Video :size="26" />
              <span>摄像头未开启</span>
            </div>
            <div v-if="visionResult?.hand" class="hand-frame" :style="handFrameStyle"></div>
            <span v-if="visionResult?.hand" class="hand-center" :style="handCenterStyle"></span>
          </div>
          <div class="finger-grid">
            <span
              v-for="finger in fingerStates"
              :key="finger.key"
              :class="{ active: finger.active }"
            >
              {{ finger.label }}
            </span>
          </div>
          <p>{{ debugDetailText }}</p>
        </aside>

        <aside class="assist-card">
          <p>
            <Hand :size="23" />
            <span>{{ gestureText }}</span>
          </p>
          <p>
            <Mic :size="23" />
            <span>{{ voiceText }}</span>
          </p>
          <p>
            <i></i>
            <span>{{ latencyText }}</span>
          </p>
          <small>{{ visionStatus }} · {{ modeText }}</small>
        </aside>

        <button v-if="!hasDeck" class="quick-upload" type="button" @click="pickFile">
          <UploadCloud :size="18" />
          <span>上传真实 PPT</span>
        </button>

        <div v-if="isUploading" class="loading-mask">
          <Loader2 :size="26" class="spin" />
          <span>正在转换 PPT 页面</span>
        </div>

        <div v-if="errorMessage" class="error-toast">
          {{ errorMessage }}
        </div>

        <div class="slide-progress">
          <span :style="{ width: `${progress}%` }"></span>
        </div>
      </article>
    </section>

    <footer class="bottom-bar">
      <button class="collapse-button" type="button">
        <ChevronUp :size="30" />
      </button>

      <nav class="tool-strip">
        <button class="tool-button" type="button" :disabled="hasDeck ? currentIndex === 0 : demoIndex === 0" @click="previousSlide">
          <ArrowLeft :size="34" />
          <span>上一页</span>
        </button>
        <button
          class="tool-button"
          type="button"
          :disabled="hasDeck ? currentIndex >= (deck?.slideCount ?? 1) - 1 : demoIndex >= slideCount - 1"
          @click="nextSlide"
        >
          <ArrowRight :size="34" />
          <span>下一页</span>
        </button>
        <button class="tool-button" :class="{ active: activeMode === 'pointer' }" type="button" @click="activeMode = 'pointer'">
          <Hand :size="33" />
          <span>空气指针</span>
        </button>
        <button class="tool-button" :class="{ selected: activeMode === 'pen' }" type="button" @click="activeMode = 'pen'" @dblclick="clearAnnotations">
          <PenLine :size="32" />
          <span>标注</span>
        </button>
        <button class="tool-button" :class="{ selected: activeMode === 'zoom' }" type="button" @click="activeMode = 'zoom'">
          <Expand :size="32" />
          <span>区域放大</span>
        </button>
        <button class="tool-button" type="button" @click="recognitionPaused = !recognitionPaused">
          <Pause :size="34" />
          <span>{{ recognitionPaused ? '继续识别' : '暂停识别' }}</span>
        </button>
        <button class="tool-button danger" type="button" @click="requestEndPresentation">
          <Square :size="25" />
          <span>结束演示</span>
        </button>
      </nav>

      <div class="footer-meta">
        <span>{{ conversionLabel }}</span>
        <b>{{ displayIndex }} / {{ slideCount }}</b>
        <button type="button" @click="enterFullscreen">全屏</button>
      </div>
    </footer>

    <section v-if="showEndConfirm" class="confirm-layer">
      <article class="confirm-dialog">
        <h2>确认结束演示？</h2>
        <p>为避免误操作，请点击确认按钮，或开启语音后说“确认结束”。</p>
        <div class="confirm-checks">
          <span :class="{ ok: !pendingEndByVoice }">手动确认已就绪</span>
          <span :class="{ ok: voiceEnabled }">语音确认{{ voiceEnabled ? '可用' : '未开启' }}</span>
        </div>
        <div class="confirm-actions">
          <button type="button" @click="cancelEndPresentation">继续演示</button>
          <button class="danger" type="button" @click="confirmEndPresentation">确认结束</button>
        </div>
      </article>
    </section>

    <section v-if="showSettings" class="confirm-layer">
      <article class="settings-dialog">
        <header>
          <h2>交互设置</h2>
          <button type="button" @click="showSettings = false">
            <X :size="20" />
          </button>
        </header>

        <label class="setting-row">
          <span>
            手势冷却时间
            <small>翻页手势固定 5 秒冷却，防止连续误触发</small>
          </span>
          <input v-model.number="visionSettings.cooldownSeconds" min="5" max="5" step="0.1" type="range" disabled />
          <b>{{ visionSettings.cooldownSeconds.toFixed(1) }}s</b>
        </label>

        <label class="setting-row">
          <span>
            滑动触发阈值
            <small>数值越小越灵敏，越大越稳定</small>
          </span>
          <input v-model.number="visionSettings.swipeThreshold" min="0.08" max="0.5" step="0.01" type="range" />
          <b>{{ visionSettings.swipeThreshold.toFixed(2) }}</b>
        </label>

        <label class="setting-row">
          <span>
            识别置信阈值
            <small>过滤较小或不稳定的手部区域</small>
          </span>
          <input v-model.number="visionSettings.confidenceThreshold" min="0.2" max="0.95" step="0.01" type="range" />
          <b>{{ visionSettings.confidenceThreshold.toFixed(2) }}</b>
        </label>

        <label class="toggle-row">
          <span>
            控制外部 PowerPoint
            <small>开启后会通过 Python 调用 PowerPoint COM，失败时用系统按键兜底</small>
          </span>
          <input v-model="externalControlEnabled" type="checkbox" />
        </label>

        <footer>
          <button type="button" @click="showSettings = false">取消</button>
          <button class="primary" type="button" @click="saveVisionSettings">保存设置</button>
        </footer>
      </article>
    </section>
  </main>
</template>

<style scoped>
.prototype-shell {
  display: grid;
  min-height: 100vh;
  grid-template-rows: 64px minmax(0, 1fr) 96px;
  overflow: hidden;
  background:
    radial-gradient(circle at 50% 20%, rgb(40 67 104 / 0.2), transparent 42%),
    linear-gradient(180deg, #0a1423 0%, #121e2d 100%);
  color: #f5f8ff;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
}

.top-bar,
.bottom-bar {
  position: relative;
  z-index: 20;
  display: flex;
  align-items: center;
  background: rgb(10 20 35 / 0.96);
  box-shadow: 0 10px 34px rgb(0 0 0 / 0.28);
}

.top-bar {
  justify-content: space-between;
  gap: 24px;
  border-bottom: 1px solid rgb(255 255 255 / 0.09);
  padding: 0 28px;
}

.brand-zone,
.device-zone,
.live-state,
.icon-status,
.camera-toggle,
.settings-button,
.file-title,
.upload-button,
.window-actions {
  display: flex;
  align-items: center;
}

.brand-zone {
  min-width: 370px;
  gap: 16px;
}

.app-logo {
  display: flex;
  width: 40px;
  height: 40px;
  align-items: center;
  justify-content: center;
  gap: 2px;
  border-radius: 10px;
  background: linear-gradient(135deg, #2d91ff, #275de8);
  box-shadow: 0 12px 26px rgb(45 125 255 / 0.34);
}

.app-logo span {
  width: 3px;
  border-radius: 999px;
  background: white;
}

.app-logo span:nth-child(1),
.app-logo span:nth-child(5) {
  height: 13px;
}

.app-logo span:nth-child(2),
.app-logo span:nth-child(4) {
  height: 21px;
}

.app-logo span:nth-child(3) {
  height: 28px;
}

.brand-zone h1 {
  white-space: nowrap;
  font-size: 20px;
  font-weight: 700;
  letter-spacing: 0;
}

.divider {
  width: 1px;
  height: 28px;
  background: rgb(255 255 255 / 0.13);
}

.live-state {
  gap: 10px;
  white-space: nowrap;
  color: #d8e2f0;
  font-size: 17px;
}

.live-state i,
.assist-card i,
.camera-dot {
  width: 11px;
  height: 11px;
  border-radius: 999px;
  background: #20e793;
  box-shadow: 0 0 18px rgb(32 231 147 / 0.8);
}

.file-title {
  max-width: 580px;
  min-width: 340px;
  justify-content: center;
  gap: 8px;
  border: 0;
  background: transparent;
  color: #e8eef8;
  font-size: 18px;
  cursor: pointer;
}

.file-title span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-zone {
  justify-content: flex-end;
  gap: 18px;
  min-width: 490px;
  color: #d4deec;
}

.icon-status,
.camera-toggle,
.settings-button,
.upload-button {
  gap: 8px;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  cursor: pointer;
}

.icon-status.active {
  color: #18e193;
}

.level-bars {
  display: flex;
  align-items: flex-end;
  gap: 4px;
  color: #16eb91;
}

.level-bars i {
  width: 4px;
  border-radius: 999px;
  background: currentColor;
}

.level-bars i:nth-child(1) {
  height: 13px;
}

.level-bars i:nth-child(2) {
  height: 19px;
}

.level-bars i:nth-child(3) {
  height: 19px;
}

.upload-button {
  height: 34px;
  padding: 0 12px;
  border: 1px solid rgb(255 255 255 / 0.14);
  border-radius: 8px;
  background: rgb(255 255 255 / 0.06);
}

.window-actions {
  gap: 18px;
  color: #cfd9e8;
}

.stage-area {
  display: flex;
  min-height: 0;
  align-items: center;
  justify-content: center;
  padding: 16px;
  background: linear-gradient(180deg, #07111f 0%, #0f1b2a 100%);
}

.presentation-stage {
  position: relative;
  width: min(100%, 1880px);
  aspect-ratio: 16 / 9;
  overflow: hidden;
  border: 1px solid rgb(255 255 255 / 0.2);
  border-radius: 4px;
  background: #f7fbff;
  box-shadow: 0 24px 58px rgb(0 0 0 / 0.36);
}

.presentation-stage.dragging {
  outline: 3px solid rgb(32 126 255 / 0.7);
}

.real-slide {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: white;
}

.annotation-layer {
  position: absolute;
  inset: 0;
  z-index: 4;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.annotation-layer.drawable {
  cursor: crosshair;
  pointer-events: auto;
}

.annotation-layer polyline {
  fill: none;
  stroke: #13d59d;
  stroke-width: 5;
  stroke-linecap: round;
  stroke-linejoin: round;
  filter: drop-shadow(0 4px 8px rgb(19 213 157 / 0.28));
}

.air-pointer {
  position: absolute;
  z-index: 5;
  width: 26px;
  height: 26px;
  transform: translate(-50%, -50%);
  border: 3px solid white;
  border-radius: 999px;
  background: rgb(43 132 255 / 0.9);
  box-shadow:
    0 0 0 9px rgb(43 132 255 / 0.16),
    0 10px 26px rgb(23 84 170 / 0.36);
  pointer-events: none;
}

.air-pointer span {
  position: absolute;
  left: 19px;
  top: 19px;
  width: 92px;
  height: 3px;
  transform: rotate(28deg);
  transform-origin: left center;
  border-radius: 999px;
  background: linear-gradient(90deg, rgb(43 132 255 / 0.7), transparent);
}

.zoom-window {
  position: absolute;
  z-index: 6;
  width: 252px;
  height: 158px;
  overflow: hidden;
  border: 2px solid rgb(43 132 255 / 0.95);
  border-radius: 10px;
  background: rgb(243 248 255 / 0.96);
  box-shadow: 0 24px 54px rgb(21 67 140 / 0.26);
  pointer-events: none;
}

.zoom-surface {
  display: grid;
  width: 100%;
  height: 100%;
  place-items: center;
  background:
    linear-gradient(rgb(255 255 255 / 0.08), rgb(255 255 255 / 0.08)),
    radial-gradient(circle at 50% 50%, #ffffff, #ddecff);
  background-repeat: no-repeat;
  background-size: 230% 230%;
  color: #1e67d8;
  font-weight: 800;
}

.zoom-window b {
  position: absolute;
  right: 8px;
  bottom: 7px;
  border-radius: 999px;
  background: rgb(16 40 76 / 0.7);
  color: white;
  padding: 3px 8px;
  font-size: 12px;
}

.demo-slide {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background:
    radial-gradient(circle at 52% 20%, rgb(255 255 255 / 0.95), rgb(237 246 255 / 0.95) 46%, rgb(226 239 255 / 0.92)),
    linear-gradient(135deg, #f9fcff, #eaf3ff);
  color: #102849;
}

.slide-bg-line {
  position: absolute;
  pointer-events: none;
  border-radius: 50%;
}

.line-one {
  right: -160px;
  top: 70px;
  width: 680px;
  height: 680px;
  border: 1px solid rgb(183 205 238 / 0.35);
  box-shadow:
    inset 20px 0 0 rgb(255 255 255 / 0.18),
    inset 42px 0 0 rgb(255 255 255 / 0.16),
    inset 68px 0 0 rgb(255 255 255 / 0.13);
}

.line-two {
  left: -160px;
  bottom: -300px;
  width: 1180px;
  height: 540px;
  border-top: 1px solid rgb(206 220 241 / 0.78);
  transform: rotate(9deg);
}

.slide-heading {
  padding-top: 86px;
  text-align: center;
}

.slide-heading h2 {
  margin: 0;
  color: #102849;
  font-size: clamp(38px, 4.1vw, 72px);
  font-weight: 800;
  line-height: 1;
  letter-spacing: 0;
}

.slide-heading span {
  display: block;
  width: 76px;
  height: 5px;
  margin: 24px auto 28px;
  border-radius: 999px;
  background: linear-gradient(90deg, #1f7fff, #6da4ff);
}

.slide-heading p {
  margin: 0 auto;
  max-width: 980px;
  color: #50627a;
  font-size: clamp(15px, 1.08vw, 21px);
  font-weight: 500;
}

.process-row {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 34px;
  width: min(88%, 1640px);
  margin: clamp(58px, 7vw, 96px) auto 0;
}

.process-step {
  position: relative;
  text-align: center;
}

.step-icon {
  position: relative;
  display: grid;
  width: clamp(120px, 9.6vw, 192px);
  height: clamp(120px, 9.6vw, 192px);
  place-items: center;
  margin: 0 auto;
  border: 2px solid #78a8ff;
  border-radius: 50%;
  background: radial-gradient(circle, rgb(221 234 252 / 0.8), rgb(247 251 255 / 0.96) 68%);
  color: #3275d9;
  box-shadow: inset 0 0 34px rgb(99 148 220 / 0.14);
}

.step-icon b {
  position: absolute;
  left: -8px;
  top: -12px;
  display: grid;
  width: 44px;
  height: 44px;
  place-items: center;
  border-radius: 999px;
  background: linear-gradient(180deg, #1f84ff, #2867d9);
  color: white;
  font-size: 22px;
  line-height: 1;
  box-shadow: 0 8px 18px rgb(32 117 228 / 0.28);
}

.process-step h3 {
  margin: 26px 0 0;
  color: #102849;
  font-size: clamp(17px, 1.25vw, 24px);
  font-weight: 800;
  line-height: 1.25;
}

.process-step p {
  margin: 15px 0 0;
  color: #68758a;
  font-size: clamp(14px, 1.05vw, 21px);
  line-height: 1.7;
}

.process-step p span {
  display: block;
}

.step-arrow {
  position: absolute;
  left: calc(50% + 98px);
  top: 84px;
  display: flex;
  width: 122px;
  align-items: center;
  color: #2e7af0;
}

.step-arrow span {
  flex: 1;
  border-top: 2px dashed #8bb5ff;
}

.hand-points {
  position: relative;
  width: 88px;
  height: 88px;
}

.hand-points i,
.hand-points em {
  position: absolute;
  display: block;
}

.hand-points i {
  width: 11px;
  height: 11px;
  border-radius: 50%;
  background: #3976d3;
}

.hand-points em {
  left: 42px;
  top: 55px;
  width: 48px;
  height: 2px;
  transform-origin: left center;
  background: #78a8e8;
}

.hand-points .point-1 { left: 16px; top: 52px; }
.hand-points .point-2 { left: 30px; top: 70px; }
.hand-points .point-3 { left: 42px; top: 55px; }
.hand-points .point-4 { left: 35px; top: 22px; }
.hand-points .point-5 { left: 52px; top: 14px; }
.hand-points .point-6 { left: 63px; top: 48px; }
.hand-points .point-7 { left: 78px; top: 28px; }
.hand-points .point-8 { left: 52px; top: 40px; }
.hand-points .point-9 { left: 20px; top: 35px; }
.hand-points .point-10 { left: 70px; top: 68px; }
.hand-points .point-11 { left: 58px; top: 76px; }
.hand-points .line-1 { transform: rotate(-101deg); }
.hand-points .line-2 { transform: rotate(-74deg); }
.hand-points .line-3 { transform: rotate(-48deg); }
.hand-points .line-4 { transform: rotate(-18deg); }
.hand-points .line-5 { transform: rotate(22deg); }

.pointer-path {
  position: absolute;
  right: 17.5%;
  bottom: 25%;
  width: 168px;
  height: 118px;
  overflow: visible;
}

.pointer-path path {
  fill: none;
  stroke: #5b98f3;
  stroke-width: 5;
  stroke-linecap: round;
  filter: drop-shadow(0 8px 14px rgb(40 110 210 / 0.22));
}

.pointer-path circle {
  fill: white;
  stroke: #2c87ff;
  stroke-width: 6;
}

.camera-preview {
  position: absolute;
  left: 24px;
  top: 22px;
  z-index: 6;
  width: clamp(220px, 15.5vw, 292px);
  height: clamp(112px, 8.1vw, 154px);
  overflow: hidden;
  border-radius: 10px;
  background: rgb(55 65 78 / 0.75);
  box-shadow: 0 18px 42px rgb(23 46 79 / 0.18);
  backdrop-filter: blur(12px);
}

.camera-dot {
  position: absolute;
  left: 13px;
  top: 13px;
  z-index: 4;
  width: 14px;
  height: 14px;
  border: 2px solid white;
}

.camera-preview video {
  width: 58%;
  height: 100%;
  object-fit: cover;
  transform: scaleX(-1);
}

.mock-face {
  position: absolute;
  inset: 0 auto 0 0;
  width: 58%;
  background: linear-gradient(110deg, #384352, #1b2531);
}

.hair,
.head,
.glasses,
.bridge,
.eye,
.mouth {
  position: absolute;
}

.hair {
  left: 32%;
  top: 14%;
  width: 44%;
  height: 38%;
  border-radius: 48% 48% 42% 42%;
  background: #151820;
  box-shadow: -12px 7px 0 #11151d, 12px 4px 0 #11151d;
}

.head {
  left: 34%;
  top: 30%;
  width: 40%;
  height: 48%;
  border-radius: 42% 42% 46% 46%;
  background: linear-gradient(#e0c0aa, #c89579);
}

.glasses {
  top: 47%;
  width: 16%;
  height: 15%;
  border: 2px solid #252a33;
  border-radius: 8px;
}

.glasses.left {
  left: 39%;
}

.glasses.right {
  left: 56%;
}

.bridge {
  left: 55%;
  top: 55%;
  width: 6%;
  height: 2px;
  background: #252a33;
}

.eye {
  top: 55%;
  width: 6%;
  height: 3px;
  border-radius: 999px;
  background: #1c2028;
}

.eye-left {
  left: 44%;
}

.eye-right {
  left: 61%;
}

.mouth {
  left: 49%;
  top: 72%;
  width: 15%;
  height: 2px;
  border-radius: 999px;
  background: rgb(86 40 40 / 0.55);
}

.face-frame {
  position: absolute;
  left: 11%;
  top: 27%;
  width: 38%;
  height: 62%;
  border: 2px solid white;
  box-shadow: 0 0 0 1px rgb(31 130 255 / 0.15);
}

.camera-copy {
  position: absolute;
  left: 58%;
  top: 50%;
  display: grid;
  gap: 7px;
  transform: translateY(-50%);
  color: white;
  font-size: clamp(13px, 0.95vw, 18px);
  line-height: 1.25;
}

.camera-copy strong {
  font-weight: 800;
}

.hand-debug-panel {
  position: absolute;
  right: 28px;
  top: 22px;
  z-index: 7;
  width: clamp(260px, 17vw, 326px);
  overflow: hidden;
  border: 1px solid rgb(255 255 255 / 0.18);
  border-radius: 10px;
  background: rgb(13 27 47 / 0.78);
  color: white;
  box-shadow: 0 18px 42px rgb(12 28 52 / 0.26);
  backdrop-filter: blur(14px);
}

.hand-debug-panel header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-bottom: 1px solid rgb(255 255 255 / 0.1);
  font-size: 14px;
  font-weight: 800;
}

.hand-debug-panel header b {
  border-radius: 999px;
  background: rgb(255 255 255 / 0.08);
  color: #b8c7dc;
  padding: 3px 8px;
  font-size: 12px;
  font-weight: 800;
}

.hand-debug-panel header b.ready {
  background: rgb(32 231 147 / 0.16);
  color: #76f2bd;
}

.debug-video-box {
  position: relative;
  height: clamp(132px, 9.5vw, 176px);
  overflow: hidden;
  background: #07111f;
}

.debug-video-box video {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transform: scaleX(-1);
}

.debug-video-placeholder {
  display: grid;
  height: 100%;
  place-items: center;
  color: #9fb0c8;
  font-size: 13px;
}

.debug-video-placeholder span {
  margin-top: 6px;
}

.hand-frame {
  position: absolute;
  border: 2px solid #20e793;
  box-shadow:
    0 0 0 1px rgb(255 255 255 / 0.65),
    0 0 18px rgb(32 231 147 / 0.42);
}

.hand-center {
  position: absolute;
  width: 13px;
  height: 13px;
  transform: translate(-50%, -50%);
  border: 2px solid white;
  border-radius: 999px;
  background: #ffcc4d;
  box-shadow: 0 0 18px rgb(255 204 77 / 0.7);
}

.finger-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 6px;
  padding: 10px 12px 0;
}

.finger-grid span {
  min-width: 0;
  border: 1px solid rgb(255 255 255 / 0.1);
  border-radius: 7px;
  background: rgb(255 255 255 / 0.06);
  color: #b6c3d6;
  padding: 6px 2px;
  text-align: center;
  font-size: 12px;
  font-weight: 800;
}

.finger-grid span.active {
  border-color: rgb(32 231 147 / 0.38);
  background: rgb(32 231 147 / 0.14);
  color: #78f2be;
}

.hand-debug-panel p {
  margin: 0;
  padding: 10px 12px 12px;
  color: #aebbd0;
  font-size: 12px;
  line-height: 1.45;
}

.assist-card {
  position: absolute;
  right: 28px;
  bottom: 28px;
  z-index: 5;
  width: clamp(226px, 15.4vw, 292px);
  padding: 22px 26px;
  border-radius: 10px;
  background: rgb(82 94 112 / 0.7);
  color: white;
  font-size: clamp(15px, 1.08vw, 20px);
  font-weight: 600;
  box-shadow: 0 22px 48px rgb(43 65 94 / 0.2);
  backdrop-filter: blur(14px);
}

.assist-card p {
  display: flex;
  align-items: center;
  gap: 13px;
  margin: 0;
}

.assist-card p + p {
  margin-top: 18px;
}

.assist-card small {
  display: block;
  margin-top: 18px;
  color: rgb(255 255 255 / 0.7);
  font-size: 13px;
  font-weight: 500;
}

.quick-upload {
  position: absolute;
  left: 50%;
  bottom: 22px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  transform: translateX(-50%);
  border: 0;
  border-radius: 8px;
  background: rgb(16 38 66 / 0.72);
  color: white;
  padding: 10px 15px;
  cursor: pointer;
  backdrop-filter: blur(12px);
}

.loading-mask {
  position: absolute;
  inset: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  background: rgb(8 19 34 / 0.76);
  color: white;
  font-size: 18px;
  backdrop-filter: blur(8px);
}

.spin {
  animation: spin 900ms linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.error-toast {
  position: absolute;
  left: 50%;
  top: 20px;
  z-index: 11;
  max-width: min(760px, 72%);
  transform: translateX(-50%);
  border: 1px solid rgb(255 144 92 / 0.34);
  border-radius: 8px;
  background: rgb(82 38 30 / 0.84);
  color: #ffd7c2;
  padding: 12px 16px;
}

.slide-progress {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 4px;
  background: rgb(15 33 58 / 0.14);
}

.slide-progress span {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, #1f84ff, #13d59d);
}

.bottom-bar {
  gap: 24px;
  border-top: 1px solid rgb(255 255 255 / 0.08);
  padding: 0 28px;
}

.collapse-button {
  display: grid;
  width: 64px;
  height: 58px;
  place-items: center;
  border: 0;
  border-radius: 18px;
  background: rgb(255 255 255 / 0.07);
  color: #dbe5f4;
  cursor: pointer;
}

.tool-strip {
  display: flex;
  flex: 1;
  justify-content: center;
  gap: clamp(14px, 2vw, 38px);
}

.tool-button {
  display: inline-flex;
  min-width: 166px;
  height: 64px;
  align-items: center;
  justify-content: center;
  gap: 13px;
  border: 1px solid rgb(255 255 255 / 0.11);
  border-radius: 8px;
  background: linear-gradient(180deg, rgb(255 255 255 / 0.1), rgb(255 255 255 / 0.045));
  color: #f3f7ff;
  font-size: 20px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: inset 0 1px 0 rgb(255 255 255 / 0.05);
  transition:
    border-color 160ms ease,
    background-color 160ms ease,
    color 160ms ease,
    transform 160ms ease;
}

.tool-button:hover:not(:disabled) {
  border-color: rgb(122 169 255 / 0.62);
  transform: translateY(-1px);
}

.tool-button:disabled {
  cursor: not-allowed;
  opacity: 0.42;
}

.tool-button.active,
.tool-button.selected {
  border-color: rgb(71 132 242 / 0.72);
  background: rgb(37 93 167 / 0.34);
  color: #8ebcff;
  box-shadow: inset 0 0 0 1px rgb(55 120 237 / 0.22);
}

.tool-button.danger {
  border-color: rgb(255 93 103 / 0.34);
  color: #ff6e76;
}

.tool-button.danger svg {
  fill: currentColor;
}

.footer-meta {
  display: none;
}

.confirm-layer {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: grid;
  place-items: center;
  background: rgb(3 10 20 / 0.58);
  backdrop-filter: blur(7px);
}

.confirm-dialog {
  width: min(460px, calc(100vw - 32px));
  border: 1px solid rgb(255 255 255 / 0.14);
  border-radius: 14px;
  background: linear-gradient(180deg, rgb(18 32 52 / 0.98), rgb(12 21 36 / 0.98));
  box-shadow: 0 28px 80px rgb(0 0 0 / 0.42);
  padding: 28px;
}

.settings-dialog {
  width: min(620px, calc(100vw - 32px));
  border: 1px solid rgb(255 255 255 / 0.14);
  border-radius: 14px;
  background: linear-gradient(180deg, rgb(18 32 52 / 0.98), rgb(12 21 36 / 0.98));
  box-shadow: 0 28px 80px rgb(0 0 0 / 0.42);
  padding: 24px;
}

.settings-dialog header,
.settings-dialog footer,
.setting-row,
.toggle-row {
  display: flex;
  align-items: center;
}

.settings-dialog header {
  justify-content: space-between;
  margin-bottom: 18px;
}

.settings-dialog h2 {
  margin: 0;
  color: white;
  font-size: 24px;
}

.settings-dialog header button {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border: 0;
  border-radius: 8px;
  background: rgb(255 255 255 / 0.07);
  color: white;
  cursor: pointer;
}

.setting-row,
.toggle-row {
  gap: 18px;
  border-top: 1px solid rgb(255 255 255 / 0.08);
  padding: 18px 0;
}

.setting-row > span,
.toggle-row > span {
  flex: 1;
  color: #eef5ff;
  font-weight: 800;
}

.setting-row small,
.toggle-row small {
  display: block;
  margin-top: 6px;
  color: #9eacc2;
  font-size: 13px;
  font-weight: 500;
}

.setting-row input[type='range'] {
  width: 190px;
  accent-color: #2d91ff;
}

.setting-row b {
  width: 56px;
  color: #8ebcff;
  text-align: right;
}

.toggle-row input {
  width: 20px;
  height: 20px;
  accent-color: #18e193;
}

.settings-dialog footer {
  justify-content: flex-end;
  gap: 12px;
  border-top: 1px solid rgb(255 255 255 / 0.08);
  padding-top: 18px;
}

.settings-dialog footer button {
  height: 40px;
  border: 1px solid rgb(255 255 255 / 0.14);
  border-radius: 8px;
  background: rgb(255 255 255 / 0.08);
  color: white;
  padding: 0 16px;
  cursor: pointer;
}

.settings-dialog footer button.primary {
  border-color: rgb(45 145 255 / 0.38);
  background: rgb(45 145 255 / 0.18);
  color: #b9d6ff;
  font-weight: 800;
}

.confirm-dialog h2 {
  margin: 0;
  color: white;
  font-size: 24px;
}

.confirm-dialog p {
  margin: 12px 0 0;
  color: #becbe0;
  line-height: 1.75;
}

.confirm-checks {
  display: grid;
  gap: 10px;
  margin: 22px 0;
}

.confirm-checks span {
  border: 1px solid rgb(255 255 255 / 0.1);
  border-radius: 8px;
  background: rgb(255 255 255 / 0.05);
  color: #c8d4e7;
  padding: 10px 12px;
}

.confirm-checks span.ok {
  border-color: rgb(32 231 147 / 0.35);
  color: #8df1c8;
}

.confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.confirm-actions button {
  height: 40px;
  border: 1px solid rgb(255 255 255 / 0.14);
  border-radius: 8px;
  background: rgb(255 255 255 / 0.08);
  color: white;
  padding: 0 16px;
  cursor: pointer;
}

.confirm-actions button.danger {
  border-color: rgb(255 93 103 / 0.42);
  background: rgb(255 93 103 / 0.16);
  color: #ff8c92;
  font-weight: 800;
}

@media (max-width: 1400px) {
  .device-zone {
    min-width: 390px;
  }

  .camera-toggle span,
  .settings-button span,
  .upload-button span {
    display: none;
  }

  .tool-button {
    min-width: 132px;
    font-size: 17px;
  }

  .process-row {
    gap: 18px;
  }

  .step-arrow {
    left: calc(50% + 72px);
    width: 84px;
  }
}

@media (max-width: 980px) {
  .prototype-shell {
    grid-template-rows: auto minmax(0, 1fr) auto;
  }

  .top-bar {
    flex-wrap: wrap;
    height: auto;
    padding: 12px;
  }

  .brand-zone,
  .device-zone,
  .file-title {
    min-width: 0;
    width: 100%;
    justify-content: center;
  }

  .stage-area {
    padding: 10px;
  }

  .presentation-stage {
    width: 100%;
  }

  .camera-preview {
    width: 190px;
    height: 96px;
  }

  .hand-debug-panel {
    right: 10px;
    top: 116px;
    width: min(250px, calc(100vw - 20px));
  }

  .debug-video-box {
    height: 118px;
  }

  .assist-card {
    display: none;
  }

  .process-row {
    grid-template-columns: repeat(5, 1fr);
    width: 94%;
    gap: 8px;
  }

  .process-step h3 {
    font-size: 12px;
  }

  .process-step p,
  .step-arrow {
    display: none;
  }

  .bottom-bar {
    padding: 12px;
  }

  .collapse-button {
    display: none;
  }

  .tool-strip {
    flex-wrap: wrap;
  }

  .tool-button {
    min-width: 120px;
    height: 48px;
    font-size: 15px;
  }
}
</style>
