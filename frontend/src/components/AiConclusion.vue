<script setup>
import { nextTick, ref, watch } from 'vue'
import { store } from '../store.js'

const box = ref(null)
// 流式时自动滚到底部
watch(() => store.aiText, async () => {
  await nextTick()
  if (box.value) box.value.scrollTop = box.value.scrollHeight
})
</script>

<template>
  <div>
    <div v-if="!store.aiText && !store.streaming" class="empty">
      AI 结论将以“打字机”方式在这里流式输出…
    </div>

    <div v-if="store.analysisRound > 1" class="round">
      🔁 第 {{ store.analysisRound }} 轮分析{{ store.feedbackApplied ? '，已核实并采纳工程师打回理由，更新对应内容' : '' }}
    </div>

    <div v-if="store.conclusion" class="summary">
      {{ store.conclusion.summary }}
    </div>

    <div ref="box" class="stream">
      <pre>{{ store.aiText }}<span v-if="store.streaming" class="cursor">▋</span></pre>
    </div>
  </div>
</template>

<style scoped>
.empty { color: #a0a6b3; font-size: 13px; padding: 8px 4px; }
.summary { font-size: 13px; background: #ecf5ff; color: #337ecc; padding: 8px 10px; border-radius: 6px; margin-bottom: 8px; }
.round { font-size: 12.5px; background: #fdf6ec; color: #b88230; padding: 6px 10px; border-radius: 6px; margin-bottom: 8px; }
.stream { max-height: 360px; overflow: auto; background: #1e2430; border-radius: 8px; padding: 12px; }
.stream pre { margin: 0; color: #d7deea; font-size: 12.5px; line-height: 1.7; white-space: pre-wrap; word-break: break-word; font-family: "Cascadia Code", Consolas, monospace; }
.cursor { color: #67c23a; animation: blink 1s steps(1) infinite; }
@keyframes blink { 50% { opacity: 0; } }
</style>
