<template>
  <div class="terminal-page">
    <header class="terminal-header">
      <el-button type="text" class="back-button" @click="goBack">
        <el-icon><ArrowLeft /></el-icon>
        返回设备详情
      </el-button>
      <div class="header-info">
        <h2>ADB Terminal</h2>
        <div class="sub-info">
          <el-tag size="small" type="info">{{ deviceId }}</el-tag>
          <el-tag size="small" :type="statusTagType">{{ connectionStatusLabel }}</el-tag>
        </div>
      </div>
      <div class="header-actions">
        <el-button size="small" @click="clearTerminal">清屏</el-button>
        <el-button size="small" type="danger" :disabled="connectionStatus !== 'ready'" @click="disconnect">
          断开
        </el-button>
      </div>
    </header>

    <div ref="terminalContainer" class="terminal-container"></div>
  </div>
</template>

<script>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'
import { ArrowLeft } from '@element-plus/icons-vue'
import { deviceAPI } from '../api.js'
import { store } from '../store.js'

const buildWebSocketUrl = (path) => {
  const isDev = import.meta.env.DEV
  const defaultOrigin = typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8001'
  const backendBase = import.meta.env.VITE_BACKEND_BASE_URL || (isDev ? 'http://localhost:8001' : defaultOrigin)
  const base = import.meta.env.VITE_WS_BASE_URL || backendBase
  const url = new URL(path, base)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  return url.toString()
}

