import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000
})

// Request interceptor to add auth token
api.interceptors.request.use(
  config => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// Response interceptor to handle auth errors
api.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// Create separate auth API instance for auth endpoints
const authApiInstance = axios.create({
  baseURL: '/',
  timeout: 10000
})

// Auth API
export const authAPI = {
  login: (username, password) => {
    const formData = new FormData()
    formData.append('username', username)
    formData.append('password', password)
    return authApiInstance.post('/auth/login', formData)
  },
  register: (userData) => authApiInstance.post('/auth/register', userData),
  getMe: () => {
    const token = localStorage.getItem('token')
    return authApiInstance.get('/auth/me', {
      headers: { Authorization: `Bearer ${token}` }
    })
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
  getWifiApInfo: (deviceId) => api.get(`/devices/${deviceId}/wifi/ap/info`)
}

// Legacy API for backward compatibility
export const legacyAPI = {
  getAdbDevices: () => api.get('/devices'),
  getBluetoothInfos: () => api.get('/bluetooth/infos')
}

export default api