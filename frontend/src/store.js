import { reactive } from 'vue'

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
    if (this.ws) return
    
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws`
    
    this.ws = new WebSocket(wsUrl)
    
    this.ws.onopen = () => {
      console.log('WebSocket connected')
    }
    
    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'device_update') {
          // Trigger device refresh
          this.$emit && this.$emit('device-update')
        }
      } catch (e) {
        console.error('WebSocket message parse error:', e)
      }
    }
    
    this.ws.onclose = () => {
      console.log('WebSocket disconnected')
      this.ws = null
      // Reconnect after 5 seconds
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
  }
})

// Initialize store
store.init()