<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  ArrowLeft,
  ArrowRight,
  Camera,
  ChevronDown,
  ChevronUp,
  Expand,
  Hand,
  Mic,
  Monitor,
  Pause,
  PenLine,
  Settings,
  ShieldCheck,
  Square,
  Video,
  X,
  Minus,
  Maximize2,
  Circle
} from 'lucide-vue-next'

type ProcessStep = {
  index: string
  title: string
  lines: string[]
  icon: 'camera' | 'joints' | 'gesture' | 'shield' | 'monitor'
}

const processSteps: ProcessStep[] = [
  {
    index: '01',
    title: '摄像头采集手部图像',
    lines: ['实时采集演讲者手部', '视频流'],
    icon: 'camera'
  },
  {
    index: '02',
    title: '手部检测与关键点提取',
    lines: ['检测手部区域并提取', '21 个关键点坐标'],
    icon: 'joints'
  },
  {
    index: '03',
    title: '手势识别',
    lines: ['基于深度学习模型', '识别静态/动态手势'],
    icon: 'gesture'
  },
  {
    index: '04',
    title: '时序稳定与误判抑制',
    lines: ['结合时间窗口与滤波算法', '提升稳定性与鲁棒性'],
    icon: 'shield'
  },
  {
    index: '05',
    title: '交互映射',
    lines: ['将识别结果映射为', '演示控制指令'],
    icon: 'monitor'
  }
]

const activeTool = ref('空写指针')
const elapsed = ref('00:08:42')

const statusLabel = computed(() => `演示中 ${elapsed.value}`)
</script>

