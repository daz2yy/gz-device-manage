import { reactive } from 'vue'

const DEV_MODE = import.meta.env.DEV
const DEFAULT_ORIGIN = typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8001'
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || (DEV_MODE ? 'http://localhost:8001' : DEFAULT_ORIGIN)
const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL || API_BASE_URL
const deviceUpdateListeners = new Set()

const buildWebSocketUrl = () => {
  const base = WS_BASE_URL || DEFAULT_ORIGIN
  const url = new URL('/ws', base)
  if (url.protocol === 'http:') {
    url.protocol = 'ws:'
  } else if (url.protocol === 'https:') {
    url.protocol = 'wss:'
  }
  return url.toString()
}

const notifyDeviceUpdate = (payload) => {
  deviceUpdateListeners.forEach((listener) => {
    try {
      listener(payload)
    } catch (error) {
      console.error('Device update listener failed:', error)
    }
  })
}

export const store = reactive({
  user: null,
  token: null,
  devices: [],
  stats: {
    total_devices: 0,
    online_devices: 0,
    occupied_devices: 0,
    offline_devices: 0,
    devices_by_type: {}
  },
  
  // WebSocket connection
  ws: null,
  
  // UI state
  loading: false,
  error: null,
  
  // Initialize from localStorage
  init() {
    const token = localStorage.getItem('token')
    const user = localStorage.getItem('user')
    
    if (token) {
      this.token = token
    }
    if (user) {
      try {
        this.user = JSON.parse(user)
      } catch (e) {
        localStorage.removeItem('user')
      }
    }
  },
  
  // Auth methods
  setAuth(token, user) {
    this.token = token
    this.user = user
    localStorage.setItem('token', token)
    localStorage.setItem('user', JSON.stringify(user))
  },
  
  clearAuth() {
    this.token = null
    this.user = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  },
  
  // Device methods
  setDevices(devices) {
    this.devices = devices
  },
  
  setStats(stats) {
    this.stats = stats
  },
  
  updateDevice(deviceId, updates) {
    const index = this.devices.findIndex(d => d.device_id === deviceId)
    if (index !== -1) {
      Object.assign(this.devices[index], updates)
    }
  },
  
  // WebSocket methods
  connectWebSocket() {
    if (this.ws || !this.token) return

    const wsUrl = buildWebSocketUrl()

    try {
      this.ws = new WebSocket(wsUrl)
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error)
      this.ws = null
      return
    }

    this.ws.onopen = () => {
      console.log('WebSocket connected:', wsUrl)
    }

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'device_update') {
          notifyDeviceUpdate(data)
        }
      } catch (e) {
        console.error('WebSocket message parse error:', e)
      }
    }

    this.ws.onclose = () => {
      console.log('WebSocket disconnected')
      this.ws = null
      // Reconnect after 5 seconds when authenticated
      setTimeout(() => {
        if (this.token) {
          this.connectWebSocket()
        }
      }, 5000)
    }

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error)
    }
  },

  disconnectWebSocket() {
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  },

  onDeviceUpdate(callback) {
    if (typeof callback !== 'function') {
      return () => {}
    }
    deviceUpdateListeners.add(callback)
    return () => deviceUpdateListeners.delete(callback)
  }
})

// Initialize store
store.init()