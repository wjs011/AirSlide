<script setup lang="ts">
import { ref } from 'vue'
import { Camera, Hand, Mic, Sparkles } from 'lucide-vue-next'

type Slide = {
  title: string
  subtitle: string
  points: string[]
}

const slides = ref<Slide[]>([
  {
    title: 'AirSlide Control Hub',
    subtitle: 'Gesture, voice, and gaze aligned for live presentations.',
    points: ['Low-latency input fusion', 'Precision slide timing', 'Presenter focus mode']
  },
  {
    title: 'Interaction Intelligence',
    subtitle: 'Understand intent, confirm actions, and keep the flow on stage.',
    points: ['Gesture confirmation loop', 'Voice intent parsing', 'Context-aware overlays']
  },
  {
    title: 'Audience-Ready Output',
    subtitle: 'Confident transitions and clean delivery in any room.',
    points: ['Cinematic transitions', 'Safe mode failover', 'Realtime status cues']
  }
])

const currentSlide = ref(0)
const feedbackMessage = ref('')
const feedbackVisible = ref(false)

const showFeedback = (message: string) => {
  feedbackMessage.value = message
  feedbackVisible.value = true

  window.setTimeout(() => {
    feedbackVisible.value = false
  }, 1200)
}

const handleGesture = (type: string) => {
  showFeedback(`Gesture: ${type}`)
}

const handleVoice = (cmd: string) => {
  showFeedback(`Voice: ${cmd}`)
}

const updateFaceTracking = (coords: { x: number; y: number }) => {
  const x = Math.round(coords.x)
  const y = Math.round(coords.y)
  showFeedback(`Tracking: ${x}, ${y}`)
}

const nextSlide = () => {
  currentSlide.value = (currentSlide.value + 1) % slides.value.length
  showFeedback('Slide advanced')
}

const prevSlide = () => {
  currentSlide.value =
    (currentSlide.value - 1 + slides.value.length) % slides.value.length
  showFeedback('Slide reversed')
}
</script>

