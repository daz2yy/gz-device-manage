import axios from 'axios'

const env = import.meta.env

const normalizeBaseUrl = (value) => {
  if (!value) return ''
  return value.replace(/\/+$/, '')
}

const normalizePrefix = (value, fallback) => {
  if (value === undefined) {
    return fallback
  }
  if (!value) {
    return ''
  }
  return value.startsWith('/') ? value : `/${value}`
}

const joinBaseAndPrefix = (base, prefix) => {
  if (!base) {
    return prefix || ''
  }
  return `${base}${prefix || ''}`
}

const backendBaseUrl = normalizeBaseUrl(env.VITE_BACKEND_BASE_URL ?? (env.DEV ? 'http://localhost:8001' : ''))
const apiPrefix = normalizePrefix(env.VITE_BACKEND_API_PREFIX, '/api')
const authPrefix = normalizePrefix(env.VITE_BACKEND_AUTH_PREFIX, '/auth')

const apiBaseURL = joinBaseAndPrefix(backendBaseUrl, apiPrefix)
const authBaseURL = joinBaseAndPrefix(backendBaseUrl, authPrefix)

const attachInterceptors = (instance) => {
  instance.interceptors.request.use(
    (config) => {
      const token = localStorage.getItem('token')
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
      return config
    },
    (error) => Promise.reject(error)
  )

  instance.interceptors.response.use(
    (response) => response,
    (error) => {
      if (error.response?.status === 401) {
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        window.location.href = '/login'
      }
      return Promise.reject(error)
    }
  )

  return instance
}

const api = attachInterceptors(axios.create({
  baseURL: apiBaseURL,
  timeout: 10000
}))

const authApiInstance = attachInterceptors(axios.create({
  baseURL: authBaseURL,
  timeout: 10000
}))

// Auth API
export const authAPI = {
  login: (username, password) => {
    const formData = new URLSearchParams()
    formData.append('username', username)
    formData.append('password', password)
    return authApiInstance.post('/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    })
  },
  register: (userData) => authApiInstance.post('/register', userData),
  getMe: () => {
    return authApiInstance.get('/me')
  }
}

// Device API
export const deviceAPI = {
  getDevices: (params = {}) => api.get('/devices', { params }),
  getStats: () => api.get('/devices/stats'),
  occupyDevice: (deviceId, notes) => api.post(`/devices/${deviceId}/occupy`, { notes }),
  releaseDevice: (deviceId) => api.post(`/devices/${deviceId}/release`),
  updateDevice: (deviceId, data) => api.put(`/devices/${deviceId}`, data),
  getDeviceLogs: (deviceId, params = {}) => api.get(`/devices/${deviceId}/logs`, { params }),
  scanDevices: () => api.post('/devices/scan'),
  
  // Bluetooth operations
  bluetoothConnect: (deviceId) => api.post(`/devices/${deviceId}/bluetooth/connect`),
  bluetoothDisconnect: (deviceId) => api.post(`/devices/${deviceId}/bluetooth/disconnect`),
  bluetoothPair: (deviceId) => api.post(`/devices/${deviceId}/bluetooth/pair`),
  getBluetoothInfo: (deviceId) => api.get(`/devices/${deviceId}/bluetooth/info`),
  
  // WiFi AP operations
  getWifiApInfo: (deviceId) => api.get(`/devices/${deviceId}/wifi/ap/info`),

  // Filesystem operations
  getFilesystemMounts: (deviceId) => api.get(`/devices/${deviceId}/filesystem/mounts`),

  // Version information
  getVersions: (deviceId) => api.get(`/devices/${deviceId}/versions`),

  // Log operations
  downloadFastApiLog: (deviceId) => api.get(`/devices/${deviceId}/logs/fastapi`, { responseType: 'blob' })
}

// Legacy API for backward compatibility
export const legacyAPI = {
  getAdbDevices: () => api.get('/devices'),
  getBluetoothInfos: () => api.get('/bluetooth/infos')
}

export default api
