<script setup>
import { computed } from 'vue'
import { store } from '../store.js'

const TYPE_LABEL = { replace: '修改', insert: '新增', delete: '删除' }
const TYPE_TAG = { replace: 'warning', insert: 'success', delete: 'danger' }

// change_id -> finding (AI 完成后用于着色分类)
const findingMap = computed(() => {
  const m = {}
  for (const f of store.conclusion?.findings || []) m[f.change_id] = f
  return m
})

const CAT_COLOR = { reuse: '#67c23a', new: '#f56c6c', removed: '#e6a23c' }

function catOf(cid) {
  const f = findingMap.value[cid]
  if (!f) return null
  return { color: CAT_COLOR[f.category.split('-')[0]] || '#909399', label: f.category_label, risk: f.risk_level }
}
</script>

<template>
  <div v-if="store.diffItems.length === 0" class="empty">
    上传文件或载入示例后，这里显示 difflib 提取的逐句改动。
  </div>
  <el-timeline v-else>
    <el-timeline-item
      v-for="d in store.diffItems" :key="d.change_id"
      :type="TYPE_TAG[d.type]" size="normal"
    >
      <div class="row">
        <el-tag size="small" :type="TYPE_TAG[d.type]">{{ d.change_id }} · {{ TYPE_LABEL[d.type] }}</el-tag>
        <el-tag v-if="catOf(d.change_id)" size="small" :style="{ background: catOf(d.change_id).color, color: '#fff', border: 'none' }">
          {{ catOf(d.change_id).label }} · {{ catOf(d.change_id).risk }}
        </el-tag>
      </div>
      <p v-if="d.before" class="del">{{ d.before }}</p>
      <p v-if="d.after" class="ins">{{ d.after }}</p>
    </el-timeline-item>
  </el-timeline>
</template>

<style scoped>
.empty { color: #a0a6b3; font-size: 13px; padding: 20px 4px; }
.row { display: flex; gap: 8px; margin-bottom: 6px; }
.del { margin: 2px 0; padding: 4px 8px; background: #fef0f0; color: #b0413e; border-left: 3px solid #f56c6c; font-size: 13px; }
.ins { margin: 2px 0; padding: 4px 8px; background: #f0f9eb; color: #529b2e; border-left: 3px solid #67c23a; font-size: 13px; }
</style>
