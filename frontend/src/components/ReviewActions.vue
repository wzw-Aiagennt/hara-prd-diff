<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { store } from '../store.js'
import { review, reportUrl } from '../api.js'

const dialog = ref(false)
const reason = ref('')
const busy = ref(false)

// 追加需求③: 打回后通知父组件结合理由重新分析
const emit = defineEmits(['reanalyze'])

const canAnalyze = () => !!store.sessionId

// 认可并导出
async function approveAndExport() {
  if (!canAnalyze()) return ElMessage.warning('请先完成分析')
  busy.value = true
  try {
    await review(store.sessionId, true, '')
    store.reviewStatus = 'approved'
    store.reviewReason = ''
    ElMessage.success('已认可结论，正在导出报告…')
    doExport()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  } finally {
    busy.value = false
  }
}

// 打回：弹出强制理由输入
function openReject() {
  if (!canAnalyze()) return ElMessage.warning('请先完成分析')
  reason.value = ''
  dialog.value = true
}

async function confirmReject() {
  if (!reason.value.trim()) return ElMessage.warning('打回时必须填写纠正理由')
  busy.value = true
  try {
    await review(store.sessionId, false, reason.value.trim())
    store.reviewStatus = 'rejected'
    store.reviewReason = reason.value.trim()
    dialog.value = false
    ElMessage.success('已打回并记录纠正理由，将写入最终报表')
    emit('reanalyze')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  } finally {
    busy.value = false
  }
}

function doExport() {
  const a = document.createElement('a')
  a.href = reportUrl(store.sessionId)
  a.download = ''
  document.body.appendChild(a)
  a.click()
  a.remove()
}

const STATUS = {
  pending: { t: '待审核', type: 'info' },
  approved: { t: '已认可', type: 'success' },
  rejected: { t: '已打回', type: 'danger' },
}
</script>

<template>
  <div>
    <div class="bar">
      <el-tag :type="STATUS[store.reviewStatus]?.type || 'info'">审核状态：{{ STATUS[store.reviewStatus]?.t }}</el-tag>
      <el-button type="success" :disabled="!store.conclusion" :loading="busy" @click="approveAndExport">
        认可结论并导出
      </el-button>
      <el-button type="danger" plain :disabled="!store.conclusion" @click="openReject">
        不认可并打回
      </el-button>
      <el-button :disabled="!store.conclusion" @click="doExport">仅导出</el-button>
    </div>

    <p v-if="store.reviewReason" class="reason">纠正理由：{{ store.reviewReason }}</p>

    <el-dialog v-model="dialog" title="不认可 · 请填写纠正理由" width="460px">
      <p class="tip">该理由将强制记录并写入最终分析报告；确认后 AI 将结合此理由立即重新分析（示例：AI 未识别出底盘的线束接口已更改）。</p>
      <el-input v-model="reason" type="textarea" :rows="4" placeholder="请输入工程判断 / 纠正理由…" />
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="danger" :loading="busy" @click="confirmReject">确认打回</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.bar { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.reason { margin-top: 10px; font-size: 13px; color: #b0413e; background: #fef0f0; padding: 8px 10px; border-radius: 6px; }
.tip { font-size: 12px; color: #8a94a6; margin: 0 0 10px; }
</style>
