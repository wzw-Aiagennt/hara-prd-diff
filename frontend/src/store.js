// 全局分析状态 (轻量 reactive store, 免去 Pinia 依赖)
import { reactive } from 'vue'

export const store = reactive({
  sessionId: '',
  meta: null,          // 会话元信息 (文件名等)
  diffItems: [],       // ② 差异条目
  aiText: '',          // ③ 流式全文 (打字机缓冲)
  streaming: false,    // 是否正在流式
  conclusion: null,    // 结构化结论 {summary, findings}
  reviewStatus: 'pending', // pending | approved | rejected
  reviewReason: '',
  analysisRound: 0,    // 追加需求③: 分析轮次 (>1 为结合打回理由的重分析)
  feedbackApplied: false,
  haraColumns: [],
  haraRecordCount: 0,

  reset() {
    this.sessionId = ''
    this.meta = null
    this.diffItems = []
    this.aiText = ''
    this.streaming = false
    this.conclusion = null
    this.reviewStatus = 'pending'
    this.reviewReason = ''
    this.analysisRound = 0
    this.feedbackApplied = false
    this.haraColumns = []
    this.haraRecordCount = 0
  },

  setFromSession(s) {
    this.sessionId = s.id
    this.meta = s
    this.reviewStatus = s.review_status || 'pending'
    this.diffItems = s.diff_items || []
    this.conclusion = s.conclusion || null
    this.aiText = s.ai_conclusion_text || ''
    this.reviewReason = s.review_reason || ''
    this.haraColumns = s.hara_columns || []
    this.haraRecordCount = s.hara_record_count || 0
    this.analysisRound = s.analysis_round || 0
  },
})