<template>
  <main class="relative h-screen min-h-[760px] overflow-hidden bg-[#07101d] text-slate-100">
    <header class="relative z-20 flex h-16 items-center justify-between border-b border-white/10 bg-[#091423]/95 px-6 shadow-[0_12px_40px_rgba(0,0,0,0.24)]">
      <section class="flex min-w-0 items-center gap-5">
        <div class="flex items-center gap-3">
          <div class="grid h-9 w-9 place-items-center rounded-lg bg-gradient-to-br from-[#2d8dff] to-[#285de8] shadow-[0_10px_24px_rgba(45,125,255,0.36)]">
            <div class="flex h-5 items-center gap-0.5">
              <span class="h-2.5 w-0.5 rounded-full bg-white/95"></span>
              <span class="h-4 w-0.5 rounded-full bg-white/95"></span>
              <span class="h-6 w-0.5 rounded-full bg-white/95"></span>
              <span class="h-4 w-0.5 rounded-full bg-white/95"></span>
              <span class="h-2.5 w-0.5 rounded-full bg-white/95"></span>
            </div>
          </div>
          <h1 class="whitespace-nowrap text-xl font-semibold tracking-wide text-white">智能演讲辅助系统</h1>
        </div>
        <div class="h-8 w-px bg-white/12"></div>
        <div class="flex items-center gap-2.5 whitespace-nowrap text-base text-slate-200">
          <span class="h-2.5 w-2.5 rounded-full bg-[#17e68d] shadow-[0_0_18px_rgba(23,230,141,0.8)]"></span>
          <span>{{ statusLabel }}</span>
        </div>
      </section>

      <section class="absolute left-1/2 flex -translate-x-1/2 items-center gap-2 text-base font-medium text-slate-100">
        <span>人工智能进展与未来趋势.pptx</span>
        <ChevronDown class="h-4 w-4 text-slate-400" />
      </section>

      <section class="flex items-center gap-5 text-slate-300">
        <div class="flex items-center gap-2">
          <Mic class="h-5 w-5" />
          <div class="flex items-end gap-1 text-[#18e193]">
            <span class="h-3 w-1 rounded-full bg-current"></span>
            <span class="h-4 w-1 rounded-full bg-current"></span>
            <span class="h-4 w-1 rounded-full bg-current"></span>
          </div>
        </div>
        <div class="h-7 w-px bg-white/10"></div>
        <div class="flex items-center gap-2 whitespace-nowrap">
          <Video class="h-5 w-5" />
          <span>摄像头已开启</span>
        </div>
        <div class="h-7 w-px bg-white/10"></div>
        <button class="flex items-center gap-2 whitespace-nowrap transition hover:text-white" type="button">
          <Settings class="h-5 w-5" />
          <span>设置</span>
        </button>
        <div class="h-7 w-px bg-white/10"></div>
        <div class="flex items-center gap-5">
          <Minus class="h-5 w-5" />
          <Maximize2 class="h-4 w-4" />
          <X class="h-5 w-5" />
        </div>
      </section>
    </header>

    <section class="relative h-[calc(100vh-146px)] min-h-[614px] overflow-hidden bg-[#091321] p-4">
      <article class="relative h-full overflow-hidden rounded-[3px] bg-[#f7fbff] text-[#102748] shadow-[0_18px_50px_rgba(0,0,0,0.32)]">
        <div class="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_48%_28%,rgba(255,255,255,0.9),rgba(238,246,255,0.96)_45%,rgba(226,239,255,0.92))]"></div>
        <div class="pointer-events-none absolute -bottom-36 -left-28 h-[430px] w-[820px] rounded-[50%] border-t border-white/70 bg-[radial-gradient(ellipse_at_center,rgba(185,213,248,0.22),transparent_68%)]"></div>
        <div class="pointer-events-none absolute -right-24 top-12 h-[620px] w-[620px] rounded-full border border-[#d8e7fa]/50 opacity-70"></div>
        <div class="pointer-events-none absolute bottom-[-220px] right-[-130px] h-[640px] w-[980px] rotate-[-9deg] rounded-[50%] border-t border-white/70 bg-[repeating-linear-gradient(168deg,rgba(116,158,220,0.09)_0,rgba(116,158,220,0.09)_1px,transparent_1px,transparent_7px)] opacity-75"></div>

        <aside class="absolute left-5 top-5 z-10 h-[134px] w-[256px] overflow-hidden rounded-lg bg-[#3d4856]/75 shadow-[0_18px_45px_rgba(23,46,79,0.18)] backdrop-blur">
          <div class="absolute left-3 top-3 z-20 h-4 w-4 rounded-full border border-white/80 bg-[#15b77b] shadow-[0_0_0_3px_rgba(21,183,123,0.22)]"></div>
          <div class="absolute inset-y-0 left-0 w-[152px] overflow-hidden bg-[linear-gradient(110deg,#384352,#1b2531)]">
            <div class="face-hair"></div>
            <div class="face"></div>
            <div class="ear left-ear"></div>
            <div class="ear right-ear"></div>
            <div class="glass left-glass"></div>
            <div class="glass right-glass"></div>
            <div class="glass-bridge"></div>
            <div class="eye left-eye"></div>
            <div class="eye right-eye"></div>
            <div class="nose"></div>
            <div class="mouth"></div>
            <div class="neck"></div>
            <div class="shirt"></div>
            <div class="scan-corner corner-lt"></div>
            <div class="scan-corner corner-rt"></div>
            <div class="scan-corner corner-lb"></div>
            <div class="scan-corner corner-rb"></div>
          </div>
          <div class="absolute left-[150px] top-[58px] space-y-2 text-sm font-semibold leading-none text-white">
            <p>人脸锁定 96%</p>
            <p>距离 2.8m</p>
          </div>
        </aside>

        <section class="relative z-10 mx-auto flex h-full max-w-[1480px] flex-col items-center px-16 pb-14 pt-16">
          <div class="text-center">
            <h2 class="text-[54px] font-bold leading-none tracking-[0.16em] text-[#0c2549]">手势识别模块</h2>
            <div class="mx-auto mt-5 h-1 w-[68px] rounded-full bg-gradient-to-r from-[#1f7fff] via-[#1f7fff] to-[#89b5ff]"></div>
            <p class="mt-7 text-[18px] font-medium tracking-wide text-[#56657a]">
              通过计算机视觉与深度学习技术，识别演讲者的手势并映射为演示控制指令，实现自然、无接触的交互体验。
            </p>
          </div>

          <div class="mt-20 grid w-full grid-cols-5 items-start gap-8">
            <template v-for="(step, stepIndex) in processSteps" :key="step.index">
              <article class="relative flex flex-col items-center text-center">
                <div v-if="stepIndex < processSteps.length - 1" class="absolute left-[calc(50%+105px)] top-[85px] hidden h-px w-[110px] border-t border-dashed border-[#78a8ff] xl:block">
                  <ArrowRight class="absolute -right-2 -top-[11px] h-6 w-6 fill-[#2e7af0] text-[#2e7af0]" />
                </div>
                <div class="relative grid h-[172px] w-[172px] place-items-center rounded-full border-2 border-[#7aa9ff] bg-[radial-gradient(circle,rgba(218,232,251,0.72)_0%,rgba(245,250,255,0.96)_62%,rgba(238,246,255,0.96)_100%)] shadow-[inset_0_0_38px_rgba(99,148,220,0.14)]">
                  <span class="absolute -left-2 -top-3 grid h-11 w-11 place-items-center rounded-full bg-gradient-to-b from-[#1f84ff] to-[#2867d9] text-xl font-bold text-white shadow-[0_8px_18px_rgba(32,117,228,0.28)]">{{ step.index }}</span>

                  <Camera v-if="step.icon === 'camera'" class="h-[72px] w-[72px] fill-[#3e7ed9]/80 text-[#316fd0]" stroke-width="1.7" />
                  <div v-else-if="step.icon === 'joints'" class="relative h-[92px] w-[92px]">
                    <div class="joint-line line-a"></div>
                    <div class="joint-line line-b"></div>
                    <div class="joint-line line-c"></div>
                    <div class="joint-line line-d"></div>
                    <div class="joint-line line-e"></div>
                    <span v-for="point in 11" :key="point" :class="`joint joint-${point}`"></span>
                  </div>
                  <Hand v-else-if="step.icon === 'gesture'" class="h-[78px] w-[78px] text-[#2f73d5]" stroke-width="2.3" />
                  <ShieldCheck v-else-if="step.icon === 'shield'" class="h-[82px] w-[82px] fill-[#3e7ed9]/70 text-[#2f73d5]" stroke-width="1.9" />
                  <Monitor v-else class="h-[82px] w-[82px] fill-[#3e7ed9]/60 text-[#2f73d5]" stroke-width="1.8" />
                </div>

                <h3 class="mt-6 text-[20px] font-bold tracking-wide text-[#102847]">{{ step.title }}</h3>
                <p class="mt-3 text-[17px] leading-[1.75] tracking-wide text-[#657184]">
                  <span v-for="line in step.lines" :key="line" class="block">{{ line }}</span>
                </p>
              </article>
            </template>
          </div>

          <div class="absolute bottom-[212px] right-[260px] h-[110px] w-[150px] border-l-[3px] border-t-[3px] border-[#5c99f4] opacity-80 connection-path">
            <span class="absolute -left-[14px] -top-[14px] h-6 w-6 rounded-full border-[4px] border-[#2c87ff] bg-white shadow-[0_9px_20px_rgba(42,126,232,0.45)]"></span>
          </div>

          <aside class="absolute bottom-6 right-6 z-20 w-[258px] rounded-lg bg-[#667487]/72 p-6 text-[17px] font-medium text-white shadow-[0_22px_48px_rgba(43,65,94,0.22)] backdrop-blur-md">
            <p class="flex items-center gap-3">
              <Hand class="h-6 w-6" />
              <span>右滑：下一页</span>
            </p>
            <p class="mt-5 flex items-center gap-3">
              <Mic class="h-6 w-6" />
              <span>语音：放大此区域</span>
            </p>
            <p class="mt-8 flex items-center gap-3">
              <span class="h-3 w-3 rounded-full bg-[#14e68e] shadow-[0_0_14px_rgba(20,230,142,0.8)]"></span>
              <span>延迟 38ms</span>
            </p>
          </aside>
        </section>
      </article>
    </section>

    <footer class="relative z-20 flex h-20 items-center gap-8 border-t border-white/8 bg-[#111d2c] px-7 shadow-[0_-16px_48px_rgba(0,0,0,0.26)]">
      <button class="grid h-11 w-14 place-items-center rounded-2xl bg-white/8 text-slate-300 shadow-inner shadow-white/5 transition hover:bg-white/12" type="button" aria-label="展开">
        <ChevronUp class="h-7 w-7" />
      </button>

      <nav class="flex flex-1 items-center justify-center gap-9">
        <button class="control-button" type="button">
          <ArrowLeft class="h-8 w-8" />
          <span>上一页</span>
        </button>
        <button class="control-button" type="button">
          <ArrowRight class="h-8 w-8" />
          <span>下一页</span>
        </button>
        <button class="control-button is-active relative" type="button" @click="activeTool = '空写指针'">
          <span class="absolute -top-1 left-1/2 h-2.5 w-2.5 -translate-x-1/2 rounded-full bg-[#287fff]"></span>
          <Hand class="h-8 w-8" />
          <span>{{ activeTool }}</span>
        </button>
        <button class="control-button" type="button" @click="activeTool = '标注'">
          <PenLine class="h-8 w-8" />
          <span>标注</span>
        </button>
        <button class="control-button" type="button">
          <Expand class="h-8 w-8" />
          <span>区域放大</span>
        </button>
        <button class="control-button" type="button">
          <Pause class="h-8 w-8 fill-white text-white" />
          <span>暂停识别</span>
        </button>
        <button class="control-button danger" type="button">
          <Square class="h-6 w-6 fill-[#ff686d] text-[#ff686d]" />
          <span>结束演示</span>
        </button>
      </nav>
    </footer>
  </main>
