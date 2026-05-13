<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  ArrowLeft,
  ArrowRight,
  Camera,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Eraser,
  Expand,
  Clock,
  FileText,
  FileUp,
  Hand,
  Lightbulb,
  Loader2,
  Maximize2,
  Mic,
  Minus,
  Monitor,
  RotateCcw,
  Pause,
  PenLine,
  Settings,
  Sparkles,
  SlidersHorizontal,
  Square,
  UserRound,
  UploadCloud,
  Video,
  Wrench,
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

type ToolMode = 'pointer' | 'pen' | 'eraser' | 'zoom'

type Point = {
  x: number
  y: number
}

type AnnotationLine = {
  id: number
  points: Point[]
}

type OnboardingStep = {
  title: string
  summary: string
  cue: string
  steps: string[]
  notes: string[]
}

type ImportGuideSlide = {
  step: string
  navLabel: string
  title: string
  summary: string
  facts: Array<{
    label: string
    value: string
    detail: string
  }>
  tip: string
  icon: 'upload' | 'camera' | 'gesture' | 'tools'
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
    pageTurnHoldGrace?: boolean
    pageTurnHoldProgress?: number
    pageTurnHoldSeconds?: number
    pageTurnArmed?: boolean
    pageTurnCooldownRemaining?: number
    pageTurnSwipeDirection?: 'left' | 'right' | null
    pageTurnSwipeDelta?: number | null
    pageTurnSwipeVelocity?: number | null
  } | null
}

type VisionSettings = {
  cooldownSeconds: number
  swipeThreshold: number
  confidenceThreshold: number
}

type CommandSource = 'gesture' | 'voice' | 'button'
type CommandAction =
  | 'next'
  | 'previous'
  | 'pointer'
  | 'pen'
  | 'eraser'
  | 'zoom'
  | 'pause'
  | 'resume'
  | 'end'
  | 'confirm-end'
  | 'first'
  | 'last'
  | 'fullscreen'
  | 'clear-annotations'
type VoiceAction = CommandAction | 'cancel-end'

type VoiceCommandPattern = {
  action: VoiceAction
  label: string
  phrases: string[]
  weakPhrases?: string[]
  patterns?: RegExp[]
}

type VoiceTranscriptCandidate = {
  text: string
  isFinal: boolean
  confidence: number
}

type VoiceCommandMatch = VoiceTranscriptCandidate & {
  action: VoiceAction
  label: string
  score: number
}

type BackendVoiceMatch = {
  matched: boolean
  action: VoiceAction | null
  label: string | null
  score: number
  isFinal?: boolean
  text?: string
  candidates?: Array<{
    action: VoiceAction
    label: string
    text: string
    isFinal: boolean
    confidence: number
    score: number
  }>
}

type ExternalControlResult = {
  action: string
  executed: boolean
  method: string
  detail?: string | null
  platform?: string
}

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

const shellRef = ref<HTMLElement | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const stageRef = ref<HTMLElement | null>(null)
const videoRef = ref<HTMLVideoElement | null>(null)
const previewCanvasRef = ref<HTMLCanvasElement | null>(null)
const debugVideoRef = ref<HTMLVideoElement | null>(null)
const frameCanvasRef = ref<HTMLCanvasElement | null>(null)
const cameraStream = ref<MediaStream | null>(null)
const deck = ref<PresentationManifest | null>(null)
const pendingDeck = ref<PresentationManifest | null>(null)
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
const faceTrackingEnabled = ref(true)
const targetFaceCenter = ref<Point>({ x: 0.5, y: 0.5 })
const targetFaceZoom = ref(1.04)
const trackedFaceCenter = ref<Point>({ x: 0.5, y: 0.5 })
const trackedFaceZoom = ref(1.04)
const trackedFaceSize = ref(0.24)
const visionStatus = ref('视觉待机')
const pointerPosition = ref<Point>({ x: 0.72, y: 0.58 })
const zoomPoint = ref<Point>({ x: 0.72, y: 0.55 })
const annotations = ref<AnnotationLine[]>([])
const drawingLine = ref<AnnotationLine | null>(null)
const voiceEnabled = ref(false)
const voiceSupported = ref(true)
const lastVoiceText = ref('等待语音')
const lastVoiceError = ref('')
const showEndConfirm = ref(false)
const pendingEndByVoice = ref(false)
const showSettings = ref(false)
const showAnnotationActions = ref(false)
const showHandDebugPanel = ref(false)
const externalControlEnabled = ref(false)
const externalControlStatus = ref('外部控制待检测')
const fullscreenPresentationActive = ref(false)
const fullscreenChromeVisible = ref(true)
const showOnboarding = ref(false)
const expandedOnboardingStep = ref<number | null>(null)
const showImportGuide = ref(false)
const importGuideIndex = ref(0)
const visionSettings = ref<VisionSettings>({
  cooldownSeconds: 5,
  swipeThreshold: 0.02,
  confidenceThreshold: 0.45,
})
const eraserRadius = 0.022

let timerId: number | undefined
let visionTimerId: number | undefined
let previewFrameId: number | undefined
let annotationId = 0
let lastCommandAt = 0
let lastVoiceAction = ''
let lastVoiceActionAt = 0
let voiceRequestSerial = 0
let visionRequestInFlight = false
let lastFaceDetectedAt = 0
let voiceStream: MediaStream | null = null
let voiceAudioContext: AudioContext | null = null
let voiceProcessor: ScriptProcessorNode | null = null
let voiceSource: MediaStreamAudioSourceNode | null = null
let voiceChunks: Float32Array[] = []
let voiceChunkSampleCount = 0
let voiceFlushTimerId: number | undefined
let voiceRequestInFlight = false
let fullscreenChromeTimerId: number | undefined

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value))
}

function blend(current: number, target: number, factor: number) {
  return current + (target - current) * factor
}

const VOICE_FINAL_SCORE_THRESHOLD = 3.1
const VOICE_INTERIM_SCORE_THRESHOLD = 4.35
const VOICE_INTERIM_FAST_ACTIONS = new Set<VoiceAction>([
  'next',
  'previous',
  'pointer',
  'pen',
  'zoom',
  'pause',
  'resume',
  'confirm-end',
  'cancel-end',
])

const VOICE_COMMANDS: VoiceCommandPattern[] = [
  {
    action: 'next',
    label: '下一页',
    phrases: ['下一页', '下页', '下一张', '下张', '下一屏', '下一个页面', '往后翻', '向后翻', '后翻', '翻到下一页'],
    weakPhrases: ['下一个', '往后', '向后', '前进', '继续播放', 'next'],
    patterns: [/下(?:一)?(?:页|张|屏)/, /(?:往后|向后|后翻|前进)(?:翻|一页|一张)?/],
  },
  {
    action: 'previous',
    label: '上一页',
    phrases: ['上一页', '上页', '上一张', '上张', '前一页', '前一张', '上一屏', '返回上一页', '往前翻', '向前翻', '前翻'],
    weakPhrases: ['上一个', '返回', '往前', '向前', '后退', 'previous', 'back'],
    patterns: [/(?:上|前)(?:一)?(?:页|张|屏)/, /(?:往前|向前|前翻|后退)(?:翻|一页|一张)?/],
  },
  {
    action: 'pointer',
    label: '空气指针',
    phrases: ['空气指针', '打开指针', '切换指针', '指针模式', '激光笔', '光标', '指示器', '鼠标'],
    weakPhrases: ['指针', 'pointer'],
  },
  {
    action: 'pen',
    label: '标注模式',
    phrases: ['标注模式', '打开标注', '开始标注', '画笔模式', '打开画笔', '批注模式', '写字模式', '画线'],
    weakPhrases: ['标注', '画笔', '批注', '手写', '涂鸦', 'pen'],
  },
  {
    action: 'zoom',
    label: '区域放大',
    phrases: ['区域放大', '局部放大', '打开放大', '放大模式', '放大镜', '缩放模式'],
    weakPhrases: ['放大', '缩放', '区域', 'zoom'],
  },
  {
    action: 'pause',
    label: '暂停识别',
    phrases: ['暂停识别', '暂停演示', '暂停播放', '暂停一下', '先暂停', '停一下', '停止识别'],
    weakPhrases: ['暂停', 'pause'],
  },
  {
    action: 'resume',
    label: '继续识别',
    phrases: ['继续识别', '恢复识别', '继续演示', '继续播放', '恢复播放', '接着讲', '继续讲'],
    weakPhrases: ['继续', '恢复', '开始识别', 'resume'],
  },
  {
    action: 'end',
    label: '结束演示',
    phrases: ['结束演示', '结束放映', '结束展示', '退出演示', '退出放映', '停止演示', '关闭演示'],
    weakPhrases: ['结束吧', '退出吧', 'end'],
  },
  {
    action: 'first',
    label: '第一页',
    phrases: ['第一页', '第一张', '回到第一页', '回到首页', '跳到第一页', '返回开头'],
    weakPhrases: ['首页', '开头'],
  },
  {
    action: 'last',
    label: '最后一页',
    phrases: ['最后一页', '最后一张', '跳到最后一页', '到最后一页', '放到最后'],
    weakPhrases: ['尾页', '末页', '结尾'],
  },
  {
    action: 'fullscreen',
    label: '全屏放映',
    phrases: ['进入全屏', '全屏放映', '开始放映', '放映模式', '全屏模式'],
    weakPhrases: ['全屏'],
  },
  {
    action: 'clear-annotations',
    label: '清除标注',
    phrases: ['清除标注', '清空标注', '擦除标注', '清除画笔', '清空画笔', '删除标注'],
    weakPhrases: ['清屏'],
  },
  {
    action: 'confirm-end',
    label: '确认结束',
    phrases: ['确认结束', '确定结束', '确认退出', '确定退出', '确认关闭'],
    weakPhrases: ['确认', '确定'],
  },
  {
    action: 'cancel-end',
    label: '继续演示',
    phrases: ['取消结束', '不要结束', '不结束', '别结束', '继续演示', '返回演示'],
    weakPhrases: ['取消', '返回', '继续'],
  },
]