<template>
  <main class="relative min-h-screen overflow-hidden bg-night-900">
    <div class="pointer-events-none absolute inset-0">
      <div class="absolute inset-0 bg-radial-glow"></div>
      <div class="absolute -top-32 left-1/2 h-64 w-[36rem] -translate-x-1/2 rounded-full bg-neon-purple/20 blur-[120px]"></div>
      <div class="absolute bottom-[-12rem] left-8 h-72 w-72 rounded-full bg-neon-cyan/20 blur-[140px]"></div>
      <div class="absolute inset-0 bg-[linear-gradient(90deg,rgba(255,255,255,0.04)_1px,transparent_1px),linear-gradient(0deg,rgba(255,255,255,0.04)_1px,transparent_1px)] bg-[size:36px_36px] opacity-35"></div>
    </div>

    <div class="relative mx-auto flex min-h-screen max-w-6xl flex-col px-4 py-6 sm:px-6 lg:px-8">
      <section class="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-white/10 bg-white/5 px-5 py-3 backdrop-blur">
        <div class="flex flex-wrap items-center gap-3 text-sm text-slate-200">
          <span class="flex items-center gap-2 rounded-full border border-neon-cyan/40 bg-neon-cyan/10 px-3 py-1">
            <Camera class="h-4 w-4 text-neon-cyan" />
            Camera Active
          </span>
          <span class="flex items-center gap-2 rounded-full border border-neon-purple/40 bg-neon-purple/10 px-3 py-1">
            <Mic class="h-4 w-4 text-neon-purple" />
            Voice Listening
          </span>
          <span class="flex items-center gap-2 rounded-full border border-neon-mint/40 bg-neon-mint/10 px-3 py-1">
            <Hand class="h-4 w-4 text-neon-mint" />
            Gesture Ready
          </span>
        </div>

        <div class="flex items-center gap-2 text-xs text-slate-300">
          <Sparkles class="h-4 w-4 text-neon-cyan" />
          Stage Sync: Stable
        </div>
      </section>

      <section class="mt-10 flex flex-1 items-center justify-center">
        <div class="relative w-full max-w-4xl">
          <div class="absolute -inset-6 rounded-[32px] bg-gradient-to-br from-neon-cyan/15 via-neon-purple/10 to-transparent opacity-70 blur-2xl"></div>
          <article class="relative rounded-[28px] border border-white/10 bg-white/5 p-10 shadow-glass backdrop-blur">
            <div class="flex items-center justify-between">
              <span class="text-xs uppercase tracking-[0.3em] text-neon-cyan">Main Stage</span>
              <span class="text-xs text-slate-400">Slide {{ currentSlide + 1 }} / {{ slides.length }}</span>
            </div>

            <div class="mt-8 space-y-5">
              <h1 class="text-4xl font-semibold text-white sm:text-5xl">
                {{ slides[currentSlide].title }}
              </h1>
              <p class="max-w-2xl text-lg text-slate-300">
                {{ slides[currentSlide].subtitle }}
              </p>
              <ul class="space-y-3 text-base text-slate-200">
                <li v-for="(point, index) in slides[currentSlide].points" :key="index" class="flex items-start gap-3">
                  <span class="mt-1 h-2.5 w-2.5 rounded-full bg-neon-cyan shadow-glow"></span>
                  <span>{{ point }}</span>
                </li>
              </ul>
            </div>

            <div class="mt-10 flex flex-wrap gap-3">
              <button type="button" class="rounded-full border border-white/10 bg-white/5 px-5 py-2 text-sm text-slate-200 transition hover:border-neon-cyan/60 hover:text-white" @click="prevSlide">
                Previous
              </button>
              <button type="button" class="rounded-full border border-neon-cyan/50 bg-neon-cyan/10 px-5 py-2 text-sm text-white transition hover:bg-neon-cyan/20" @click="nextSlide">
                Next Slide
              </button>
              <button type="button" class="rounded-full border border-neon-purple/40 bg-neon-purple/10 px-5 py-2 text-sm text-slate-200 transition hover:text-white" @click="handleVoice('start demo')">
                Voice Demo
              </button>
              <button type="button" class="rounded-full border border-neon-mint/40 bg-neon-mint/10 px-5 py-2 text-sm text-slate-200 transition hover:text-white" @click="handleGesture('swipe right')">
                Gesture Demo
              </button>
            </div>
          </article>
        </div>
      </section>
    </div>

    <section class="absolute bottom-6 right-6 w-60 overflow-hidden rounded-2xl border border-white/15 bg-white/10 shadow-glass backdrop-blur">
      <div class="flex items-center justify-between border-b border-white/10 px-4 py-2 text-xs uppercase tracking-[0.2em] text-slate-200">
        <span>Side Monitor</span>
        <span class="text-neon-cyan">Live</span>
      </div>
      <div class="aspect-video w-full bg-[linear-gradient(120deg,rgba(62,243,255,0.12),rgba(143,107,255,0.08))]">
        <div class="flex h-full flex-col items-center justify-center gap-2 text-xs text-slate-300">
          <div class="h-12 w-12 rounded-full border border-dashed border-white/40"></div>
          Camera Feed Placeholder
        </div>
      </div>
    </section>

    <transition name="feedback">
      <div v-if="feedbackVisible" class="pointer-events-none absolute inset-0 flex items-center justify-center">
        <div class="feedback-card rounded-full border border-neon-cyan/50 bg-night-700/70 px-6 py-3 text-sm font-medium text-white shadow-glow backdrop-blur">
          {{ feedbackMessage }}
        </div>
      </div>
    </transition>
  </main>
</template>

<style scoped>
.feedback-card {
  animation: feedback-pulse 1.2s ease both;
}

.feedback-enter-active,
.feedback-leave-active {
  transition: opacity 0.3s ease;
}

.feedback-enter-from,
.feedback-leave-to {
  opacity: 0;
}

@keyframes feedback-pulse {
  0% {
    transform: scale(0.9);
    opacity: 0.7;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
  100% {
    transform: scale(1.05);
    opacity: 0;
  }
}
</style>