</template>

<style scoped>
.control-button {
  display: inline-flex;
  height: 62px;
  min-width: 160px;
  align-items: center;
  justify-content: center;
  gap: 14px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.11), rgba(255, 255, 255, 0.055));
  color: rgb(229 237 248);
  font-size: 20px;
  font-weight: 600;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08), 0 10px 26px rgba(0, 0, 0, 0.13);
  transition: border-color 160ms ease, background 160ms ease, color 160ms ease;
}

.control-button:hover {
  border-color: rgba(128, 172, 255, 0.55);
  color: white;
}

.control-button.is-active {
  border-color: rgba(69, 137, 255, 0.88);
  background: linear-gradient(180deg, rgba(42, 115, 226, 0.28), rgba(47, 102, 187, 0.18));
  color: #8fbdff;
}

.control-button.danger {
  border-color: rgba(255, 103, 111, 0.42);
  color: #ff7278;
}

.face-hair {
  position: absolute;
  left: 36px;
  top: 20px;
  width: 82px;
  height: 60px;
  border-radius: 48% 48% 42% 42%;
  background: #151820;
  box-shadow: -13px 7px 0 #11151d, 12px 4px 0 #11151d;
}

.face {
  position: absolute;
  left: 44px;
  top: 44px;
  width: 68px;
  height: 72px;
  border-radius: 42% 42% 46% 46%;
  background: linear-gradient(#e0c0aa, #c89579);
}

.ear {
  position: absolute;
  top: 70px;
  height: 18px;
  width: 11px;
  border-radius: 999px;
  background: #c99578;
}

.left-ear {
  left: 36px;
}

.right-ear {
  left: 109px;
}

.neck {
  position: absolute;
  left: 65px;
  top: 109px;
  height: 19px;
  width: 28px;
  background: #bd856c;
}

.shirt {
  position: absolute;
  left: 38px;
  top: 122px;
  height: 34px;
  width: 82px;
  border-radius: 40% 40% 0 0;
  background: #f3f5f8;
}

.glass {
  position: absolute;
  top: 67px;
  height: 21px;
  width: 26px;
  border: 2px solid #252a33;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.05);
}

.left-glass {
  left: 52px;
}

.right-glass {
  left: 80px;
}

.glass-bridge {
  position: absolute;
  left: 77px;
  top: 76px;
  height: 2px;
  width: 6px;
  background: #252a33;
}

.eye {
  position: absolute;
  top: 76px;
  height: 3px;
  width: 8px;
  border-radius: 999px;
  background: #1c2028;
}

.left-eye {
  left: 60px;
}

.right-eye {
  left: 89px;
}

.nose {
  position: absolute;
  left: 76px;
  top: 82px;
  height: 14px;
  width: 5px;
  border-radius: 999px;
  border-right: 2px solid rgba(92, 53, 42, 0.38);
}

.mouth {
  position: absolute;
  left: 68px;
  top: 100px;
  height: 2px;
  width: 22px;
  border-radius: 999px;
  background: rgba(86, 40, 40, 0.55);
}

.scan-corner {
  position: absolute;
  height: 19px;
  width: 19px;
  border-color: white;
  opacity: 0.95;
}

.corner-lt {
  left: 29px;
  top: 38px;
  border-left: 2px solid;
  border-top: 2px solid;
}

.corner-rt {
  left: 123px;
  top: 38px;
  border-right: 2px solid;
  border-top: 2px solid;
}

.corner-lb {
  left: 29px;
  top: 118px;
  border-left: 2px solid;
  border-bottom: 2px solid;
}

.corner-rb {
  left: 123px;
  top: 118px;
  border-right: 2px solid;
  border-bottom: 2px solid;
}

.joint {
  position: absolute;
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: #3875d3;
  box-shadow: 0 3px 9px rgba(56, 117, 211, 0.3);
}

.joint-line {
  position: absolute;
  left: 44px;
  top: 58px;
  height: 2px;
  width: 46px;
  transform-origin: left center;
  background: #78a8e8;
}

.line-a {
  transform: rotate(-100deg);
}

.line-b {
  transform: rotate(-74deg);
}

.line-c {
  transform: rotate(-48deg);
}

.line-d {
  transform: rotate(-18deg);
}

.line-e {
  transform: rotate(22deg);
}

.joint-1 {
  left: 19px;
  top: 54px;
}

.joint-2 {
  left: 33px;
  top: 71px;
}

.joint-3 {
  left: 44px;
  top: 58px;
}

.joint-4 {
  left: 39px;
  top: 25px;
}

.joint-5 {
  left: 55px;
  top: 18px;
}

.joint-6 {
  left: 65px;
  top: 52px;
}

.joint-7 {
  left: 78px;
  top: 30px;
}

.joint-8 {
  left: 52px;
  top: 43px;
}

.joint-9 {
  left: 23px;
  top: 38px;
}

.joint-10 {
  left: 70px;
  top: 70px;
}

.joint-11 {
  left: 58px;
  top: 77px;
}

.connection-path {
  border-radius: 0 42px 0 0;
  transform: rotate(16deg);
}

@media (max-width: 1360px) {
  .control-button {
    min-width: 132px;
    font-size: 17px;
  }
}
</style>