export default {
  name: 'DeviceTerminal',
  setup() {
    const route = useRoute()
    const router = useRouter()
    const deviceId = computed(() => route.params.deviceId)
    const terminalContainer = ref(null)
    const connectionStatus = ref('connecting')
    const terminal = ref(null)
    const fitAddon = ref(null)
    const socket = ref(null)
    const awaitingResponse = ref(false)
    const currentDevice = ref(null)
    let closing = false
    let inputBuffer = ''

    const connectionStatusLabel = computed(() => {
      switch (connectionStatus.value) {
        case 'connecting':
          return '连接中'
        case 'ready':
          return '已连接'
        case 'closed':
          return '已断开'
        case 'denied':
          return '无权限'
        default:
          return connectionStatus.value
      }
    })

    const statusTagType = computed(() => {
      switch (connectionStatus.value) {
        case 'ready':
          return 'success'
        case 'closed':
          return 'info'
        case 'denied':
          return 'danger'
        default:
          return 'warning'
      }
    })

    const goBack = () => {
      router.push({ name: 'DeviceDetail', params: { deviceId: deviceId.value } })
    }

    const ensurePermission = async () => {
      try {
        const response = await deviceAPI.getDevices({ search: deviceId.value, limit: 1 })
        const found = response.data.find(device => device.device_id === deviceId.value)
        if (!found) {
          ElMessage.error('设备不存在或已离线')
          goBack()
          return false
        }

        const canControl = store.user?.role === 'admin' || found.occupied_by === store.user?.id
        if (!canControl || found.device_type !== 'adb') {
          ElMessage.error('当前账号无权访问 ADB Terminal')
          connectionStatus.value = 'denied'
          goBack()
          return false
        }

        currentDevice.value = found
        return true
      } catch (error) {
        console.error('Failed to verify device access:', error)
        ElMessage.error('验证设备权限失败')
        goBack()
        return false
      }
    }

    const initializeTerminal = () => {
      const term = new Terminal({
        cols: 120,
        rows: 30,
        convertEol: true,
        cursorBlink: true,
        fontSize: 14,
        theme: {
          background: '#1e1e1e',
          foreground: '#f5f5f5'
        }
      })

      const fit = new FitAddon()
      term.loadAddon(fit)
      fitAddon.value = fit
      terminal.value = term

      term.open(terminalContainer.value)
      fit.fit()

      term.writeln('ADB Terminal 准备中...')
      term.writeln('按 Enter 发送命令，Ctrl+C 取消当前输入。')
      term.write('\r\n')

      term.onData((data) => {
        if (connectionStatus.value !== 'ready') {
          return
        }

        if (awaitingResponse.value) {
          if (data === '\u0003') {
            term.write('^C')
            awaitingResponse.value = false
            writePrompt()
          }
          return
        }

        switch (data) {
          case '\r':
            term.write('\r\n')
            sendCommand(inputBuffer.trim())
            inputBuffer = ''
            break
          case '\u0003': // Ctrl+C
            term.write('^C')
            inputBuffer = ''
            writePrompt()
            break
          case '\u007f': // Backspace
            if (inputBuffer.length > 0) {
              inputBuffer = inputBuffer.slice(0, -1)
              term.write('\b \b')
            }
            break
          default:
            if (data >= ' ' && data <= '~') {
              inputBuffer += data
              term.write(data)
            }
        }
      })

      window.addEventListener('resize', handleResize)
      setTimeout(() => handleResize(), 50)
    }

    const handleResize = () => {
      if (fitAddon.value) {
        fitAddon.value.fit()
      }
      if (terminal.value) {
        terminal.value.scrollToBottom()
      }
    }

    const writePrompt = () => {
      if (!terminal.value) return
      const prompt = `adb:${deviceId.value}$ `
      terminal.value.write(`\r\n${prompt}`)
    }

    const appendOutput = (label, text, color) => {
      if (!text) return
      if (!terminal.value) return
      const lines = text.replace(/\r?\n/g, '\r\n')
      if (color) {
        terminal.value.write(`\r\n\x1b[${color}m${label}${lines}\x1b[0m`)
      } else {
        terminal.value.write(`\r\n${label}${lines}`)
      }
    }

    const sendCommand = (command) => {
      if (!command) {
        writePrompt()
        return
      }
      if (!socket.value || socket.value.readyState !== WebSocket.OPEN || !terminal.value) {
        terminal.value.write('\r\n连接不可用，命令未发送')
        writePrompt()
        return
      }

      awaitingResponse.value = true
      try {
        socket.value.send(JSON.stringify({ type: 'command', command }))
      } catch (error) {
        awaitingResponse.value = false
        terminal.value.write(`\r\n命令发送失败: ${error.message || error}`)
        writePrompt()
      }
    }

    const connectWebSocket = () => {
      if (!store.token) {
        ElMessage.error('登录已过期，请重新登录')
        router.push('/login')
        return
      }

      const wsUrl = buildWebSocketUrl(`/ws/devices/${deviceId.value}/terminal?token=${encodeURIComponent(store.token)}`)
      const ws = new WebSocket(wsUrl)
      socket.value = ws

      ws.onopen = () => {
        connectionStatus.value = 'connecting'
      }

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data)
          handleWebSocketMessage(payload)
        } catch (error) {
          console.error('Failed to parse terminal message:', error)
        }
      }

      ws.onerror = (event) => {
        console.error('Terminal websocket error:', event)
        ElMessage.error('终端连接发生错误')
      }

      ws.onclose = () => {
        connectionStatus.value = connectionStatus.value === 'denied' ? 'denied' : 'closed'
        awaitingResponse.value = false
        if (terminal.value && !closing) {
          terminal.value.write('\r\n连接已关闭')
          writePrompt()
        }
        closing = false
      }
    }

    const handleWebSocketMessage = (payload) => {
      switch (payload.type) {
        case 'ready':
          connectionStatus.value = 'ready'
          terminal.value.write(`\r\n已连接至 ${payload.device_id}`)
          writePrompt()
          break
        case 'output': {
          const { stdout, stderr, status, returncode } = payload
          if (stdout) {
            appendOutput('', stdout)
          }
          if (stderr) {
            appendOutput('', stderr, '31')
          }
          terminal.value.write(`\r\n[退出码 ${returncode}] (${status})`)
          awaitingResponse.value = false
          writePrompt()
          handleResize()
          break
        }
        case 'error':
          appendOutput('', payload.message || '执行失败', '31')
          awaitingResponse.value = false
          writePrompt()
          handleResize()
          break
        case 'timeout':
          appendOutput('', payload.message || '终端会话超时', '33')
          awaitingResponse.value = false
          disconnect()
          break
      }
    }

    const disconnect = () => {
      if (socket.value && socket.value.readyState === WebSocket.OPEN) {
        closing = true
        socket.value.close()
      }
      handleResize()
    }

    const clearTerminal = () => {
      if (terminal.value) {
        terminal.value.clear()
        terminal.value.write('ADB Terminal\r\n')
        writePrompt()
      }
    }

    onMounted(async () => {
      if (!store.token) {
        router.push('/login')
        return
      }

      const allowed = await ensurePermission()
      if (!allowed) {
        return
      }

      initializeTerminal()
      connectWebSocket()
    })

    onBeforeUnmount(() => {
      closing = true
      if (socket.value) {
        socket.value.close()
      }
      if (terminal.value) {
        terminal.value.dispose()
        terminal.value = null
      }
      window.removeEventListener('resize', handleResize)
    })

    return {
      deviceId,
      terminalContainer,
      connectionStatus,
      connectionStatusLabel,
      statusTagType,
      goBack,
      clearTerminal,
      disconnect,
      ArrowLeft
    }
  }
}
</script>

<style scoped>
.terminal-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #1e1e1e;
  color: #f5f5f5;
}

.terminal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  background: #ffffff;
  color: #303133;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.terminal-header h2 {
  margin: 0;
  font-size: 18px;
}

.back-button {
  display: flex;
  align-items: center;
  gap: 4px;
}

.header-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-left: 20px;
}

.sub-info {
  display: flex;
  gap: 8px;
  align-items: center;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.terminal-container {
  flex: 1;
  padding: 0 20px 20px;
  overflow: hidden;
}

.terminal-container .xterm {
  height: 100%;
  width: 100%;
}
</style>
