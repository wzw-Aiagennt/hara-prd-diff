// API 层: REST (axios) + 流式分析 (EventSource / SSE)
import axios from 'axios'

const http = axios.create({ baseURL: '/api', timeout: 60000 })

// ① 上传 2×PRD + 1×HARA → 建立会话
export async function uploadSession({ oldPrd, newPrd, hara }) {
  const fd = new FormData()
  fd.append('old_prd', oldPrd)
  fd.append('new_prd', newPrd)
  fd.append('hara', hara)
  const { data } = await http.post('/sessions', fd)
  return data
}

// 载入内置示例
export async function loadDemo() {
  const { data } = await http.post('/sessions/demo')
  return data
}

export async function listSessions() {
  const { data } = await http.get('/sessions')
  return data
}

export async function getSession(sid) {
  const { data } = await http.get(`/sessions/${sid}`)
  return data
}

// ⑤ 人工判断: approve=true 认可; false 打回 (必须带 reason)
export async function review(sid, approve, reason = '') {
  const { data } = await http.post(`/sessions/${sid}/review`, { approve, reason })
  return data
}

// ⑥ 报告下载地址 (浏览器直接下载)
export function reportUrl(sid) {
  return `/api/sessions/${sid}/report`
}

// ②③④ 流式分析。callbacks: {onMeta, onToken, onDone, onError, onStage}
export function streamAnalysis(sid, callbacks = {}) {
  const es = new EventSource(`/api/sessions/${sid}/stream`)
  es.addEventListener('meta', (e) => callbacks.onMeta && callbacks.onMeta(JSON.parse(e.data)))
  es.addEventListener('token', (e) => callbacks.onToken && callbacks.onToken(e.data))
  es.addEventListener('done', (e) => {
    if (callbacks.onDone) callbacks.onDone(JSON.parse(e.data))
    es.close()
  })
  es.onerror = (err) => {
    if (callbacks.onError) callbacks.onError(err)
    es.close()
  }
  return () => es.close()
}
