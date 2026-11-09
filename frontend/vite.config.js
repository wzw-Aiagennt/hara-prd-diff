import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// /api 代理到后端 FastAPI (127.0.0.1:8000), 前端统一走相对路径, 免跨域配置
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
