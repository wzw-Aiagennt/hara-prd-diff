<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { store } from './store.js'
import { loadDemo, uploadSession, streamAnalysis } from './api.js'
import UploadPanel from './components/UploadPanel.vue'
import DiffViewer from './components/DiffViewer.vue'
import AiConclusion from './components/AiConclusion.vue'
import ReviewActions from './components/ReviewActions.vue'

const closeStream = ref(null)
const preparing = ref(false)

// 开始流式分析: 差异(meta) 先渲染, 结论(token) 打字机, done 落结构化结论
function startStream(sid) {
  store.aiText = ''
  store.conclusion = null
  store.streaming = true
  if (closeStream.value) closeStream.value()
  closeStream.value = streamAnalysis(sid, {
    onMeta: (meta) => {
      store.diffItems = meta.diff_items || []
      store.analysisRound = meta.analysis_round || 1
      store.feedbackApplied = !!meta.feedback_applied
    },
    onToken: (tok) => {
      store.aiText += tok
    },
    onDone: (concl) => {
      store.conclusion = concl
      store.streaming = false
      ElMessage.success('AI 分析完成, 请进行人工判断')
    },
    onError: () => {
      store.streaming = false
      ElMessage.error('流式分析中断, 请重试')
    },
  })
}

// 追加需求③: 打回后自动结合工程师理由重新分析
function handleReanalyze() {
  ElMessage.info('正在结合您的纠正理由重新分析…')
  startStream(store.sessionId)
}

async function handleDemo() {
  preparing.value = true
  try {
    store.reset()
    const s = await loadDemo()
    store.meta = s
    store.sessionId = s.id
    startStream(s.id)
  } catch (e) {
    ElMessage.error('加载示例失败: ' + (e.message || e))
  } finally {
    preparing.value = false
  }
}

async function handleUpload(payload) {
  preparing.value = true
  try {
    store.reset()
    const s = await uploadSession(payload)
    store.meta = s
    store.sessionId = s.id
    ElMessage.success(`解析完成: 旧PRD「${s.old_prd_name}」 新PRD「${s.new_prd_name}」`)
    startStream(s.id)
  } catch (e) {
    ElMessage.error('上传/解析失败: ' + (e.response?.data?.detail || e.message || e))
  } finally {
    preparing.value = false
  }
}
</script>

<template>
  <div class="page">
    <header class="hd">
      <div class="title">
        <span class="logo">🛡️</span>
        <div>
          <h1>HARA / PRD 差异分析智能体</h1>
          <p>基于 GB/T 34590 · 差异比对 + 大模型研判 + 人工复核 + Word 报告导出</p>
        </div>
      </div>
      <div class="tags">
        <el-tag v-if="store.analysisRound > 1" type="info" effect="plain">第 {{ store.analysisRound }} 轮重分析</el-tag>
        <el-tag v-if="store.streaming" type="warning" effect="dark">分析中…</el-tag>
        <el-tag v-else-if="store.conclusion" type="success" effect="dark">已完成</el-tag>
      </div>
    </header>

    <el-row :gutter="16" class="body">
      <!-- ① 上传区 -->
      <el-col :span="6">
        <el-card shadow="never" class="col-card">
          <template #header>① 文件接收与解析</template>
          <UploadPanel :preparing="preparing" @upload="handleUpload" @demo="handleDemo" />
        </el-card>
      </el-col>

      <!-- ② 差异区 -->
      <el-col :span="9">
        <el-card shadow="never" class="col-card">
          <template #header>② 差异点识别 (difflib 逐句)</template>
          <DiffViewer />
        </el-card>
      </el-col>

      <!-- ③⑤ AI 结论 + 人工判断 -->
      <el-col :span="9">
        <el-card shadow="never" class="col-card">
          <template #header>③ AI 结论 · ⑤ 人工判断</template>
          <AiConclusion />
          <el-divider />
          <ReviewActions @reanalyze="handleReanalyze" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style>
body { margin: 0; background: #f2f4f8; font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif; }
.page { padding: 16px 20px; }
.hd { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
.title { display: flex; align-items: center; gap: 12px; }
.logo { font-size: 34px; }
.hd h1 { margin: 0; font-size: 20px; color: #1f2d3d; }
.hd p { margin: 2px 0 0; font-size: 12px; color: #8a94a6; }
.col-card { height: calc(100vh - 140px); overflow: auto; }
.col-card :deep(.el-card__header) { font-weight: 600; }
</style>
