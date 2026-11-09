<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { store } from '../store.js'

const props = defineProps({ preparing: Boolean })
const emit = defineEmits(['upload', 'demo'])

const oldFile = ref(null)
const newFile = ref(null)
const haraFile = ref(null)

// el-upload 关闭自动上传, 手动收集 raw File
function pick(which, file) {
  const raw = file.raw || file
  if (which === 'old') oldFile.value = raw
  else if (which === 'new') newFile.value = raw
  else haraFile.value = raw
}

function submit() {
  if (!oldFile.value || !newFile.value || !haraFile.value) {
    ElMessage.warning('请同时选择 旧PRD、新PRD、HARA 三个文件')
    return
  }
  emit('upload', { oldPrd: oldFile.value, newPrd: newFile.value, hara: haraFile.value })
}
</script>

<template>
  <div>
    <div class="drop">
      <p class="lbl">旧 PRD（.docx / .pdf）</p>
      <el-upload :auto-upload="false" :limit="1" accept=".docx,.pdf" :show-file-list="false"
                 :on-change="(f) => pick('old', f)">
        <el-button size="small">{{ oldFile ? '✓ ' + oldFile.name : '选择文件' }}</el-button>
      </el-upload>

      <p class="lbl">新 PRD（.docx / .pdf）</p>
      <el-upload :auto-upload="false" :limit="1" accept=".docx,.pdf" :show-file-list="false"
                 :on-change="(f) => pick('new', f)">
        <el-button size="small">{{ newFile ? '✓ ' + newFile.name : '选择文件' }}</el-button>
      </el-upload>

      <p class="lbl">旧 HARA（.xlsx）</p>
      <el-upload :auto-upload="false" :limit="1" accept=".xlsx,.xls" :show-file-list="false"
                 :on-change="(f) => pick('hara', f)">
        <el-button size="small">{{ haraFile ? '✓ ' + haraFile.name : '选择文件' }}</el-button>
      </el-upload>
    </div>

    <el-button type="primary" class="go" :loading="props.preparing" @click="submit">
      上传并开始分析
    </el-button>
    <el-divider>或</el-divider>
    <el-button class="go" :disabled="props.preparing" @click="emit('demo')">载入内置示例（ACC 场景）</el-button>

    <div v-if="store.meta" class="meta">
      <p><b>会话</b>：{{ store.sessionId.slice(0, 8) }}</p>
      <p v-if="store.haraRecordCount">HARA 条目：{{ store.haraRecordCount }} 条，关键列：{{ store.haraColumns.join(' / ') }}</p>
    </div>
  </div>
</template>

<style scoped>
.lbl { margin: 10px 0 4px; font-size: 13px; color: #5a6a85; }
.go { width: 100%; margin-top: 8px; }
.meta { margin-top: 14px; font-size: 12px; color: #8a94a6; line-height: 1.7; }
</style>