function normaliseVoiceText(text: string) {
  return text
    .toLowerCase()
    .replace(/ppt|powerpoint/g, '演示')
    .replace(/幻灯片|页面/g, '页')
    .replace(/[\s,，.。!！?？:：;；、"'“”‘’`~·()（）[\]【】{}<>《》/\\|-]/g, '')
}

function phraseScore(command: string, phrase: string, strong: boolean) {
  const normalisedPhrase = normaliseVoiceText(phrase)
  if (!normalisedPhrase || !command.includes(normalisedPhrase)) return 0

  const base = command === normalisedPhrase ? 5.4 : strong ? 4 : 2.35
  const lengthBonus = Math.min(normalisedPhrase.length * (strong ? 0.14 : 0.08), strong ? 1.15 : 0.68)
  const positionBonus = command.endsWith(normalisedPhrase) ? 0.16 : 0
  return base + lengthBonus + positionBonus
}

function commandScore(pattern: VoiceCommandPattern, command: string) {
  let score = 0
  for (const phrase of pattern.phrases) {
    score = Math.max(score, phraseScore(command, phrase, true))
  }
  for (const phrase of pattern.weakPhrases ?? []) {
    score = Math.max(score, phraseScore(command, phrase, false))
  }
  for (const matcher of pattern.patterns ?? []) {
    if (matcher.test(command)) score = Math.max(score, 3.85)
  }
  return score
}

function commandPoolForCurrentState() {
  if (showEndConfirm.value) {
    return VOICE_COMMANDS.filter((command) => command.action === 'confirm-end' || command.action === 'cancel-end')
  }
  return VOICE_COMMANDS.filter((command) => command.action !== 'confirm-end' && command.action !== 'cancel-end')
}

function matchVoiceCandidate(candidate: VoiceTranscriptCandidate): VoiceCommandMatch | null {
  const command = normaliseVoiceText(candidate.text)
  if (!command) return null

  let best: VoiceCommandMatch | null = null
  for (const pattern of commandPoolForCurrentState()) {
    const score = commandScore(pattern, command)
    if (score <= 0) continue

    const confidenceBonus = candidate.confidence > 0 ? Math.min(candidate.confidence, 1) * 0.55 : 0
    const finalBonus = candidate.isFinal ? 0.45 : 0
    const match: VoiceCommandMatch = {
      ...candidate,
      action: pattern.action,
      label: pattern.label,
      score: score + confidenceBonus + finalBonus,
    }
    if (!best || match.score > best.score) best = match
  }

  return best
}

function collectVoiceCandidates(event: any): VoiceTranscriptCandidate[] {
  const results = event?.results
  if (!results?.length) return []

  const startIndex = typeof event.resultIndex === 'number' ? event.resultIndex : Math.max(0, results.length - 1)
  const candidates = new Map<string, VoiceTranscriptCandidate>()

  for (let index = startIndex; index < results.length; index += 1) {
    const result = results[index]
    const alternativeCount = Math.min(Number(result?.length ?? 0), 3)
    for (let alternativeIndex = 0; alternativeIndex < alternativeCount; alternativeIndex += 1) {
      const alternative = result[alternativeIndex]
      const text = String(alternative?.transcript ?? '').trim()
      const key = normaliseVoiceText(text)
      if (!key) continue

      const candidate: VoiceTranscriptCandidate = {
        text,
        isFinal: Boolean(result?.isFinal),
        confidence: typeof alternative?.confidence === 'number' ? alternative.confidence : 0,
      }
      const previous = candidates.get(key)
      const previousRank = previous ? Number(previous.isFinal) * 2 + previous.confidence : -1
      const candidateRank = Number(candidate.isFinal) * 2 + candidate.confidence
      if (!previous || candidateRank >= previousRank) candidates.set(key, candidate)
    }
  }

  return Array.from(candidates.values()).sort((left, right) => {
    if (left.isFinal !== right.isFinal) return Number(right.isFinal) - Number(left.isFinal)
    if (left.confidence !== right.confidence) return right.confidence - left.confidence
    return right.text.length - left.text.length
  })
}

function bestVoiceMatch(candidates: VoiceTranscriptCandidate[]) {
  return candidates
    .map((candidate) => matchVoiceCandidate(candidate))
    .filter((match): match is VoiceCommandMatch => Boolean(match))
    .sort((left, right) => right.score - left.score)[0] ?? null
}

function isReliableVoiceMatch(match: VoiceCommandMatch) {
  if (!match.isFinal && !VOICE_INTERIM_FAST_ACTIONS.has(match.action)) return false
  return match.score >= (match.isFinal ? VOICE_FINAL_SCORE_THRESHOLD : VOICE_INTERIM_SCORE_THRESHOLD)
}

function voiceActionCooldown(action: VoiceAction) {
  if (action === 'next' || action === 'previous') return 650
  if (action === 'end' || action === 'confirm-end' || action === 'cancel-end') return 1200
  if (action === 'pause' || action === 'resume') return 520
  return 460
}

function runVoiceAction(match: VoiceCommandMatch) {
  const now = Date.now()
  if (lastVoiceAction === match.action && now - lastVoiceActionAt < voiceActionCooldown(match.action)) return

  lastVoiceAction = match.action
  lastVoiceActionAt = now
  lastVoiceText.value = match.label

  if (match.action === 'cancel-end') {
    cancelEndPresentation()
    return
  }

  executeCommand(match.action, 'voice')
}

function runBackendVoiceAction(match: BackendVoiceMatch) {
  if (!match.action || !match.label) return
  runVoiceAction({
    text: match.text ?? match.label,
    isFinal: Boolean(match.isFinal),
    confidence: 1,
    action: match.action,
    label: match.label,
    score: match.score,
  })
}

async function recogniseVoiceOnBackend(candidates: VoiceTranscriptCandidate[]) {
  const response = await fetch(`${apiBase}/api/voice/recognize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      candidates,
      showEndConfirm: showEndConfirm.value,
    }),
  })
  if (!response.ok) throw new Error('voice recognition failed')
  return (await response.json()) as BackendVoiceMatch
}

async function handleVoiceCandidates(candidates: VoiceTranscriptCandidate[]) {
  if (!candidates.length) return

  const serial = ++voiceRequestSerial
  try {
    const backendMatch = await recogniseVoiceOnBackend(candidates)
    if (serial !== voiceRequestSerial) return

    const backendLabel = backendMatch.label ?? candidates[0].text
    lastVoiceText.value = `${backendLabel}${backendMatch.isFinal === false ? '...' : ''}`
    if (backendMatch.matched) runBackendVoiceAction(backendMatch)
    return
  } catch {
    // Fall back to local command matching when the backend is unavailable.
  }

  const match = bestVoiceMatch(candidates)
  const fallback = candidates[0]
  if (!match) {
    lastVoiceText.value = `${fallback.text}${fallback.isFinal ? '' : '...'}`
    return
  }

  lastVoiceText.value = `${match.label}${match.isFinal ? '' : '...'}`
  if (isReliableVoiceMatch(match)) runVoiceAction(match)
}

const currentSlide = computed(() => deck.value?.slides[currentIndex.value] ?? null)
const hasDeck = computed(() => Boolean(deck.value?.slides.length))
const activeImportGuideSlide = computed(() => importGuideSlides[importGuideIndex.value] ?? importGuideSlides[0])
const isImportGuideLastStep = computed(() => importGuideIndex.value >= importGuideSlides.length - 1)
const importGuideDeckReady = computed(() => Boolean(pendingDeck.value) && !isUploading.value)
const canEnterImportedDeck = computed(() => isImportGuideLastStep.value && importGuideDeckReady.value)
const importGuideProgressText = computed(() => `第 ${importGuideIndex.value + 1} 步 / ${importGuideSlides.length}`)
const importGuideStatusText = computed(() => {
  if (isUploading.value) return '正在转换 PPT 页面'
  if (pendingDeck.value) return 'PPT 已转换完成'
  return '等待导入 PPT'
})
const importGuidePrimaryText = computed(() => {
  if (!isImportGuideLastStep.value) return '下一步'
  if (canEnterImportedDeck.value) return '已阅读'
  return '等待 PPT 转换完成'
})
const importGuideFooterText = computed(() => {
  if (!isImportGuideLastStep.value) return '依次看完这几项准备内容，最后即可进入放映。'
  if (canEnterImportedDeck.value) return '准备完成，可以进入放映界面。'
  return '准备内容已看完，等待 PPT 转换完成后即可进入放映。'
})
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
  if (gesture?.action === 'previous') return '激活手势挥动：上一页'
  if (visionResult.value?.debug?.pageTurnArmed) return '翻页模式已激活：右挥下一页，左挥上一页'
  if (visionResult.value?.debug?.pageTurnPoseMatched) return '保持 1 秒后进入翻页模式'
  if (gesture?.action === 'pointer') return '指向：空气指针'
  if (!cameraEnabled.value) return '点击顶部摄像头后识别手势'
  if (activeMode.value === 'pen') return '标注模式：拖动画笔'
  if (activeMode.value === 'zoom') return '区域放大：移动定位'
  return '食指中指伸出、无名指小指收起，保持 1 秒后左右挥手翻页'
})
const voiceText = computed(() => {
  if (!voiceSupported.value) return '语音：浏览器不支持'
  if (!voiceEnabled.value) return '语音：点击麦克风开启'
  return `语音：${lastVoiceText.value}${lastVoiceError.value ? ` (${lastVoiceError.value})` : ''}`
})
const latencyText = computed(() => {
  if (recognitionPaused.value) return '识别已暂停'
  return `延迟 ${visionResult.value?.latencyMs ?? 38}ms`
})
const faceGuideStyle = computed(() => {
  const box = visionResult.value?.face?.box
  const width = box ? clamp(box.width * 58, 18, 28) : 21
  const height = box ? clamp(box.height * 100, 34, 58) : 42

  return {
    left: `${29 - width / 2}%`,
    top: `${50 - height / 2}%`,
    width: `${width}%`,
    height: `${height}%`,
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
  if (debug?.pageTurnArmed) return '等待挥动'
  if (debug?.pageTurnPoseMatched) return debug.pageTurnHoldGrace ? '保持容错中' : '保持姿势中'
  return '手部已检测'
})
const debugDetailText = computed(() => {
  const debug = visionResult.value?.debug
  const hand = visionResult.value?.hand
  if (debug?.mediapipeAvailable === false) return debug.mediapipeError || '请安装 mediapipe 后重启后端'
  if (!cameraEnabled.value) return '开启摄像头后显示识别结果'
  if (!hand) return '把手放进摄像头画面，尽量保持掌心清晰'
  const holdText = debug?.pageTurnPoseMatched
    ? ` · ${debug.pageTurnHoldGrace ? '容错保持' : '保持'} ${Math.round((debug.pageTurnHoldProgress ?? 0) * 100)}%`
    : ''
  const cooldownText = (debug?.pageTurnCooldownRemaining ?? 0) > 0
    ? ` · 冷却 ${debug?.pageTurnCooldownRemaining?.toFixed(1)}s`
    : ''
  const swipeText = debug?.pageTurnSwipeDelta
    ? ` · 挥动 ${debug.pageTurnSwipeDirection || '-'} ${debug.pageTurnSwipeDelta.toFixed(2)}`
    : ''
  return `${hand.source || debug?.handSource || 'unknown'} · ${hand.pose} · ${(hand.confidence * 100).toFixed(0)}%${holdText}${swipeText}${cooldownText}`
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

const onboardingSteps: OnboardingStep[] = [
  {
    title: '\u5bfc\u5165\u4e0e\u653e\u6620\u51c6\u5907',
    summary: '\u5148\u5bfc\u5165 PPT\uff0c\u7cfb\u7edf\u4f1a\u81ea\u52a8\u8fdb\u5165\u653e\u6620\u754c\u9762\u3002',
    cue: '\u9002\u7528\u573a\u666f\uff1a\u9996\u6b21\u5f00\u59cb\u6f14\u793a\u6216\u66f4\u6362\u65b0\u7684 PPT \u6587\u4ef6\u3002',
    steps: [
      '\u70b9\u51fb\u201c\u5bfc\u5165 PPT \u5f00\u59cb\u653e\u6620\u201d\u9009\u62e9 .ppt \u6216 .pptx \u6587\u4ef6\u3002',
      '\u7b49\u5f85\u7cfb\u7edf\u5b8c\u6210\u8f6c\u6362\uff0c\u4e0d\u8981\u5728\u8f6c\u6362\u8fc7\u7a0b\u4e2d\u91cd\u590d\u70b9\u51fb\u3002',
      '\u8fdb\u5165\u4e3b\u754c\u9762\u540e\u518d\u5f00\u542f\u6444\u50cf\u5934\u5e76\u5f00\u59cb\u6f14\u793a\u3002',
    ],
    notes: [
      '\u53ea\u652f\u6301 .ppt \u548c .pptx \u6587\u4ef6\u3002',
      '\u5efa\u8bae\u4f7f\u7528 16:9 \u9875\u9762\u6bd4\u4f8b\uff0c\u6295\u5f71\u663e\u793a\u66f4\u7a33\u5b9a\u3002',
      '\u5bfc\u5165\u65b0\u6587\u4ef6\u4f1a\u66ff\u6362\u5f53\u524d\u653e\u6620\u5185\u5bb9\u3002',
    ],
  },
  {
    title: '\u6444\u50cf\u5934\u4e0e\u7ad9\u4f4d',
    summary: '\u7ad9\u4f4d\u7a33\u5b9a\u540e\uff0c\u624b\u52bf\u8bc6\u522b\u4f1a\u66f4\u51c6\u786e\u3002',
    cue: '\u9002\u7528\u573a\u666f\uff1a\u6b63\u5f0f\u6f14\u793a\u524d\u7684\u73af\u5883\u68c0\u67e5\u548c\u8bd5\u8fd0\u884c\u3002',
    steps: [
      '\u8ba9\u4eba\u8138\u51fa\u73b0\u5728\u5de6\u4e0a\u89d2\u9884\u89c8\u533a\u5185\uff0c\u4fdd\u6301\u8ddd\u79bb\u7ea6 2 \u5230 3 \u7c73\u3002',
      '\u624b\u52bf\u52a8\u4f5c\u5c3d\u91cf\u5728\u80f8\u524d\u5230\u80a9\u90e8\u8303\u56f4\u5185\u5b8c\u6210\u3002',
      '\u5148\u786e\u4fdd\u5149\u7ebf\u5747\u5300\uff0c\u518d\u8fdb\u884c\u624b\u52bf\u6d4b\u8bd5\u3002',
    ],
    notes: [
      '\u907f\u514d\u9006\u5149\u3001\u53cd\u5149\u6216\u80cc\u666f\u592a\u590d\u6742\u3002',
      '\u624b\u638c\u4e0d\u8981\u88ab\u8eab\u4f53\u3001\u8bb2\u684c\u6216\u8863\u7269\u906e\u6321\u3002',
      '\u5982\u9700\u6392\u67e5\u95ee\u9898\uff0c\u53ef\u5728\u8bbe\u7f6e\u4e2d\u6253\u5f00\u624b\u52bf\u8c03\u8bd5\u9762\u677f\u3002',
    ],
  },
  {
    title: '\u624b\u52bf\u3001\u8bed\u97f3\u4e0e\u6807\u6ce8',
    summary: '\u6f14\u793a\u8fc7\u7a0b\u4e2d\uff0c\u4e3b\u8981\u4f7f\u7528\u624b\u52bf\u3001\u8bed\u97f3\u548c\u5de5\u5177\u680f\u5b8c\u6210\u64cd\u4f5c\u3002',
    cue: '\u9002\u7528\u573a\u666f\uff1a\u6b63\u5728\u8bb2\u89e3 PPT \u65f6\u7684\u5e38\u7528\u63a7\u5236\u3002',
    steps: [
      '\u624b\u52bf\u7528\u4e8e\u4e0a\u4e00\u9875\u3001\u4e0b\u4e00\u9875\u548c\u6307\u9488\u8ddf\u968f\u3002',
      '\u8bed\u97f3\u53ef\u7528\u4e8e\u7ffb\u9875\u3001\u5207\u6362\u6807\u6ce8\u3001\u533a\u57df\u653e\u5927\u3001\u6682\u505c\u8bc6\u522b\u3002',
      '\u6807\u6ce8\u5199\u9519\u65f6\uff0c\u5728\u201c\u4fee\u6b63\u201d\u91cc\u4f7f\u7528\u6a61\u76ae\u64e6\u6216\u4e00\u952e\u6e05\u9664\u3002',
    ],
    notes: [
      '\u8fde\u7eed\u7ffb\u9875\u5b58\u5728\u51b7\u5374\u65f6\u95f4\uff0c\u8bf7\u4e0d\u8981\u5feb\u901f\u91cd\u590d\u6325\u624b\u3002',
      '\u5168\u5c4f\u653e\u6620\u540e\uff0c\u4e0a\u4e0b\u5de5\u5177\u680f\u4f1a\u5728\u9f20\u6807\u79fb\u52a8\u65f6\u91cd\u65b0\u663e\u793a\u3002',
      '\u7ed3\u675f\u6f14\u793a\u65f6\u9700\u8981\u4e8c\u6b21\u786e\u8ba4\uff0c\u907f\u514d\u8bef\u89e6\u3002',
    ],
  },
]

const importGuideSlides: ImportGuideSlide[] = [
  {
    step: '第一步',
    navLabel: '导入',
    title: '先完成导入，再\n进入放映',
    summary: '选择 PPT 后，系统会先完成页面转换。转换完成并阅读完这份说明后，才能进入放映界面。',
    facts: [
      {
        label: '文件格式',
        value: '.ppt / .pptx',
        detail: '建议优先使用 16:9 页面比例，投影显示更稳定。',
      },
      {
        label: '进入条件',
        value: '转换完成 + 已阅读',
        detail: '两项都满足后，最后一页按钮才可进入放映。',
      },
      {
        label: '等待时间',
        value: '与页数相关',
        detail: '文件页数越多，转换时间会略长一些。',
      },
    ],
    tip: '看到右上角“PPT 已转换完成”后，再点击最后一步的“已阅读”进入放映。',
    icon: 'upload',
  },
  {
    step: '第二步',
    navLabel: '站位',
    title: '站位稳定，\n识别会更准确',
    summary: 'AirSlide 会通过摄像头识别人脸和手势。正式演示前，先确认人脸和手部都能稳定进入识别区域。',
    facts: [
      {
        label: '推荐距离',
        value: '2 到 3 米',
        detail: '让人脸稳定出现在左上角预览区内。',
      },
      {
        label: '手势位置',
        value: '胸前到肩部',
        detail: '手势动作尽量在身体前方完成，不要离镜头太边缘。',
      },
      {
        label: '环境要求',
        value: '光线均匀',
        detail: '尽量避免逆光、反光和手部被身体或讲台遮挡。',
      },
    ],
    tip: '开始演示前先看一眼左上角预览区，人脸框稳定后再开始做翻页手势。',
    icon: 'camera',
  },
  {
    step: '第三步',
    navLabel: '控制',
    title: '先摆出手势，再\n挥手翻页',
    summary: '翻页手势有固定规则。请先摆出正确手型并保持 1 秒，系统激活后再向左或向右挥手翻页。',
    facts: [
      {
        label: '激活手型',
        value: '食指 + 中指伸出',
        detail: '无名指和小指需要收起，系统才会进入翻页准备状态。',
      },
      {
        label: '保持时间',
        value: '1 秒',
        detail: '手型保持约 1 秒后，系统才会接受挥手翻页。',
      },
      {
        label: '翻页间隔',
        value: '5 秒',
        detail: '每次翻页后有 5 秒冷却时间，避免连续误触。',
      },
    ],
    tip: '如果手势没有触发，先检查手型是否正确，再确认是否仍在 5 秒冷却时间内。',
    icon: 'gesture',
  },
  {
    step: '第四步',
    navLabel: '工具',
    title: '放映工具都在\n底部工具栏',
    summary: '进入放映后，常用操作都集中在底部工具栏，包括指针、标注、修正、放大和全屏。',
    facts: [
      {
        label: '标注修正',
        value: '橡皮擦 / 一键清除',
        detail: '写错时可以局部擦除，也可以直接清空全部标记。',
      },
      {
        label: '全屏模式',
        value: '工具栏自动隐藏',
        detail: '进入全屏后，鼠标移动时会重新显示上下工具栏。',
      },
      {
        label: '语音辅助',
        value: '可与手势配合',
        detail: '语音可用于翻页、切换工具和暂停识别等常用操作。',
      },
    ],
    tip: '准备完成后，点击“已阅读”进入放映；如果按钮不可用，请先等待 PPT 转换完成。',
    icon: 'tools',
  },
]

function slideUrl(slide: Slide) {
  if (/^https?:\/\//.test(slide.url)) return slide.url
  return `${apiBase}${slide.url}`
}

function pickFile() {
  fileInput.value?.click()
}

function resetImportGuideFlow() {
  showImportGuide.value = false
  importGuideIndex.value = 0
  pendingDeck.value = null
}

function startImportGuideFlow() {
  showOnboarding.value = false
  showImportGuide.value = true
  importGuideIndex.value = 0
  pendingDeck.value = null
}

function dismissOnboarding() {
  showOnboarding.value = false
}

function startWithGuide() {
  expandedOnboardingStep.value = null
  showOnboarding.value = true
}

function previousImportGuideStep() {
  importGuideIndex.value = Math.max(0, importGuideIndex.value - 1)
}

function activatePresentation(manifest: PresentationManifest) {
  deck.value = manifest
  currentIndex.value = 0
  activeMode.value = 'pointer'
  recognitionPaused.value = false
  annotations.value = []
  drawingLine.value = null
  showAnnotationActions.value = false
  showEndConfirm.value = false
  pendingEndByVoice.value = false
}

function enterImportedPresentation() {
  if (!canEnterImportedDeck.value || !pendingDeck.value) return
  activatePresentation(pendingDeck.value)
  resetImportGuideFlow()
}

function nextImportGuideStep() {
  if (isImportGuideLastStep.value) {
    enterImportedPresentation()
    return
  }
  importGuideIndex.value = Math.min(importGuideSlides.length - 1, importGuideIndex.value + 1)
}

function validateFile(file: File) {
  if (!/\.(ppt|pptx)$/i.test(file.name)) {
    throw new Error('请上传 .ppt 或 .pptx 文件')
  }
}

async function uploadFile(file: File) {
  try {
    validateFile(file)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'PPT 载入失败'
    return
  }
  startImportGuideFlow()
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

    pendingDeck.value = (await response.json()) as PresentationManifest
  } catch (error) {
    resetImportGuideFlow()
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
  goToSlide((hasDeck.value ? currentIndex.value : demoIndex.value) - 1)
}

function nextSlide() {
  goToSlide((hasDeck.value ? currentIndex.value : demoIndex.value) + 1)
}

function canTurnSlide(action: CommandAction) {
  if (action === 'previous') return (hasDeck.value ? currentIndex.value : demoIndex.value) > 0
  if (action === 'next') return (hasDeck.value ? currentIndex.value : demoIndex.value) < slideCount.value - 1
  return true
}

function externalControlAction(action: CommandAction) {
  if (action === 'confirm-end') return 'end'
  if (action === 'resume') return 'resume'
  if (action === 'fullscreen') return 'fullscreen'
  if (['next', 'previous', 'first', 'last', 'pause', 'end'].includes(action)) return action
  return null
}

function executeCommand(action: CommandAction, source: CommandSource = 'button') {
  const now = Date.now()
  const needsCooldown = action === 'next' || action === 'previous'
  if (needsCooldown && !canTurnSlide(action)) return

  if (action !== 'clear-annotations') {
    showAnnotationActions.value = false
  }
  if (fullscreenPresentationActive.value) {
    fullscreenChromeVisible.value = true
  }

  const commandCooldownMs = source === 'gesture' ? 5000 : source === 'voice' ? 620 : 950
  if (needsCooldown && now - lastCommandAt < commandCooldownMs) return
  if (needsCooldown) lastCommandAt = now

  if (action === 'next') nextSlide()
  if (action === 'previous') previousSlide()
  if (action === 'first') goToSlide(0)
  if (action === 'last') goToSlide(slideCount.value - 1)
  if (action === 'fullscreen') void toggleFullscreen()
  if (action === 'clear-annotations') clearAnnotations()
  if (action === 'pointer') activeMode.value = 'pointer'
  if (action === 'pen') activeMode.value = 'pen'
  if (action === 'eraser') activeMode.value = 'eraser'
  if (action === 'zoom') activeMode.value = 'zoom'
  if (action === 'pause') recognitionPaused.value = true
  if (action === 'resume') recognitionPaused.value = false
  if (action === 'end') {
    showEndConfirm.value = true
    pendingEndByVoice.value = source === 'voice'
  }
  if (action === 'confirm-end') confirmEndPresentation()

  const externalAction = externalControlAction(action)
  if (externalControlEnabled.value && externalAction) {
    void sendExternalControl(externalAction)
  }
}

async function sendExternalControl(action: string) {
  try {
    const response = await fetch(`${apiBase}/api/presentation/control`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action }),
    })
    if (!response.ok) throw new Error('control request failed')
    const result = (await response.json()) as ExternalControlResult
    if (!result.executed) {
      errorMessage.value = result.detail || '外部 PowerPoint 控制未执行，请确认放映窗口在前台'
      return
    }
    errorMessage.value = ''
  } catch {
    errorMessage.value = '外部 PowerPoint 控制暂不可用'
  }
}

async function loadExternalControlStatus() {
  try {
    const response = await fetch(`${apiBase}/api/presentation/control/status`)
    if (!response.ok) throw new Error('control status failed')
    const status = (await response.json()) as {
      platform?: string
      keyboardFallbackAvailable?: boolean
      powerpointComAvailable?: boolean
    }
    const platform = status.platform || 'Unknown'
    if (status.powerpointComAvailable) {
      externalControlStatus.value = `${platform} · PowerPoint COM 可用`
    } else if (status.keyboardFallbackAvailable) {
      externalControlStatus.value = `${platform} · 系统按键控制可用`
    } else {
      externalControlStatus.value = `${platform} · 未检测到可用外部控制`
    }
  } catch {
    externalControlStatus.value = '外部控制状态获取失败'
  }
}

async function enterFullscreen() {
  if (!shellRef.value || document.fullscreenElement) return
  await shellRef.value.requestFullscreen()
}

async function toggleFullscreen() {
  if (document.fullscreenElement === shellRef.value) {
    await document.exitFullscreen()
    return
  }
  await enterFullscreen()
}

function clearFullscreenChromeTimer() {
  if (fullscreenChromeTimerId !== undefined) {
    window.clearTimeout(fullscreenChromeTimerId)
    fullscreenChromeTimerId = undefined
  }
}

function scheduleFullscreenChromeHide() {
  clearFullscreenChromeTimer()
  if (!fullscreenPresentationActive.value || showSettings.value || showEndConfirm.value) return
  fullscreenChromeTimerId = window.setTimeout(() => {
    fullscreenChromeVisible.value = false
  }, 1800)
}

function revealFullscreenChrome() {
  if (!fullscreenPresentationActive.value) return
  fullscreenChromeVisible.value = true
  scheduleFullscreenChromeHide()
}

function handleFullscreenChange() {
  fullscreenPresentationActive.value = document.fullscreenElement === shellRef.value
  fullscreenChromeVisible.value = true
  if (fullscreenPresentationActive.value) {
    scheduleFullscreenChromeHide()
  } else {
    clearFullscreenChromeTimer()
  }
}

function startVisionLoop() {
  window.clearInterval(visionTimerId)
  visionStatus.value = '视觉识别中'
  visionTimerId = window.setInterval(() => {
    void captureVisionFrame()
  }, 90)
}

function stopVisionLoop() {
  window.clearInterval(visionTimerId)
  visionTimerId = undefined
  visionStatus.value = '视觉待机'
  visionResult.value = null
  visionRequestInFlight = false
  lastFaceDetectedAt = 0
  targetFaceCenter.value = { x: 0.5, y: 0.5 }
  targetFaceZoom.value = 1.04
  trackedFaceCenter.value = { x: 0.5, y: 0.5 }
  trackedFaceZoom.value = 1.04
  trackedFaceSize.value = 0.24
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
  if (visionRequestInFlight) return

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
  visionRequestInFlight = true
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
    visionStatus.value = '视觉请求失败，请检查后端服务'
  } finally {
    visionRequestInFlight = false
  }
}

function applyVisionResult(payload: VisionResult) {
  visionResult.value = payload
  updateTrackedFaceCenter(payload.face)
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

function updateTrackedFaceCenter(face: VisionResult['face']) {
  const now = performance.now()
  if (face) {
    lastFaceDetectedAt = now
  }

  const shouldHoldLastTarget = !face && now - lastFaceDetectedAt < 420
  const target = shouldHoldLastTarget ? targetFaceCenter.value : (face?.center ?? { x: 0.5, y: 0.5 })
  targetFaceCenter.value = {
    x: clamp(target.x, 0.1, 0.9),
    y: clamp(target.y, 0.16, 0.84),
  }

  if (!faceTrackingEnabled.value || (!face && !shouldHoldLastTarget)) {
    targetFaceZoom.value = 1.04
    return
  }

  if (!face) {
    return
  }

  const observedFaceSize = clamp((face.box.width + face.box.height * 0.6) / 1.6, 0.16, 0.42)
  trackedFaceSize.value = blend(trackedFaceSize.value, observedFaceSize, 0.18)

  // Ignore tiny width changes caused by lateral motion and detector jitter.
  if (Math.abs(observedFaceSize - trackedFaceSize.value) < 0.012) {
    return
  }

  // Face larger => user closer => zoom out slightly.
  // Face smaller => user farther => zoom in slightly.
  const normalisedDistance = clamp((0.24 - trackedFaceSize.value) / 0.09, -1, 1)
  targetFaceZoom.value = clamp(1.08 + normalisedDistance * 0.2, 0.96, 1.28)
}

function renderPreviewFrame() {
  if (!previewCanvasRef.value || !videoRef.value) return

  const canvas = previewCanvasRef.value
  const video = videoRef.value
  const context = canvas.getContext('2d')
  if (!context) return

  const width = canvas.clientWidth || 1
  const height = canvas.clientHeight || 1
  const dpr = window.devicePixelRatio || 1
  const renderWidth = Math.max(1, Math.round(width * dpr))
  const renderHeight = Math.max(1, Math.round(height * dpr))

  if (canvas.width !== renderWidth || canvas.height !== renderHeight) {
    canvas.width = renderWidth
    canvas.height = renderHeight
  }

  context.setTransform(1, 0, 0, 1, 0, 0)
  context.clearRect(0, 0, renderWidth, renderHeight)

  if (video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA || video.videoWidth === 0 || video.videoHeight === 0) {
    return
  }

  const centerFactor = faceTrackingEnabled.value ? 0.1 : 0.08
  const zoomFactor = faceTrackingEnabled.value ? 0.06 : 0.04
  const edgeDistance = Math.min(
    targetFaceCenter.value.x,
    1 - targetFaceCenter.value.x,
    targetFaceCenter.value.y,
    1 - targetFaceCenter.value.y,
  )
  trackedFaceCenter.value = {
    x: clamp(blend(trackedFaceCenter.value.x, targetFaceCenter.value.x, centerFactor), 0.1, 0.9),
    y: clamp(blend(trackedFaceCenter.value.y, targetFaceCenter.value.y, centerFactor), 0.16, 0.84),
  }
  const edgeSafeZoom = edgeDistance < 0.16 ? Math.min(targetFaceZoom.value, 1.08) : targetFaceZoom.value
  trackedFaceZoom.value = blend(trackedFaceZoom.value, edgeSafeZoom, zoomFactor)

  const sourceWidth = video.videoWidth
  const sourceHeight = video.videoHeight
  const outputAspect = renderWidth / renderHeight
  const sourceAspect = sourceWidth / sourceHeight
  const zoom = faceTrackingEnabled.value ? trackedFaceZoom.value : 1

  let cropWidth = sourceWidth
  let cropHeight = sourceHeight

  if (sourceAspect > outputAspect) {
    cropWidth = sourceHeight * outputAspect
  } else {
    cropHeight = sourceWidth / outputAspect
  }

  cropWidth = cropWidth / zoom
  cropHeight = cropHeight / zoom

  const previewCenterX = faceTrackingEnabled.value ? clamp(trackedFaceCenter.value.x, 0.12, 0.88) : 0.5
  const previewCenterY = faceTrackingEnabled.value ? clamp(trackedFaceCenter.value.y, 0.18, 0.82) : 0.5
  const rawCenterX = 1 - previewCenterX
  const rawCenterY = previewCenterY
  const sourceX = clamp(rawCenterX * sourceWidth - cropWidth / 2, 0, sourceWidth - cropWidth)
  const sourceY = clamp(rawCenterY * sourceHeight - cropHeight / 2, 0, sourceHeight - cropHeight)

  context.save()
  context.translate(renderWidth, 0)
  context.scale(-1, 1)
  context.drawImage(video, sourceX, sourceY, cropWidth, cropHeight, 0, 0, renderWidth, renderHeight)
  context.restore()
}

function startPreviewLoop() {
  stopPreviewLoop()

  const step = () => {
    renderPreviewFrame()
    previewFrameId = window.requestAnimationFrame(step)
  }

  previewFrameId = window.requestAnimationFrame(step)
}

function stopPreviewLoop() {
  if (previewFrameId !== undefined) {
    window.cancelAnimationFrame(previewFrameId)
    previewFrameId = undefined
  }
}

async function attachVideoStream(video: HTMLVideoElement | null, stream: MediaStream | null) {
  if (!video || !stream) return
  if (video.srcObject !== stream) {
    video.srcObject = stream
  }
  try {
    await video.play()
  } catch {
    // Ignore autoplay timing issues and retry when the panel updates again.
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
    await attachVideoStream(videoRef.value, stream)
    await attachVideoStream(debugVideoRef.value, stream)
    startPreviewLoop()
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
  stopPreviewLoop()
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
    void startVoice()
  }
}

watch(
  [cameraStream, showHandDebugPanel, debugVideoRef],
  async ([stream, visible, debugVideo]) => {
    if (!stream || !visible || !debugVideo) return
    await nextTick()
    await attachVideoStream(debugVideoRef.value, stream)
  },
)

function encodeWav(samples: Float32Array, sampleRate: number) {
  const buffer = new ArrayBuffer(44 + samples.length * 2)
  const view = new DataView(buffer)
  writeAscii(view, 0, 'RIFF')
  view.setUint32(4, 36 + samples.length * 2, true)
  writeAscii(view, 8, 'WAVE')
  writeAscii(view, 12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  writeAscii(view, 36, 'data')
  view.setUint32(40, samples.length * 2, true)

  let offset = 44
  for (let index = 0; index < samples.length; index += 1) {
    const sample = Math.max(-1, Math.min(1, samples[index]))
    view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true)
    offset += 2
  }
  return new Blob([buffer], { type: 'audio/wav' })
}

function writeAscii(view: DataView, offset: number, text: string) {
  for (let index = 0; index < text.length; index += 1) {
    view.setUint8(offset + index, text.charCodeAt(index))
  }
}

function resampleTo16k(input: Float32Array, sourceRate: number) {
  const targetRate = 16000
  if (sourceRate === targetRate) return input
  const ratio = sourceRate / targetRate
  const length = Math.max(1, Math.round(input.length / ratio))
  const output = new Float32Array(length)
  for (let index = 0; index < length; index += 1) {
    const sourceIndex = index * ratio
    const before = Math.floor(sourceIndex)
    const after = Math.min(before + 1, input.length - 1)
    const weight = sourceIndex - before
    output[index] = input[before] * (1 - weight) + input[after] * weight
  }
  return output
}

function mergeVoiceChunks(chunks: Float32Array[], length: number) {
  const merged = new Float32Array(length)
  let offset = 0
  for (const chunk of chunks) {
    merged.set(chunk, offset)
    offset += chunk.length
  }
  return merged
}

function blobToDataUrl(blob: Blob) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(blob)
  })
}

async function transcribeVoiceChunk(samples: Float32Array, sourceRate: number) {
  if (voiceRequestInFlight || samples.length < sourceRate * 0.45) return
  voiceRequestInFlight = true
  try {
    const wav = encodeWav(resampleTo16k(samples, sourceRate), 16000)
    const data = await blobToDataUrl(wav)
    const response = await fetch(`${apiBase}/api/voice/transcribe`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ data, showEndConfirm: showEndConfirm.value }),
    })
    if (!response.ok) throw new Error(await response.text())
    const match = (await response.json()) as BackendVoiceMatch & { transcript?: string }
    lastVoiceError.value = ''
    if (match.transcript) {
      lastVoiceText.value = match.matched ? match.label ?? match.transcript : match.transcript
    } else {
      lastVoiceText.value = '正在聆听'
    }
    if (match.matched) runBackendVoiceAction(match)
  } catch (exc) {
    lastVoiceError.value = exc instanceof Error ? exc.message.slice(0, 60) : 'transcribe-failed'
    lastVoiceText.value = '本地语音识别失败'
  } finally {
    voiceRequestInFlight = false
  }
}

function flushVoiceChunk() {
  if (!voiceAudioContext || !voiceChunks.length) return
  const chunks = voiceChunks
  const length = voiceChunkSampleCount
  const sampleRate = voiceAudioContext.sampleRate
  voiceChunks = []
  voiceChunkSampleCount = 0
  void transcribeVoiceChunk(mergeVoiceChunks(chunks, length), sampleRate)
}

async function startVoice() {
  lastVoiceError.value = ''
  lastVoiceText.value = '正在聆听'
  try {
    voiceStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
      video: false,
    })
    voiceAudioContext = new AudioContext()
    voiceSource = voiceAudioContext.createMediaStreamSource(voiceStream)
    voiceProcessor = voiceAudioContext.createScriptProcessor(4096, 1, 1)
    voiceProcessor.onaudioprocess = (event) => {
      if (!voiceEnabled.value) return
      const input = event.inputBuffer.getChannelData(0)
      voiceChunks.push(new Float32Array(input))
      voiceChunkSampleCount += input.length
    }
    voiceSource.connect(voiceProcessor)
    voiceProcessor.connect(voiceAudioContext.destination)
    voiceFlushTimerId = window.setInterval(flushVoiceChunk, 1800)
    voiceEnabled.value = true
    voiceSupported.value = true
  } catch (exc) {
    voiceEnabled.value = false
    lastVoiceError.value = exc instanceof Error ? exc.name : 'start-failed'
    lastVoiceText.value = '麦克风启动失败'
  }
}

function stopVoice() {
  voiceEnabled.value = false
  if (voiceFlushTimerId !== undefined) {
    window.clearInterval(voiceFlushTimerId)
    voiceFlushTimerId = undefined
  }
  flushVoiceChunk()
  voiceProcessor?.disconnect()
  voiceSource?.disconnect()
  void voiceAudioContext?.close()
  voiceStream?.getTracks().forEach((track) => track.stop())
  voiceProcessor = null
  voiceSource = null
  voiceAudioContext = null
  voiceStream = null
  voiceChunks = []
  voiceChunkSampleCount = 0
  voiceRequestInFlight = false
  lastVoiceAction = ''
  lastVoiceActionAt = 0
  lastVoiceError.value = ''
  lastVoiceText.value = '等待语音'
}

function handleVoiceCommand(text: string) {
  void handleVoiceCandidates([{ text, isFinal: true, confidence: 1 }])
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
  if (fullscreenPresentationActive.value) {
    revealFullscreenChrome()
  }
  if (activeMode.value === 'zoom') {
    zoomPoint.value = stagePoint(event)
  }
}

function distanceBetween(left: Point, right: Point) {
  const dx = left.x - right.x
  const dy = left.y - right.y
  return Math.sqrt(dx * dx + dy * dy)
}

function simplifyAnnotationLine(points: Point[]) {
  if (points.length <= 1) return points
  const simplified: Point[] = [points[0]]
  for (let index = 1; index < points.length; index += 1) {
    const point = points[index]
    if (distanceBetween(point, simplified[simplified.length - 1]) >= 0.0035) {
      simplified.push(point)
    }
  }
  if (simplified[simplified.length - 1] !== points[points.length - 1]) {
    simplified.push(points[points.length - 1])
  }
  return simplified
}

function eraseAtPoint(point: Point) {
  const nextLines: AnnotationLine[] = []
  for (const line of annotations.value) {
    let currentSegment: Point[] = []
    const segments: Point[][] = []

    for (const linePoint of line.points) {
      if (distanceBetween(linePoint, point) <= eraserRadius) {
        if (currentSegment.length >= 2) segments.push(currentSegment)
        currentSegment = []
        continue
      }
      currentSegment.push(linePoint)
    }

    if (currentSegment.length >= 2) segments.push(currentSegment)

    if (!segments.length && line.points.every((linePoint) => distanceBetween(linePoint, point) > eraserRadius)) {
      nextLines.push(line)
      continue
    }

    for (const segment of segments) {
      const simplified = simplifyAnnotationLine(segment)
      if (simplified.length >= 2) {
        nextLines.push({ id: annotationId++, points: simplified })
      }
    }
  }
  annotations.value = nextLines
}

function startAnnotation(event: PointerEvent) {
  if (activeMode.value !== 'pen' && activeMode.value !== 'eraser') return
  const target = event.currentTarget as HTMLElement
  target.setPointerCapture?.(event.pointerId)
  if (activeMode.value === 'eraser') {
    eraseAtPoint(stagePoint(event))
    return
  }
  const line = { id: annotationId++, points: [stagePoint(event)] }
  drawingLine.value = line
  annotations.value.push(line)
}

function moveAnnotation(event: PointerEvent) {
  if (activeMode.value === 'eraser') {
    eraseAtPoint(stagePoint(event))
    return
  }
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
  showAnnotationActions.value = false
  revealFullscreenChrome()
}

function requestEndPresentation() {
  showEndConfirm.value = true
  showAnnotationActions.value = false
  fullscreenChromeVisible.value = true
  clearFullscreenChromeTimer()
}

function confirmEndPresentation() {
  deck.value = null
  currentIndex.value = 0
  activeMode.value = 'pointer'
  recognitionPaused.value = false
  annotations.value = []
  showAnnotationActions.value = false
  showEndConfirm.value = false
  pendingEndByVoice.value = false
  revealFullscreenChrome()
}

function cancelEndPresentation() {
  showEndConfirm.value = false
  pendingEndByVoice.value = false
  revealFullscreenChrome()
}


function handleKeydown(event: KeyboardEvent) {
  const target = event.target as HTMLElement | null
  if (target?.tagName === 'INPUT' || target?.tagName === 'TEXTAREA') return

  if (event.key === 'ArrowRight' || event.key === 'PageDown' || event.key === ' ') {
    event.preventDefault()
    executeCommand('next', 'button')
  }
  if (event.key === 'ArrowLeft' || event.key === 'PageUp') {
    event.preventDefault()
    executeCommand('previous', 'button')
  }
  if (event.key === 'Home') {
    event.preventDefault()
    executeCommand('first', 'button')
  }
  if (event.key === 'End') {
    event.preventDefault()
    executeCommand('last', 'button')
  }
  if (event.key.toLowerCase() === 'f') {
    event.preventDefault()
    executeCommand('fullscreen', 'button')
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
  document.addEventListener('fullscreenchange', handleFullscreenChange)
  void loadVisionSettings()
  void loadExternalControlStatus()
  timerId = window.setInterval(() => {
    if (!recognitionPaused.value) elapsedSeconds.value += 1
  }, 1000)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKeydown)
  document.removeEventListener('fullscreenchange', handleFullscreenChange)
  if (timerId) window.clearInterval(timerId)
  clearFullscreenChromeTimer()
  stopPreviewLoop()
  stopVoice()
  stopCamera()
})
</script>

<template>
  <main
    ref="shellRef"
    class="prototype-shell"
    :class="{ 'presentation-mode': fullscreenPresentationActive, 'chrome-hidden': fullscreenPresentationActive && !fullscreenChromeVisible, 'guide-mode': showImportGuide }"
  >
    <input
      ref="fileInput"
      class="sr-only"
      type="file"
      accept=".ppt,.pptx,application/vnd.ms-powerpoint,application/vnd.openxmlformats-officedocument.presentationml.presentation"
      @change="onFileChange"
    />
    <canvas ref="frameCanvasRef" class="sr-only" aria-hidden="true"></canvas>

    <header v-if="hasDeck" class="top-bar" :class="{ hidden: fullscreenPresentationActive && !fullscreenChromeVisible }" @pointermove="revealFullscreenChrome">
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
        <section v-if="showImportGuide" class="import-guide-overlay">
          <div class="import-guide-backdrop" @click="resetImportGuideFlow"></div>
          <article class="import-guide-card">
            <header class="import-guide-topbar">
              <button class="import-guide-back" type="button" @click="resetImportGuideFlow">
                <ArrowLeft :size="20" />
                <span>返回首页</span>
              </button>
              <span class="import-guide-status" :class="{ ready: importGuideDeckReady, busy: isUploading }">
                <Loader2 v-if="isUploading" :size="20" class="spin" />
                <CheckCircle2 v-else-if="importGuideDeckReady" :size="20" />
                <span>{{ importGuideStatusText }}</span>
              </span>
            </header>

            <div class="import-guide-hero">
              <p>放映前准备</p>
              <h2>{{ activeImportGuideSlide.title }}</h2>
            </div>

            <div class="import-guide-body">
              <nav class="import-guide-tabs" aria-label="放映前准备步骤">
                <template v-for="(guideStep, index) in importGuideSlides" :key="guideStep.step">
                  <button
                    type="button"
                    class="import-guide-tab"
                    :class="{ active: index === importGuideIndex, done: index < importGuideIndex }"
                    @click="importGuideIndex = index"
                  >
                    <component
                      :is="guideStep.icon === 'upload' ? FileText : guideStep.icon === 'camera' ? UserRound : guideStep.icon === 'gesture' ? SlidersHorizontal : Wrench"
                      :size="24"
                    />
                    <span>{{ String(index + 1).padStart(2, '0') }}</span>
                    <strong>{{ guideStep.navLabel }}</strong>
                  </button>
                  <div v-if="index < importGuideSlides.length - 1" class="import-guide-connector" aria-hidden="true">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                </template>
              </nav>

              <section class="import-guide-panel">
                <div class="import-guide-intro">
                  <div class="import-guide-intro-icon">
                    <Sparkles :size="26" />
                  </div>
                  <p class="import-guide-summary">{{ activeImportGuideSlide.summary }}</p>
                </div>
                <div class="import-guide-divider"></div>
                <div class="import-guide-facts">
                  <article v-for="(fact, factIndex) in activeImportGuideSlide.facts" :key="fact.label" class="import-guide-fact">
                    <FileText v-if="factIndex === 0" :size="28" />
                    <CheckCircle2 v-else-if="factIndex === 1" :size="28" />
                    <Clock v-else :size="28" />
                    <span>{{ fact.label }}</span>
                    <strong>{{ fact.value }}</strong>
                    <p>{{ fact.detail }}</p>
                  </article>
                </div>
                <div class="import-guide-note">
                  <div class="import-guide-note-icon">
                    <Lightbulb :size="20" />
                  </div>
                  <div>
                    <span>提示</span>
                    <p>{{ activeImportGuideSlide.tip }}</p>
                  </div>
                </div>
              </section>
            </div>

            <footer class="import-guide-footer">
              <div class="import-guide-footer-copy">
                <strong>{{ importGuideProgressText }}</strong>
                <p>{{ importGuideFooterText }}</p>
              </div>
              <div class="import-guide-actions">
                <button type="button" :disabled="importGuideIndex === 0" @click="previousImportGuideStep">上一步</button>
                <button class="primary" type="button" :disabled="isImportGuideLastStep && !canEnterImportedDeck" @click="nextImportGuideStep">
                  {{ importGuidePrimaryText }}
                </button>
              </div>
            </footer>
          </article>
        </section>

        <template v-else-if="currentSlide">
          <img class="real-slide" :src="slideUrl(currentSlide)" :alt="`PPT 第 ${currentSlide.index} 页`" />
        </template>

        <template v-else-if="hasDeck">
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

        <section v-if="!hasDeck" class="launchpad-overlay">
          <div class="launchpad-glow launchpad-glow-left"></div>
          <div class="launchpad-glow launchpad-glow-right"></div>

          <div class="launchpad-header">
            <div class="launchpad-badge">
              <Monitor :size="16" />
              <span>AirSlide 放映控制台</span>
            </div>
            <button class="launchpad-guide-link" type="button" @click="startWithGuide">
              查看上手教程
            </button>
          </div>

          <div class="launchpad-content">
            <section class="launchpad-copy">
              <h2>先导入 PPT，再进入放映控制</h2>
              <p>
                导入演示文稿后，系统会完成页面转换，并进入支持手势、语音与标注控制的放映界面。
              </p>
              <div class="launchpad-highlights">
                <span>支持 .ppt / .pptx</span>
                <span>适配投影放映场景</span>
                <span>导入后进入放映模式</span>
              </div>
            </section>

            <button class="launchpad-upload" type="button" :disabled="isUploading" @click="pickFile">
              <Loader2 v-if="isUploading" :size="22" class="spin" />
              <UploadCloud v-else :size="22" />
              <strong>{{ isUploading ? '正在转换 PPT' : '导入 PPT 开始放映' }}</strong>
              <span>{{ isUploading ? '请稍等，系统正在生成放映页' : '点击选择文件，或直接将文件拖入当前区域' }}</span>
            </button>
          </div>
        </section>

        <svg
          class="annotation-layer"
          :class="{ drawable: activeMode === 'pen' || activeMode === 'eraser', erasing: activeMode === 'eraser' }"
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

        <aside v-if="hasDeck" class="camera-preview">
          <span class="camera-dot"></span>
          <div v-if="cameraEnabled" class="camera-video-surface">
            <canvas ref="previewCanvasRef" class="camera-preview-canvas"></canvas>
            <video ref="videoRef" class="camera-source-video" muted playsinline></video>
          </div>
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
          <div class="face-frame" :class="{ active: Boolean(visionResult?.face), passive: !visionResult?.face }" :style="faceGuideStyle"></div>
          <div class="camera-copy">
            <strong>{{ faceStatusText }}</strong>
            <span>{{ distanceText }}</span>
          </div>
        </aside>

        <aside v-if="hasDeck && showHandDebugPanel" class="hand-debug-panel">
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

        <aside v-if="hasDeck" class="assist-card">
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

    <footer v-if="hasDeck" class="bottom-bar" :class="{ hidden: fullscreenPresentationActive && !fullscreenChromeVisible }" @pointermove="revealFullscreenChrome">
      <button class="collapse-button" type="button">
        <ChevronUp :size="30" />
      </button>

      <nav class="tool-strip">
        <button class="tool-button" type="button" :disabled="hasDeck ? currentIndex === 0 : demoIndex === 0" @click="executeCommand('previous')">
          <ArrowLeft :size="34" />
          <span>上一页</span>
        </button>
        <button
          class="tool-button"
          type="button"
          :disabled="hasDeck ? currentIndex >= (deck?.slideCount ?? 1) - 1 : demoIndex >= slideCount - 1"
          @click="executeCommand('next')"
        >
          <ArrowRight :size="34" />
          <span>下一页</span>
        </button>
        <button class="tool-button" :class="{ active: activeMode === 'pointer' }" type="button" @click="executeCommand('pointer')">
          <Hand :size="33" />
          <span>空气指针</span>
        </button>
        <button class="tool-button" :class="{ selected: activeMode === 'pen' }" type="button" @click="executeCommand('pen')" @dblclick="executeCommand('clear-annotations')">
          <PenLine :size="32" />
          <span>标注</span>
        </button>
        <div class="tool-button-group">
          <button
            class="tool-button compact"
            :class="{ selected: activeMode === 'eraser' || showAnnotationActions }"
            type="button"
            :disabled="annotations.length === 0"
            @click="showAnnotationActions = !showAnnotationActions"
          >
            <Eraser :size="28" />
            <span>修正</span>
          </button>
          <div v-if="showAnnotationActions && annotations.length > 0" class="annotation-actions-menu">
            <button type="button" :class="{ active: activeMode === 'eraser' }" @click="executeCommand('eraser')">
              <Eraser :size="16" />
              <span>橡皮擦</span>
            </button>
            <button type="button" @click="executeCommand('clear-annotations')">
              <RotateCcw :size="16" />
              <span>一键清除</span>
            </button>
          </div>
        </div>
        <button class="tool-button" :class="{ selected: activeMode === 'zoom' }" type="button" @click="executeCommand('zoom')">
          <Expand :size="32" />
          <span>区域放大</span>
        </button>
        <button class="tool-button" :class="{ active: fullscreenPresentationActive }" type="button" @click="executeCommand('fullscreen')">
          <Maximize2 :size="30" />
          <span>{{ fullscreenPresentationActive ? '退出全屏' : '全屏放映' }}</span>
        </button>
        <button class="tool-button" type="button" @click="executeCommand(recognitionPaused ? 'resume' : 'pause')">
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
        <button type="button" @click="executeCommand('fullscreen')">全屏</button>
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
          <input v-model.number="visionSettings.swipeThreshold" min="0.005" max="0.08" step="0.005" type="range" />
          <b>{{ visionSettings.swipeThreshold.toFixed(3) }}</b>
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
            显示手势调试面板
            <small>仅用于调试手部识别、手势姿态和翻页触发状态，正式演示建议关闭</small>
          </span>
          <input v-model="showHandDebugPanel" type="checkbox" />
        </label>

        <label class="toggle-row">
          <span>
            控制外部 PowerPoint
            <small>{{ externalControlStatus }}，开启后命令会同步发送给前台放映窗口</small>
          </span>
          <input v-model="externalControlEnabled" type="checkbox" />
        </label>

        <footer>
          <button type="button" @click="showSettings = false">取消</button>
          <button class="primary" type="button" @click="saveVisionSettings">保存设置</button>
        </footer>
      </article>
    </section>
    <section v-if="showOnboarding && !hasDeck" class="confirm-layer onboarding-layer">
      <article class="onboarding-dialog">
        <header>
          <div>
            <p>三步上手</p>
            <h2>AirSlide 使用教程</h2>
          </div>
          <button type="button" @click="dismissOnboarding" aria-label="跳过教程">
            <X :size="20" />
          </button>
        </header>

        <div class="onboarding-steps">
          <article v-for="(step, index) in onboardingSteps" :key="step.title" class="onboarding-step">
            <div class="onboarding-step-index">
              {{ String(index + 1).padStart(2, '0') }}
            </div>
            <div class="onboarding-step-copy">
              <h3>{{ step.title }}</h3>
              <p>{{ step.summary }}</p>
              <small class="onboarding-step-cue">{{ step.cue }}</small>
              <button
                class="onboarding-detail-toggle"
                type="button"
                @click="expandedOnboardingStep = expandedOnboardingStep === index ? null : index"
              >
                {{ expandedOnboardingStep === index ? '收起详细说明' : '查看详细说明' }}
              </button>
              <div v-if="expandedOnboardingStep === index" class="onboarding-detail-panel">
                <section class="onboarding-detail-group">
                  <h4>使用步骤</h4>
                  <ol class="onboarding-step-list">
                    <li v-for="entry in step.steps" :key="entry">{{ entry }}</li>
                  </ol>
                </section>
                <section class="onboarding-detail-group">
                  <h4>注意事项</h4>
                  <ul class="onboarding-rule-list">
                    <li v-for="note in step.notes" :key="note">{{ note }}</li>
                  </ul>
                </section>
              </div>
            </div>
          </article>
        </div>

        <footer>
          <button class="primary" type="button" @click="dismissOnboarding">我知道了</button>
        </footer>
      </article>
    </section>
  </main>
</template>

<style scoped>
.prototype-shell {
  --space-2xs: clamp(3px, min(0.28vw, 0.5vh), 6px);
  --space-xs: clamp(5px, min(0.45vw, 0.75vh), 9px);
  --space-sm: clamp(8px, min(0.65vw, 1vh), 13px);
  --space-md: clamp(10px, min(0.95vw, 1.35vh), 18px);
  --space-lg: clamp(14px, min(1.35vw, 1.8vh), 26px);
  --font-xs: clamp(10px, min(0.66vw, 1.12vh), 13px);
  --font-sm: clamp(12px, min(0.78vw, 1.28vh), 15px);
  --font-md: clamp(13px, min(0.95vw, 1.5vh), 18px);
  --font-lg: clamp(15px, min(1.12vw, 1.75vh), 22px);
  --font-xl: clamp(20px, min(2.1vw, 3.2vh), 40px);
  --chrome-top: clamp(48px, min(3.5vw, 7.2vh), 64px);
  --chrome-bottom: clamp(64px, min(5.2vw, 10.8vh), 96px);
  --stage-pad: clamp(8px, min(1vw, 1.8vh), 16px);
  --icon-sm: clamp(16px, min(1.25vw, 2.1vh), 22px);
  --icon-md: clamp(20px, min(1.8vw, 3vh), 34px);
  --panel-radius: clamp(6px, min(0.6vw, 1vh), 10px);
  display: grid;
  height: 100vh;
  height: 100dvh;
  min-height: 520px;
  grid-template-rows: minmax(var(--chrome-top), auto) minmax(0, 1fr) minmax(var(--chrome-bottom), auto);
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
  transition:
    opacity 180ms ease,
    transform 220ms ease,
    visibility 180ms ease;
}

.top-bar.hidden,
.bottom-bar.hidden {
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
}

.top-bar.hidden {
  transform: translateY(-14px);
}

.bottom-bar.hidden {
  transform: translateY(14px);
}

.top-bar {
  justify-content: space-between;
  gap: var(--space-md);
  border-bottom: 1px solid rgb(255 255 255 / 0.09);
  padding: 0 var(--space-lg);
  min-width: 0;
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

.top-bar svg,
.file-title svg,
.device-zone svg {
  width: var(--icon-sm);
  height: var(--icon-sm);
}

.tool-button svg,
.collapse-button svg {
  width: var(--icon-md);
  height: var(--icon-md);
}

.assist-card svg,
.quick-upload svg {
  width: var(--icon-sm);
  height: var(--icon-sm);
  flex: 0 0 auto;
}

.step-icon svg {
  width: clamp(38px, min(4.2vw, 7vh), 76px);
  height: clamp(38px, min(4.2vw, 7vh), 76px);
}

.brand-zone {
  flex: 1 1 260px;
  min-width: 0;
  gap: var(--space-md);
}

.app-logo {
  display: flex;
  width: clamp(30px, min(2.4vw, 4.6vh), 40px);
  height: clamp(30px, min(2.4vw, 4.6vh), 40px);
  align-items: center;
  justify-content: center;
  gap: 2px;
  border-radius: var(--panel-radius);
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
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--font-lg);
  font-weight: 700;
  letter-spacing: 0;
}

.divider {
  width: 1px;
  height: clamp(20px, min(1.8vw, 3.5vh), 28px);
  background: rgb(255 255 255 / 0.13);
}

.live-state {
  gap: var(--space-sm);
  white-space: nowrap;
  color: #d8e2f0;
  font-size: var(--font-md);
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
  flex: 1 1 280px;
  max-width: 580px;
  min-width: 0;
  justify-content: center;
  gap: var(--space-xs);
  border: 0;
  background: transparent;
  color: #e8eef8;
  font-size: var(--font-md);
  cursor: pointer;
}

.file-title span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-zone {
  flex: 1 1 330px;
  justify-content: flex-end;
  gap: var(--space-md);
  min-width: 0;
  color: #d4deec;
}

.icon-status,
.camera-toggle,
.settings-button,
.upload-button {
  gap: var(--space-xs);
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
  height: clamp(30px, min(2.2vw, 4.2vh), 38px);
  padding: 0 var(--space-sm);
  border: 1px solid rgb(255 255 255 / 0.14);
  border-radius: var(--panel-radius);
  background: rgb(255 255 255 / 0.06);
}

.window-actions {
  gap: var(--space-md);
  color: #cfd9e8;
}

.stage-area {
  --stage-max-height: calc(100dvh - var(--chrome-top) - var(--chrome-bottom) - var(--stage-pad) * 2);
  display: flex;
  min-height: 0;
  align-items: center;
  justify-content: center;
  padding: var(--stage-pad);
  background: linear-gradient(180deg, #07111f 0%, #0f1b2a 100%);
}

.prototype-shell.presentation-mode .stage-area {
  --stage-max-height: calc(100dvh - var(--stage-pad) * 2);
}

.prototype-shell.presentation-mode {
  grid-template-rows: minmax(0, 1fr);
}

.prototype-shell.guide-mode {
  grid-template-rows: minmax(0, 1fr);
}

.prototype-shell.presentation-mode .top-bar,
.prototype-shell.presentation-mode .bottom-bar {
  position: absolute;
  left: 0;
  right: 0;
}

.prototype-shell.guide-mode .top-bar,
.prototype-shell.guide-mode .bottom-bar {
  display: none;
}

.prototype-shell.guide-mode .stage-area {
  --stage-max-height: calc(100dvh - var(--chrome-top) - var(--chrome-bottom) - var(--stage-pad) * 2);
  padding: var(--stage-pad);
}

.prototype-shell.guide-mode .presentation-stage {
  width: min(100%, 1880px, calc(var(--stage-max-height) * 16 / 9));
  max-width: 1880px;
}

.prototype-shell.presentation-mode .top-bar {
  top: 0;
}

.prototype-shell.presentation-mode .bottom-bar {
  bottom: 0;
}

.presentation-stage {
  position: relative;
  width: min(100%, 1880px, calc(var(--stage-max-height) * 16 / 9));
  max-height: var(--stage-max-height);
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
  width: clamp(16px, min(1.5vw, 2.6vh), 26px);
  height: clamp(16px, min(1.5vw, 2.6vh), 26px);
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
  left: 72%;
  top: 72%;
  width: clamp(48px, min(5vw, 8vh), 92px);
  height: 3px;
  transform: rotate(28deg);
  transform-origin: left center;
  border-radius: 999px;
  background: linear-gradient(90deg, rgb(43 132 255 / 0.7), transparent);
}

.zoom-window {
  position: absolute;
  z-index: 6;
  width: clamp(150px, min(14vw, 24vh), 252px);
  height: clamp(94px, min(8.8vw, 15vh), 158px);
  overflow: hidden;
  border: 2px solid rgb(43 132 255 / 0.95);
  border-radius: var(--panel-radius);
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
  padding: var(--space-2xs) var(--space-xs);
  font-size: var(--font-xs);
}

.launchpad-overlay {
  position: absolute;
  inset: 0;
  z-index: 8;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: clamp(22px, min(2.4vw, 4.2vh), 38px);
  background:
    radial-gradient(circle at 18% 20%, rgb(68 132 255 / 0.2), transparent 24%),
    radial-gradient(circle at 82% 22%, rgb(19 213 157 / 0.14), transparent 20%),
    linear-gradient(180deg, rgb(7 17 31 / 1), rgb(11 22 39 / 1));
}

.launchpad-glow {
  position: absolute;
  width: clamp(160px, min(18vw, 28vh), 320px);
  height: clamp(160px, min(18vw, 28vh), 320px);
  border-radius: 999px;
  filter: blur(18px);
  opacity: 0.4;
  pointer-events: none;
}

.launchpad-glow-left {
  left: -60px;
  top: -50px;
  background: rgb(47 111 240 / 0.34);
}

.launchpad-glow-right {
  right: -70px;
  bottom: -70px;
  background: rgb(19 213 157 / 0.22);
}

.launchpad-header,
.launchpad-content {
  position: relative;
  z-index: 1;
}

.launchpad-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-md);
}

.launchpad-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid rgb(255 255 255 / 0.12);
  border-radius: 999px;
  background: rgb(255 255 255 / 0.06);
  color: #dce9fb;
  padding: 8px 12px;
  font-size: var(--font-sm);
  font-weight: 700;
}

.launchpad-guide-link {
  border: 0;
  background: transparent;
  color: #98bfff;
  padding: 6px 0;
  font-size: var(--font-sm);
  font-weight: 700;
  cursor: pointer;
}

.launchpad-guide-link:hover {
  color: #c5ddff;
}

.launchpad-content {
  display: grid;
  gap: clamp(20px, min(2vw, 3vh), 30px);
  width: min(100%, 920px);
  margin: auto;
  text-align: center;
}

.launchpad-copy h2 {
  margin: 0;
  color: white;
  font-size: clamp(30px, min(3.6vw, 6vh), 58px);
  font-weight: 800;
  line-height: 1.08;
}

.launchpad-copy p {
  margin: clamp(14px, min(1.3vw, 2.2vh), 22px) auto 0;
  max-width: 760px;
  color: #b6c6da;
  font-size: clamp(14px, min(1.1vw, 1.9vh), 20px);
  line-height: 1.8;
}

.launchpad-highlights {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
  margin-top: clamp(16px, min(1.5vw, 2.4vh), 24px);
}

.launchpad-highlights span {
  border: 1px solid rgb(255 255 255 / 0.1);
  border-radius: 999px;
  background: rgb(255 255 255 / 0.05);
  color: #dce8f7;
  padding: 8px 14px;
  font-size: var(--font-sm);
  font-weight: 600;
}

.launchpad-upload {
  display: grid;
  justify-items: center;
  gap: 8px;
  width: min(100%, 560px);
  margin: 0 auto;
  border: 1px solid rgb(88 142 234 / 0.44);
  border-radius: 14px;
  background: linear-gradient(180deg, rgb(28 72 141 / 0.35), rgb(16 38 66 / 0.78));
  color: white;
  padding: clamp(20px, min(2vw, 3vh), 28px);
  cursor: pointer;
  box-shadow: 0 20px 52px rgb(4 13 26 / 0.34);
}

.launchpad-upload:hover:not(:disabled) {
  border-color: rgb(127 173 255 / 0.7);
  transform: translateY(-1px);
}

.launchpad-upload strong {
  font-size: clamp(18px, min(1.5vw, 2.4vh), 26px);
  font-weight: 800;
}

.launchpad-upload span {
  color: #b7cae4;
  font-size: var(--font-sm);
}

.launchpad-upload:disabled {
  cursor: progress;
  opacity: 0.82;
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
  padding-top: clamp(34px, min(4.8vw, 8vh), 86px);
  text-align: center;
}

.slide-heading h2 {
  margin: 0;
  color: #102849;
  font-size: clamp(26px, min(4.1vw, 7.5vh), 72px);
  font-weight: 800;
  line-height: 1;
  letter-spacing: 0;
}

.slide-heading span {
  display: block;
  width: clamp(42px, min(4.2vw, 7vh), 76px);
  height: clamp(3px, min(0.3vw, 0.6vh), 5px);
  margin: clamp(12px, min(1.3vw, 2.4vh), 24px) auto clamp(14px, min(1.5vw, 2.8vh), 28px);
  border-radius: 999px;
  background: linear-gradient(90deg, #1f7fff, #6da4ff);
}

.slide-heading p {
  margin: 0 auto;
  max-width: 980px;
  color: #50627a;
  font-size: clamp(12px, min(1.08vw, 2vh), 21px);
  font-weight: 500;
}

.process-row {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: clamp(8px, min(1.9vw, 3.2vh), 34px);
  width: min(88%, 1640px);
  margin: clamp(28px, min(5.4vw, 8.8vh), 96px) auto 0;
}

.process-step {
  position: relative;
  text-align: center;
}

.step-icon {
  position: relative;
  display: grid;
  width: clamp(68px, min(9.6vw, 15.5vh), 192px);
  height: clamp(68px, min(9.6vw, 15.5vh), 192px);
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
  width: clamp(26px, min(2.5vw, 4.2vh), 44px);
  height: clamp(26px, min(2.5vw, 4.2vh), 44px);
  place-items: center;
  border-radius: 999px;
  background: linear-gradient(180deg, #1f84ff, #2867d9);
  color: white;
  font-size: clamp(12px, min(1.25vw, 2.2vh), 22px);
  line-height: 1;
  box-shadow: 0 8px 18px rgb(32 117 228 / 0.28);
}

.process-step h3 {
  margin: clamp(10px, min(1.45vw, 2.6vh), 26px) 0 0;
  color: #102849;
  font-size: clamp(12px, min(1.25vw, 2.25vh), 24px);
  font-weight: 800;
  line-height: 1.25;
}

.process-step p {
  margin: clamp(6px, min(0.8vw, 1.5vh), 15px) 0 0;
  color: #68758a;
  font-size: clamp(11px, min(1.05vw, 1.9vh), 21px);
  line-height: 1.7;
}

.process-step p span {
  display: block;
}

.step-arrow {
  position: absolute;
  left: calc(50% + clamp(40px, min(5vw, 8vh), 98px));
  top: clamp(34px, min(4.2vw, 7vh), 84px);
  display: flex;
  width: clamp(38px, min(6vw, 10vh), 122px);
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
  width: clamp(72px, min(9vw, 15vh), 168px);
  height: clamp(52px, min(6.2vw, 10.5vh), 118px);
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
  left: var(--space-lg);
  top: var(--space-lg);
  z-index: 6;
  width: clamp(148px, min(15.5vw, 26vh), 292px);
  height: clamp(76px, min(8.1vw, 13.6vh), 154px);
  overflow: hidden;
  border-radius: var(--panel-radius);
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

.camera-video-surface {
  position: absolute;
  inset: 0 auto 0 0;
  width: 58%;
  overflow: hidden;
}

.camera-preview-canvas {
  width: 100%;
  height: 100%;
  display: block;
}

.camera-source-video {
  position: absolute;
  inset: 0;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
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
  border: 2px solid rgb(255 255 255 / 0.78);
  border-radius: 14px;
  box-shadow:
    0 0 0 1px rgb(31 130 255 / 0.15),
    0 0 18px rgb(31 130 255 / 0.18);
  transition:
    width 180ms ease-out,
    height 180ms ease-out,
    border-color 180ms ease-out,
    box-shadow 180ms ease-out;
}

.face-frame.active {
  border-color: rgb(32 231 147 / 0.95);
  box-shadow:
    0 0 0 1px rgb(32 231 147 / 0.24),
    0 0 22px rgb(32 231 147 / 0.24);
}

.face-frame.passive {
  border-style: dashed;
  opacity: 0.72;
}

.camera-copy {
  position: absolute;
  left: 58%;
  top: 50%;
  display: grid;
  gap: var(--space-xs);
  transform: translateY(-50%);
  color: white;
  font-size: var(--font-sm);
  line-height: 1.25;
}

.camera-copy strong {
  font-weight: 800;
}

.hand-debug-panel {
  position: absolute;
  right: var(--space-lg);
  top: var(--space-lg);
  z-index: 7;
  width: clamp(190px, min(17vw, 28vh), 326px);
  overflow: hidden;
  border: 1px solid rgb(255 255 255 / 0.18);
  border-radius: var(--panel-radius);
  background: rgb(13 27 47 / 0.78);
  color: white;
  box-shadow: 0 18px 42px rgb(12 28 52 / 0.26);
  backdrop-filter: blur(14px);
}

.hand-debug-panel header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-sm);
  padding: var(--space-xs) var(--space-sm);
  border-bottom: 1px solid rgb(255 255 255 / 0.1);
  font-size: var(--font-sm);
  font-weight: 800;
}

.hand-debug-panel header b {
  border-radius: 999px;
  background: rgb(255 255 255 / 0.08);
  color: #b8c7dc;
  padding: var(--space-2xs) var(--space-xs);
  font-size: var(--font-xs);
  font-weight: 800;
}

.hand-debug-panel header b.ready {
  background: rgb(32 231 147 / 0.16);
  color: #76f2bd;
}

.debug-video-box {
  position: relative;
  height: clamp(86px, min(9.5vw, 15vh), 176px);
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
  font-size: var(--font-xs);
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
  gap: var(--space-2xs);
  padding: var(--space-xs) var(--space-sm) 0;
}

.finger-grid span {
  min-width: 0;
  border: 1px solid rgb(255 255 255 / 0.1);
  border-radius: 7px;
  background: rgb(255 255 255 / 0.06);
  color: #b6c3d6;
  padding: var(--space-2xs) 2px;
  text-align: center;
  font-size: var(--font-xs);
  font-weight: 800;
}

.finger-grid span.active {
  border-color: rgb(32 231 147 / 0.38);
  background: rgb(32 231 147 / 0.14);
  color: #78f2be;
}

.hand-debug-panel p {
  margin: 0;
  padding: var(--space-xs) var(--space-sm) var(--space-sm);
  color: #aebbd0;
  font-size: var(--font-xs);
  line-height: 1.45;
}

.assist-card {
  position: absolute;
  right: var(--space-lg);
  bottom: var(--space-lg);
  z-index: 5;
  width: clamp(180px, min(15.4vw, 26vh), 292px);
  padding: var(--space-md) var(--space-lg);
  border-radius: var(--panel-radius);
  background: rgb(82 94 112 / 0.7);
  color: white;
  font-size: var(--font-md);
  font-weight: 600;
  box-shadow: 0 22px 48px rgb(43 65 94 / 0.2);
  backdrop-filter: blur(14px);
}

.assist-card p {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin: 0;
}

.assist-card p + p {
  margin-top: var(--space-md);
}

.assist-card small {
  display: block;
  margin-top: var(--space-md);
  color: rgb(255 255 255 / 0.7);
  font-size: var(--font-xs);
  font-weight: 500;
}

.quick-upload {
  position: absolute;
  left: 50%;
  bottom: var(--space-lg);
  display: inline-flex;
  align-items: center;
  gap: var(--space-xs);
  transform: translateX(-50%);
  border: 0;
  border-radius: 8px;
  background: rgb(16 38 66 / 0.72);
  color: white;
  padding: var(--space-xs) var(--space-md);
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
  gap: var(--space-sm);
  background: rgb(8 19 34 / 0.76);
  color: white;
  font-size: var(--font-md);
  backdrop-filter: blur(8px);
}

.import-guide-overlay {
  position: absolute;
  inset: 0;
  z-index: 12;
  display: block;
  padding: 0;
  overflow: hidden;
}

.import-guide-backdrop {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 27% 27%, rgb(30 107 238 / 0.28), transparent 30%),
    radial-gradient(circle at 78% 34%, rgb(10 164 143 / 0.28), transparent 28%),
    linear-gradient(135deg, #071121 0%, #0b1830 48%, #071c24 100%);
  z-index: 0;
}

.import-guide-card {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: clamp(12px, 2vh, 24px);
  width: 100%;
  height: 100%;
  border: 0;
  border-radius: 0;
  background:
    radial-gradient(circle at 18% 24%, rgb(26 83 177 / 0.22), transparent 28%),
    radial-gradient(circle at 82% 35%, rgb(9 151 133 / 0.2), transparent 30%),
    linear-gradient(135deg, rgb(6 14 27 / 0.92), rgb(8 22 42 / 0.92) 48%, rgb(5 28 34 / 0.92));
  padding: clamp(18px, 2.65vh, 32px) clamp(34px, 3.8vw, 64px) clamp(18px, 2.75vh, 34px);
  box-shadow: inset 0 0 0 1px rgb(214 226 255 / 0.72);
}

.import-guide-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  margin: 0 auto;
}

.import-guide-back {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  border: 0;
  background: transparent;
  color: #d8e5f6;
  padding: 0;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transform: translateX(-18px);
}

.import-guide-back svg,
.import-guide-status svg {
  width: 18px;
  height: 18px;
}

.import-guide-hero {
  display: grid;
  gap: 7px;
  width: min(1180px, 100%);
  max-width: 470px;
  margin: 0 auto;
  margin-left: calc((100% - min(1180px, 100%)) / 2);
}

.import-guide-hero p {
  margin: 0;
  color: #8fb4ff;
  font-size: 13px;
  font-weight: 700;
}

.import-guide-hero h2 {
  margin: 0;
  color: white;
  white-space: pre-line;
  max-width: 12ch;
  font-size: clamp(28px, 3.55vh, 42px);
  line-height: 1.24;
  letter-spacing: 0;
  font-weight: 800;
}

.import-guide-status {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  min-height: 28px;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: #e8f1ff;
  padding: 0;
  font-size: 13px;
  font-weight: 700;
}

.import-guide-status.ready {
  color: #e8f1ff;
}

.import-guide-status.busy {
  color: #e8f1ff;
}

.import-guide-body {
  display: flex;
  flex-direction: column;
  gap: clamp(14px, 2.1vh, 26px);
  min-height: auto;
  width: min(1180px, 100%);
  margin: 0 auto;
  padding-top: 0;
}

.import-guide-tabs {
  display: grid;
  grid-template-columns: minmax(160px, 1fr) 24px minmax(160px, 1fr) 24px minmax(160px, 1fr) 24px minmax(160px, 1fr);
  gap: 10px;
  align-items: center;
}

.import-guide-tab {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  min-height: clamp(44px, 5.7vh, 56px);
  border: 1px solid rgb(120 155 205 / 0.28);
  border-radius: 20px;
  background: rgb(9 21 38 / 0.46);
  color: #c5d3e3;
  padding: 0 16px;
  text-align: left;
  cursor: pointer;
  transition:
    border-color 160ms ease,
    background 160ms ease,
    color 160ms ease;
}

.import-guide-tab:hover {
  border-color: rgb(73 138 255 / 0.52);
  background: rgb(22 49 89 / 0.52);
}

.import-guide-tab.active {
  border-color: rgb(70 139 255 / 0.84);
  background: linear-gradient(135deg, #1f5cc0, #3479e6);
  color: white;
  box-shadow:
    0 14px 26px rgb(20 86 202 / 0.28),
    inset 0 1px 0 rgb(255 255 255 / 0.12);
}

.import-guide-tab.done {
  border-color: rgb(120 155 205 / 0.28);
}

.import-guide-tab span {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 24px;
  background: transparent;
  color: currentColor;
  font-size: 12px;
  font-weight: 800;
}

.import-guide-tab strong {
  font-size: 14px;
  font-weight: 700;
}

.import-guide-tab svg {
  flex: 0 0 auto;
  width: 20px;
  height: 20px;
}

.import-guide-connector {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 3px;
  opacity: 0.8;
}

.import-guide-connector span {
  width: 4px;
  height: 4px;
  border-radius: 999px;
  background: #357cff;
}

.import-guide-panel {
  display: flex;
  flex-direction: column;
  gap: clamp(11px, 1.65vh, 18px);
  border: 0;
  background: transparent;
  padding: 0;
}

.import-guide-intro {
  display: grid;
  grid-template-columns: clamp(40px, 5.4vh, 52px) minmax(0, 1fr);
  align-items: center;
  gap: 16px;
}

.import-guide-intro-icon {
  display: grid;
  width: clamp(40px, 5.4vh, 52px);
  height: clamp(40px, 5.4vh, 52px);
  place-items: center;
  border: 1px solid rgb(69 129 236 / 0.42);
  border-radius: 999px;
  background: linear-gradient(180deg, rgb(20 48 91 / 0.75), rgb(14 31 58 / 0.7));
  color: #eef5ff;
  box-shadow: inset 0 1px 0 rgb(255 255 255 / 0.05);
}

.import-guide-intro-icon svg {
  width: 22px;
  height: 22px;
}

.import-guide-summary {
  margin: 0;
  color: #cfe3ff;
  max-width: 64ch;
  font-size: clamp(13px, 1.45vh, 15px);
  font-weight: 600;
  line-height: 1.6;
}

.import-guide-divider {
  height: 1px;
  background: linear-gradient(90deg, rgb(76 118 178 / 0.58), rgb(78 128 194 / 0.22));
}

.import-guide-facts {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.import-guide-fact {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 6px 12px;
  min-height: clamp(88px, 11.8vh, 114px);
  align-content: start;
  border: 1px solid rgb(62 117 194 / 0.34);
  border-radius: 10px;
  background: linear-gradient(160deg, rgb(12 35 72 / 0.58), rgb(13 26 48 / 0.66));
  padding: clamp(12px, 1.8vh, 16px) clamp(14px, 1.9vw, 20px);
  box-shadow:
    inset 0 1px 0 rgb(255 255 255 / 0.04),
    0 14px 28px rgb(0 0 0 / 0.14);
}

.import-guide-fact svg {
  grid-row: 1 / span 2;
  color: #8db9ff;
  width: 23px;
  height: 23px;
}

.import-guide-fact span {
  color: #a7c3ff;
  font-size: 13px;
  font-weight: 700;
}

.import-guide-fact strong {
  color: white;
  font-size: clamp(17px, 2vh, 19px);
  font-weight: 800;
  line-height: 1.25;
}

.import-guide-fact p {
  grid-column: 2;
  margin: 0;
  color: #b8c8dc;
  line-height: 1.56;
  font-size: 13px;
}

.import-guide-note {
  display: flex;
  align-items: center;
  gap: 12px;
  border: 1px solid rgb(60 123 212 / 0.36);
  border-radius: 10px;
  background: linear-gradient(160deg, rgb(20 57 111 / 0.6), rgb(12 35 72 / 0.5));
  padding: clamp(12px, 1.75vh, 16px) clamp(15px, 2vw, 20px);
}

.import-guide-note-icon {
  display: grid;
  width: 36px;
  height: 36px;
  place-items: center;
  flex: 0 0 auto;
  border-radius: 999px;
  background: rgb(60 126 236 / 0.18);
  color: #9ec7ff;
}

.import-guide-note span {
  color: #a7c3ff;
  font-size: 14px;
  font-weight: 700;
}

.import-guide-note p {
  margin: 0;
  color: #d7e4f5;
  line-height: 1.55;
  font-size: 13px;
  font-weight: 500;
}

.import-guide-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 0;
  width: min(1180px, 100%);
  margin-left: auto;
  margin-right: auto;
  padding-top: clamp(10px, 1.55vh, 18px);
  border-top: 1px solid rgb(65 101 151 / 0.28);
}

.import-guide-footer-copy {
  display: grid;
  gap: 6px;
}

.import-guide-footer-copy strong {
  color: white;
  font-size: 14px;
  font-weight: 800;
}

.import-guide-footer-copy p {
  margin: 0;
  color: #9bacbf;
  line-height: 1.5;
  font-size: 13px;
}

.import-guide-actions {
  display: inline-flex;
  gap: 12px;
  flex: 0 0 auto;
}

.import-guide-actions button {
  height: 44px;
  min-width: 108px;
  border: 1px solid rgb(79 113 160 / 0.22);
  border-radius: 11px;
  background: rgb(12 26 45 / 0.58);
  color: #f2f6fb;
  padding: 0 20px;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
}

.import-guide-actions button.primary {
  border-color: rgb(66 139 255 / 0.8);
  background: linear-gradient(135deg, #2467d2, #3c83f0);
  color: white;
  box-shadow: 0 12px 24px rgb(38 110 226 / 0.22);
}

.import-guide-actions button:disabled {
  cursor: not-allowed;
  opacity: 0.52;
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
  padding: var(--space-sm) var(--space-md);
  font-size: var(--font-sm);
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
  gap: var(--space-md);
  border-top: 1px solid rgb(255 255 255 / 0.08);
  padding: var(--space-xs) var(--space-lg);
  min-width: 0;
}

.collapse-button {
  display: grid;
  flex: 0 0 auto;
  width: clamp(42px, min(3.4vw, 6vh), 64px);
  height: clamp(42px, min(3.1vw, 5.4vh), 58px);
  place-items: center;
  border: 0;
  border-radius: clamp(10px, min(1vw, 1.8vh), 18px);
  background: rgb(255 255 255 / 0.07);
  color: #dbe5f4;
  cursor: pointer;
}

.tool-strip {
  display: flex;
  flex: 1;
  min-width: 0;
  justify-content: center;
  gap: clamp(6px, min(1.5vw, 2.6vh), 38px);
}

.tool-button-group {
  position: relative;
  display: flex;
  flex: 1 1 clamp(86px, min(7.4vw, 13vh), 126px);
  min-width: 0;
  max-width: clamp(112px, min(9.4vw, 16vh), 176px);
}

.tool-button {
  display: inline-flex;
  flex: 1 1 clamp(86px, min(7.4vw, 13vh), 126px);
  min-width: 0;
  max-width: clamp(112px, min(9.4vw, 16vh), 176px);
  height: clamp(42px, min(3.4vw, 6vh), 64px);
  align-items: center;
  justify-content: center;
  gap: var(--space-xs);
  border: 1px solid rgb(255 255 255 / 0.11);
  border-radius: var(--panel-radius);
  background: linear-gradient(180deg, rgb(255 255 255 / 0.1), rgb(255 255 255 / 0.045));
  color: #f3f7ff;
  font-size: var(--font-md);
  font-weight: 600;
  cursor: pointer;
  box-shadow: inset 0 1px 0 rgb(255 255 255 / 0.05);
  transition:
    border-color 160ms ease,
    background-color 160ms ease,
    color 160ms ease,
    transform 160ms ease;
}

.tool-button.compact {
  max-width: none;
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

.annotation-actions-menu {
  position: absolute;
  left: 50%;
  bottom: calc(100% + 10px);
  z-index: 20;
  display: grid;
  gap: 8px;
  width: clamp(124px, min(10vw, 16vh), 168px);
  padding: 8px;
  transform: translateX(-50%);
  border: 1px solid rgb(255 255 255 / 0.12);
  border-radius: 12px;
  background: linear-gradient(180deg, rgb(18 32 52 / 0.98), rgb(12 21 36 / 0.98));
  box-shadow: 0 16px 34px rgb(0 0 0 / 0.34);
}

.annotation-actions-menu button {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  height: 38px;
  border: 1px solid rgb(255 255 255 / 0.08);
  border-radius: 10px;
  background: rgb(255 255 255 / 0.06);
  color: #eff5ff;
  padding: 0 10px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.annotation-actions-menu button:hover {
  border-color: rgb(122 169 255 / 0.58);
  background: rgb(53 97 164 / 0.32);
}

.annotation-actions-menu button.active {
  border-color: rgb(71 132 242 / 0.72);
  background: rgb(37 93 167 / 0.34);
  color: #8ebcff;
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
  border-radius: clamp(8px, min(0.8vw, 1.4vh), 14px);
  background: linear-gradient(180deg, rgb(18 32 52 / 0.98), rgb(12 21 36 / 0.98));
  box-shadow: 0 28px 80px rgb(0 0 0 / 0.42);
  padding: var(--space-lg);
}

.settings-dialog {
  width: min(620px, calc(100vw - 32px));
  border: 1px solid rgb(255 255 255 / 0.14);
  border-radius: clamp(8px, min(0.8vw, 1.4vh), 14px);
  background: linear-gradient(180deg, rgb(18 32 52 / 0.98), rgb(12 21 36 / 0.98));
  box-shadow: 0 28px 80px rgb(0 0 0 / 0.42);
  padding: var(--space-lg);
}

.onboarding-layer {
  z-index: 60;
}

.onboarding-dialog {
  width: min(640px, calc(100vw - 32px));
  border: 1px solid rgb(255 255 255 / 0.14);
  border-radius: clamp(10px, min(1vw, 1.6vh), 16px);
  background: linear-gradient(180deg, rgb(18 32 52 / 0.98), rgb(12 21 36 / 0.98));
  box-shadow: 0 28px 80px rgb(0 0 0 / 0.42);
  padding: clamp(18px, min(1.6vw, 2.6vh), 28px);
}

.onboarding-dialog header,
.settings-dialog header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-md);
}

.onboarding-dialog header p {
  margin: 0 0 6px;
  color: #88b5ff;
  font-size: var(--font-sm);
  font-weight: 700;
}

.onboarding-dialog header h2 {
  margin: 0;
  color: white;
  font-size: clamp(22px, min(1.8vw, 3vh), 32px);
}

.onboarding-dialog header button,
.settings-dialog header button {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border: 1px solid rgb(255 255 255 / 0.12);
  border-radius: 10px;
  background: rgb(255 255 255 / 0.06);
  color: #dbe7f9;
  cursor: pointer;
}

.onboarding-steps {
  display: grid;
  gap: 12px;
  margin: 22px 0;
}

.onboarding-step {
  display: grid;
  grid-template-columns: 52px minmax(0, 1fr);
  gap: 14px;
  align-items: start;
  border: 1px solid rgb(255 255 255 / 0.08);
  border-radius: 14px;
  background: rgb(255 255 255 / 0.05);
  padding: 14px;
}

.onboarding-step-index {
  display: grid;
  width: 52px;
  height: 52px;
  place-items: center;
  border-radius: 14px;
  background: linear-gradient(180deg, rgb(42 105 213 / 0.7), rgb(22 64 130 / 0.95));
  color: white;
  font-size: 18px;
  font-weight: 800;
}

.onboarding-step-copy h3 {
  margin: 2px 0 6px;
  color: white;
  font-size: var(--font-lg);
}

.onboarding-step-copy p {
  margin: 0;
  color: #b8c7dc;
  line-height: 1.65;
}

.onboarding-step-cue {
  display: block;
  margin-top: 8px;
  color: #8ea3c0;
  font-size: var(--font-xs);
  line-height: 1.6;
}

.onboarding-rule-list {
  margin: 0;
  padding-left: 18px;
  color: #d9e5f4;
  line-height: 1.7;
}

.onboarding-step-list {
  margin: 0;
  padding-left: 18px;
  color: #e8eef8;
  line-height: 1.75;
}

.onboarding-step-list li + li,
.onboarding-rule-list li + li {
  margin-top: 6px;
}

.onboarding-detail-toggle {
  margin-top: 10px;
  border: 0;
  background: transparent;
  color: #8ebcff;
  padding: 0;
  font-size: var(--font-sm);
  font-weight: 700;
  cursor: pointer;
}

.onboarding-detail-panel {
  display: grid;
  gap: 14px;
  margin-top: 12px;
  border: 1px solid rgb(255 255 255 / 0.08);
  border-radius: 12px;
  background: rgb(255 255 255 / 0.04);
  padding: 12px 14px;
}

.onboarding-detail-group {
  display: grid;
  gap: 8px;
}

.onboarding-detail-group h4 {
  margin: 0;
  color: #dbe8f8;
  font-size: var(--font-sm);
  font-weight: 700;
}

.onboarding-detail-panel p {
  margin: 0;
  color: #aebdd3;
  line-height: 1.7;
}

.onboarding-dialog footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-sm);
}

.onboarding-dialog footer button {
  height: clamp(38px, min(2.8vw, 4.8vh), 44px);
  border: 1px solid rgb(255 255 255 / 0.14);
  border-radius: 12px;
  background: rgb(255 255 255 / 0.08);
  color: white;
  padding: 0 16px;
  font-weight: 700;
  cursor: pointer;
}

.onboarding-dialog footer button.primary {
  border-color: rgb(45 145 255 / 0.38);
  background: rgb(45 145 255 / 0.18);
  color: #b9d6ff;
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
  margin-bottom: var(--space-md);
}

.settings-dialog h2 {
  margin: 0;
  color: white;
  font-size: var(--font-lg);
}

.settings-dialog header button {
  display: grid;
  width: clamp(28px, min(2vw, 3.6vh), 34px);
  height: clamp(28px, min(2vw, 3.6vh), 34px);
  place-items: center;
  border: 0;
  border-radius: var(--panel-radius);
  background: rgb(255 255 255 / 0.07);
  color: white;
  cursor: pointer;
}

.setting-row,
.toggle-row {
  gap: var(--space-md);
  border-top: 1px solid rgb(255 255 255 / 0.08);
  padding: var(--space-md) 0;
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
  font-size: var(--font-xs);
  font-weight: 500;
}

.setting-row input[type='range'] {
  width: clamp(120px, 28vw, 190px);
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
  gap: var(--space-sm);
  border-top: 1px solid rgb(255 255 255 / 0.08);
  padding-top: var(--space-md);
}

.settings-dialog footer button {
  height: clamp(34px, min(2.4vw, 4.4vh), 40px);
  border: 1px solid rgb(255 255 255 / 0.14);
  border-radius: var(--panel-radius);
  background: rgb(255 255 255 / 0.08);
  color: white;
  padding: 0 var(--space-md);
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
  font-size: var(--font-lg);
}

.confirm-dialog p {
  margin: var(--space-sm) 0 0;
  color: #becbe0;
  line-height: 1.75;
}

.confirm-checks {
  display: grid;
  gap: var(--space-sm);
  margin: var(--space-lg) 0;
}

.confirm-checks span {
  border: 1px solid rgb(255 255 255 / 0.1);
  border-radius: var(--panel-radius);
  background: rgb(255 255 255 / 0.05);
  color: #c8d4e7;
  padding: var(--space-xs) var(--space-sm);
}

.confirm-checks span.ok {
  border-color: rgb(32 231 147 / 0.35);
  color: #8df1c8;
}

.confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-sm);
}

.confirm-actions button {
  height: clamp(34px, min(2.4vw, 4.4vh), 40px);
  border: 1px solid rgb(255 255 255 / 0.14);
  border-radius: var(--panel-radius);
  background: rgb(255 255 255 / 0.08);
  color: white;
  padding: 0 var(--space-md);
  cursor: pointer;
}

.confirm-actions button.danger {
  border-color: rgb(255 93 103 / 0.42);
  background: rgb(255 93 103 / 0.16);
  color: #ff8c92;
  font-weight: 800;
}

@media (max-width: 1400px) {
  .top-bar {
    gap: var(--space-sm);
  }

  .brand-zone {
    flex-basis: 220px;
  }

  .device-zone {
    flex-basis: 260px;
  }

  .camera-toggle span,
  .settings-button span,
  .upload-button span,
  .live-state,
  .window-actions {
    display: none;
  }

  .tool-button {
    font-size: var(--font-sm);
  }

  .process-row {
    gap: var(--space-md);
  }

  .step-arrow {
    left: calc(50% + clamp(34px, min(4.2vw, 7vh), 72px));
    width: clamp(34px, min(5vw, 8.4vh), 84px);
  }
}

@media (max-width: 980px) {
  .prototype-shell {
    height: auto;
    min-height: 100dvh;
    grid-template-rows: auto minmax(0, 1fr) auto;
    overflow: visible;
  }

  .brand-zone,
  .device-zone,
  .file-title {
    min-width: 0;
    width: 100%;
    justify-content: center;
  }

  .stage-area {
    --stage-max-height: none;
    padding: var(--space-sm);
  }

  .presentation-stage {
    width: 100%;
    max-height: none;
  }

  .camera-preview {
    width: clamp(150px, 27vw, 190px);
    height: clamp(76px, 14vw, 96px);
  }

  .hand-debug-panel {
    right: 10px;
    top: 116px;
    width: min(250px, calc(100vw - 20px));
  }

  .debug-video-box {
    height: clamp(84px, 18vw, 118px);
  }

  .assist-card {
    display: none;
  }

  .process-row {
    grid-template-columns: repeat(5, 1fr);
    width: 94%;
    gap: var(--space-xs);
  }

  .process-step h3 {
    font-size: var(--font-xs);
  }

  .process-step p,
  .step-arrow {
    display: none;
  }

  .bottom-bar {
    padding: var(--space-sm);
  }

  .collapse-button {
    display: none;
  }

  .tool-strip {
    flex-wrap: wrap;
  }

  .tool-button {
    flex-basis: calc(50% - 8px);
    max-width: none;
    height: clamp(40px, 8vw, 48px);
    font-size: var(--font-sm);
  }
}

@media (max-height: 760px) and (min-width: 981px) {
  .prototype-shell {
    --chrome-top: 54px;
    --chrome-bottom: 70px;
    grid-template-rows: var(--chrome-top) minmax(0, 1fr) var(--chrome-bottom);
  }

  .stage-area {
    --stage-max-height: calc(100dvh - var(--chrome-top) - var(--chrome-bottom) - var(--stage-pad) * 2);
    padding: var(--stage-pad);
  }

  .app-logo,
  .divider,
  .live-state,
  .window-actions,
  .camera-preview,
  .assist-card {
    display: none;
  }

  .top-bar {
    padding-block: 0;
  }

  .bottom-bar {
    padding-block: 6px;
  }

  .hand-debug-panel {
    top: 12px;
    right: 12px;
    width: min(240px, 18vw);
  }

  .debug-video-box,
  .finger-grid {
    display: none;
  }

  .hand-debug-panel p {
    padding-top: 8px;
  }

  .tool-button {
    height: clamp(40px, 6.6vh, 50px);
  }
}

@media (max-width: 720px) {
  .prototype-shell {
    min-height: 100dvh;
  }

  .launchpad-overlay {
    padding: 18px;
  }

  .launchpad-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .launchpad-copy h2 {
    font-size: clamp(26px, 9vw, 36px);
  }

  .launchpad-highlights {
    justify-content: flex-start;
  }

  .launchpad-upload {
    width: 100%;
    padding: 18px 16px;
  }

  .import-guide-card {
    padding: 18px;
    gap: 14px;
  }

  .import-guide-hero h2 {
    max-width: 12ch;
    font-size: clamp(28px, 8vw, 36px);
  }

  .import-guide-topbar {
    align-items: flex-start;
    flex-direction: column;
    gap: 12px;
  }

  .import-guide-tabs {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .import-guide-connector {
    display: none;
  }

  .import-guide-tab {
    min-height: 48px;
    padding: 0 12px;
  }

  .import-guide-facts {
    grid-template-columns: 1fr;
  }

  .import-guide-intro {
    grid-template-columns: 44px minmax(0, 1fr);
    gap: 12px;
  }

  .import-guide-intro-icon {
    width: 44px;
    height: 44px;
  }

  .import-guide-actions {
    width: 100%;
  }

  .import-guide-actions button {
    flex: 1 1 0;
    justify-content: center;
  }

  .import-guide-footer {
    flex-direction: column;
    align-items: stretch;
  }

  .onboarding-dialog {
    padding: 18px;
  }

  .onboarding-step {
    grid-template-columns: 44px minmax(0, 1fr);
    padding: 12px;
  }

  .onboarding-step-index {
    width: 44px;
    height: 44px;
    border-radius: 12px;
    font-size: 16px;
  }

  .top-bar {
    padding: var(--space-sm);
  }

  .brand-zone h1 {
    font-size: var(--font-md);
  }

  .file-title {
    order: 3;
  }

  .stage-area {
    align-items: start;
  }

  .camera-preview,
  .hand-debug-panel {
    display: none;
  }

  .slide-heading {
    padding-top: clamp(24px, 8vw, 40px);
  }

  .process-row {
    margin-top: clamp(18px, 7vw, 32px);
  }

  .step-icon {
    width: clamp(48px, 15vw, 86px);
    height: clamp(48px, 15vw, 86px);
  }

  .step-icon svg {
    width: clamp(24px, 8vw, 36px);
    height: clamp(24px, 8vw, 36px);
  }

  .tool-button {
    flex-basis: calc(50% - 6px);
    height: clamp(38px, 11vw, 44px);
    font-size: var(--font-sm);
  }

  .tool-button svg {
    width: clamp(18px, 5.6vw, 22px);
    height: clamp(18px, 5.6vw, 22px);
  }
}

@media (max-height: 920px) and (min-width: 961px) {
  .import-guide-card {
    gap: 14px;
    padding: 26px 52px 26px;
  }

  .import-guide-hero h2 {
    font-size: 38px;
  }

  .import-guide-tabs {
    gap: 10px;
    grid-template-columns: minmax(146px, 1fr) 22px minmax(146px, 1fr) 22px minmax(146px, 1fr) 22px minmax(146px, 1fr);
  }

  .import-guide-tab {
    min-height: 50px;
    border-radius: 19px;
    padding-inline: 14px;
  }

  .import-guide-panel {
    gap: 13px;
  }

  .import-guide-summary {
    font-size: 14px;
  }

  .import-guide-fact {
    min-height: 96px;
    padding: 13px 16px;
  }

  .import-guide-fact strong {
    font-size: 18px;
  }

  .import-guide-note p,
  .import-guide-footer-copy p {
    font-size: 13px;
  }

  .import-guide-actions button {
    height: 44px;
    min-width: 108px;
  }
}
</style>
