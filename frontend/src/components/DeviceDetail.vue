<template>
  <div class="device-detail" v-loading="loading">
    <div class="page-header">
      <div>
        <h1>{{ device.name || device.device_id }}</h1>
        <p class="device-id">设备ID: {{ device.device_id }}</p>
      </div>
      <div class="header-actions">
        <el-button @click="goBack">
          <el-icon><ArrowLeft /></el-icon>
          返回
        </el-button>
        <el-button 
          v-if="!device.occupied_by && device.status === 'online'"
          type="primary"
          @click="occupyDevice"
        >
          占用设备
        </el-button>
        <el-button 
          v-else-if="device.occupied_by === store.user?.id"
          type="warning"
          @click="releaseDevice"
        >
          释放设备
        </el-button>
        <el-button 
          v-else-if="device.occupied_by && store.user?.role === 'admin'"
          type="danger"
          @click="releaseDevice"
        >
          强制释放
        </el-button>
        
        <!-- Bluetooth Controls -->
        <div v-if="device.device_type === 'bluetooth'" class="bluetooth-controls">
          <el-button 
            v-if="!device.connection_info?.bluetooth_info?.connected"
            type="success"
            @click="connectBluetooth"
            :loading="bluetoothLoading"
          >
            连接蓝牙
          </el-button>
          <el-button 
            v-else
            type="warning"
            @click="disconnectBluetooth"
            :loading="bluetoothLoading"
          >
            断开蓝牙
          </el-button>
          
          <el-button 
            v-if="!device.connection_info?.bluetooth_info?.paired"
            type="primary"
            @click="pairBluetooth"
            :loading="bluetoothLoading"
          >
            配对设备
          </el-button>
        </div>
      </div>
    </div>
    
    <div class="device-info">
      <el-row :gutter="20">
        <!-- Basic Info -->
        <el-col :span="12">
          <div class="info-card">
            <h3>基本信息</h3>
            <div class="info-grid">
              <div class="info-item">
                <label>设备类型</label>
                <el-tag :type="getDeviceTypeTagType(device.device_type)">
                  {{ getDeviceTypeLabel(device.device_type) }}
                </el-tag>
              </div>
              <div class="info-item">
                <label>设备状态</label>
                <el-tag :type="getStatusTagType(device.status)">
                  {{ getStatusLabel(device.status) }}
                </el-tag>
              </div>
              <div class="info-item">
                <label>设备分组</label>
                <span v-if="device.group_name">{{ device.group_name }}</span>
                <span v-else class="text-muted">未分组</span>
              </div>
              <div class="info-item">
                <label>创建时间</label>
                <span>{{ formatTime(device.created_at) }}</span>
              </div>
              <div class="info-item">
                <label>最后活动</label>
                <span>{{ formatTime(device.last_seen) }}</span>
              </div>
              <div class="info-item">
                <label>设备标签</label>
                <div>
                  <el-tag 
                    v-for="tag in device.tags" 
                    :key="tag" 
                    size="small" 
                    style="margin-right: 5px;"
                  >
                    {{ tag }}
                  </el-tag>
                  <span v-if="!device.tags || device.tags.length === 0" class="text-muted">无标签</span>
                </div>
              </div>
            </div>
          </div>
        </el-col>
        
        <!-- Occupation Info -->
        <el-col :span="12">
          <div class="info-card">
            <h3>占用信息</h3>
            <div class="info-grid">
              <div class="info-item">
                <label>当前使用者</label>
                <span v-if="device.user">{{ device.user.username }}</span>
                <span v-else class="text-muted">无</span>
              </div>
              <div class="info-item">
                <label>占用时间</label>
                <span v-if="device.occupied_at">{{ formatTime(device.occupied_at) }}</span>
                <span v-else class="text-muted">-</span>
              </div>
              <div class="info-item">
                <label>使用时长</label>
                <span v-if="device.occupied_at">{{ getUsageDuration(device.occupied_at) }}</span>
                <span v-else class="text-muted">-</span>
              </div>
            </div>
          </div>
        </el-col>
      </el-row>
      
      <!-- Connection Info -->
      <div class="info-card">
        <h3>连接信息</h3>
        <div v-if="device.device_type === 'adb'" class="connection-info">
          <div class="info-item">
            <label>ADB状态</label>
            <span>{{ device.connection_info?.adb_status || '-' }}</span>
          </div>
        </div>
        
        <div v-else-if="device.device_type === 'bluetooth'" class="connection-info">
          <div class="bluetooth-info">
            <div class="info-item">
              <label>ADB主机</label>
              <span>{{ device.connection_info?.adb_host || '-' }}</span>
            </div>
            <div class="info-item">
              <label>蓝牙连接状态</label>
              <el-tag :type="device.connection_info?.bluetooth_info?.connected ? 'success' : 'danger'">
                {{ device.connection_info?.bluetooth_info?.connected ? '已连接' : '未连接' }}
              </el-tag>
            </div>
            <div class="info-item">
              <label>配对状态</label>
              <span>{{ device.connection_info?.bluetooth_info?.paired ? '已配对' : '未配对' }}</span>
            </div>
            <div class="info-item">
              <label>信任状态</label>
              <span>{{ device.connection_info?.bluetooth_info?.trusted ? '已信任' : '未信任' }}</span>
            </div>
            <div class="info-item">
              <label>RSSI</label>
              <span>{{ device.connection_info?.bluetooth_info?.rssi || '-' }}</span>
            </div>
            <div class="info-item">
              <label>UUIDs</label>
              <div>
                <el-tag 
                  v-for="uuid in device.connection_info?.bluetooth_info?.uuids || []" 
                  :key="uuid.uuid"
                  size="small"
                  style="margin: 2px;"
                  :title="uuid.uuid"
                >
                  {{ uuid.desc || uuid.uuid }}
                </el-tag>
                <span v-if="!device.connection_info?.bluetooth_info?.uuids?.length" class="text-muted">无</span>
              </div>
            </div>
          </div>
        </div>
        
        <!-- Raw Connection Info -->
        <el-collapse style="margin-top: 20px;">
          <el-collapse-item title="原始连接信息" name="raw">
            <pre class="raw-info">{{ JSON.stringify(device.connection_info, null, 2) }}</pre>
          </el-collapse-item>
        </el-collapse>
      </div>

      <!-- Filesystem Info -->
      <div
        v-if="device.device_type === 'adb'"
        class="info-card"
        v-loading="filesystemLoading"
      >
        <div class="card-header">
          <h3>文件系统权限</h3>
          <div class="card-actions">
            <el-button size="small" @click="loadFilesystemInfo" :loading="filesystemLoading">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </div>
        </div>

        <div v-if="filesystemError" class="section-alert">
          <el-alert :title="filesystemError" type="error" show-icon />
        </div>

        <template v-if="filesystemInfo">
          <div
            v-if="filesystemInfo.zhuimi_writable === false"
            class="section-alert"
          >
            <el-alert
              title="/data/zhuimi 挂载点未开启写权限，可能导致程序异常"
              type="error"
              show-icon
            />
          </div>

          <el-table :data="filesystemInfo ? filesystemInfo.mounts : []" size="small">
            <el-table-column prop="mount_point" label="挂载点" width="160" />
            <el-table-column prop="source" label="来源" width="200">
              <template #default="{ row }">
                <span>{{ row.source || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="fstype" label="文件系统" width="140">
              <template #default="{ row }">
                <span>{{ row.fstype || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="options" label="挂载选项">
              <template #default="{ row }">
                <span class="mount-options">
                  {{ row.options && row.options.length ? row.options.join(', ') : '-' }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="writable" label="可写" width="100">
              <template #default="{ row }">
                <el-tag :type="row.writable ? 'success' : 'danger'">
                  {{ row.writable ? '可写' : '只读' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>

          <el-collapse style="margin-top: 20px;">
            <el-collapse-item title="mount 命令输出" name="mount-raw">
              <pre class="raw-info">{{ filesystemInfo.raw_output }}</pre>
            </el-collapse-item>
          </el-collapse>
        </template>
      </div>

      <!-- Version Info -->
      <div
        v-if="device.device_type === 'adb'"
        class="info-card"
        v-loading="versionLoading"
      >
        <div class="card-header">
          <h3>版本信息</h3>
          <div class="card-actions">
            <el-button size="small" @click="loadVersionInfo" :loading="versionLoading">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </div>
        </div>

        <div v-if="versionError" class="section-alert">
          <el-alert :title="versionError" type="error" show-icon />
        </div>

        <template v-if="versionInfo">
          <div class="info-grid compact-grid">
            <div class="info-item">
              <label>主机版本</label>
              <span>{{ versionInfo.versions?.host || '-' }}</span>
            </div>
            <div class="info-item">
              <label>主机星闪版本</label>
              <span>{{ versionInfo.versions?.host_starflash || '-' }}</span>
            </div>
            <div class="info-item">
              <label>座舱版本</label>
              <span>{{ versionInfo.versions?.cabin || '-' }}</span>
            </div>
            <div class="info-item">
              <label>座舱星闪版本</label>
              <span>{{ versionInfo.versions?.cabin_starflash || '-' }}</span>
            </div>
          </div>

          <el-collapse style="margin-top: 20px;">
            <el-collapse-item title="ql-getversion 原始输出" name="version-raw">
              <pre class="raw-info">{{ versionInfo.raw_output }}</pre>
            </el-collapse-item>
          </el-collapse>
        </template>
      </div>

      <!-- Log Tools -->
      <div v-if="device.device_type === 'adb'" class="info-card">
        <div class="card-header">
          <h3>日志工具</h3>
          <div class="card-actions">
            <el-button
              type="primary"
              :loading="logDownloading"
              @click="downloadFastApiLog"
            >
              <el-icon><Download /></el-icon>
              拉取 FastAPI 日志
            </el-button>
          </div>
        </div>
        <p class="card-description">当前仅支持一键拉取 /tmp/log_FastAPI.log。</p>
      </div>

      <!-- Usage Logs -->
      <div class="info-card">
        <div class="card-header">
          <h3>使用日志</h3>
          <el-button @click="loadLogs" :loading="logsLoading">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
        
        <el-table :data="logs" v-loading="logsLoading">
          <el-table-column prop="action" label="操作" width="120">
            <template #default="{ row }">
              <el-tag :type="getActionTagType(row.action)">
                {{ getActionLabel(row.action) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="user.username" label="用户" width="120" />
          <el-table-column prop="timestamp" label="时间" width="180">
            <template #default="{ row }">
              {{ formatTime(row.timestamp) }}
            </template>
          </el-table-column>
          <el-table-column prop="notes" label="备注">
            <template #default="{ row }">
              <span v-if="row.notes">{{ row.notes }}</span>
              <span v-else class="text-muted">-</span>
            </template>
          </el-table-column>
        </el-table>
        
        <div v-if="logs.length === 0 && !logsLoading" class="empty-logs">
          <el-empty description="暂无使用日志" />
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Refresh, Download } from '@element-plus/icons-vue'
import { deviceAPI } from '../api.js'
import { store } from '../store.js'

export default {
  name: 'DeviceDetail',
  setup() {
    const route = useRoute()
    const router = useRouter()
    const device = ref({})
    const logs = ref([])
    const loading = ref(false)
    const logsLoading = ref(false)
    const bluetoothLoading = ref(false)
    let websocketRefreshTimeout
    let unsubscribeFromDeviceUpdates
    const filesystemInfo = ref(null)
    const filesystemLoading = ref(false)
    const filesystemError = ref('')
    const versionInfo = ref(null)
    const versionLoading = ref(false)
    const versionError = ref('')
    const logDownloading = ref(false)
    
    const deviceId = computed(() => route.params.deviceId)
    
    const loadDevice = async () => {
      loading.value = true
      try {
        // Get device from devices list (simplified approach)
        const response = await deviceAPI.getDevices({
          search: deviceId.value,
          limit: 1
        })

        const foundDevice = response.data.find(d => d.device_id === deviceId.value)
        if (foundDevice) {
          device.value = foundDevice
          if (foundDevice.device_type === 'adb') {
            await Promise.all([loadFilesystemInfo(), loadVersionInfo()])
          } else {
            filesystemInfo.value = null
            filesystemError.value = ''
            filesystemLoading.value = false
            versionInfo.value = null
            versionError.value = ''
            versionLoading.value = false
          }
        } else {
          ElMessage.error('设备不存在')
        }
      } catch (error) {
        console.error('Failed to load device:', error)
        ElMessage.error('加载设备信息失败')
      } finally {
        loading.value = false
      }
    }
    
    const loadLogs = async () => {
      logsLoading.value = true
      try {
        const response = await deviceAPI.getDeviceLogs(deviceId.value)
        logs.value = response.data
      } catch (error) {
        console.error('Failed to load logs:', error)
        ElMessage.error('加载使用日志失败')
      } finally {
        logsLoading.value = false
      }
    }

    const loadFilesystemInfo = async () => {
      if (device.value.device_type !== 'adb') {
        filesystemInfo.value = null
        filesystemError.value = ''
        filesystemLoading.value = false
        return
      }

      filesystemLoading.value = true
      filesystemError.value = ''
      try {
        const response = await deviceAPI.getFilesystemMounts(deviceId.value)
        filesystemInfo.value = response.data
      } catch (error) {
        console.error('Failed to load filesystem info:', error)
        filesystemInfo.value = null
        filesystemError.value = error.response?.data?.detail || '加载文件系统信息失败'
      } finally {
        filesystemLoading.value = false
      }
    }

    const loadVersionInfo = async () => {
      if (device.value.device_type !== 'adb') {
        versionInfo.value = null
        versionError.value = ''
        versionLoading.value = false
        return
      }

      versionLoading.value = true
      versionError.value = ''
      try {
        const response = await deviceAPI.getVersions(deviceId.value)
        versionInfo.value = response.data
      } catch (error) {
        console.error('Failed to load version info:', error)
        versionInfo.value = null
        versionError.value = error.response?.data?.detail || '加载版本信息失败'
      } finally {
        versionLoading.value = false
      }
    }

    const occupyDevice = async () => {
      try {
        await deviceAPI.occupyDevice(deviceId.value, '从设备详情页占用')
        ElMessage.success('设备占用成功')
        loadDevice()
        loadLogs()
      } catch (error) {
        ElMessage.error(error.response?.data?.detail || '占用设备失败')
      }
    }
    
    const releaseDevice = async () => {
      try {
        await deviceAPI.releaseDevice(deviceId.value)
        ElMessage.success('设备释放成功')
        loadDevice()
        loadLogs()
      } catch (error) {
        ElMessage.error(error.response?.data?.detail || '释放设备失败')
      }
    }
    
    const getDeviceTypeLabel = (type) => {
      const labels = {
        'adb': 'ADB',
        'bluetooth': '蓝牙',
        'wifi': 'Wi-Fi',
        'starflash': '星闪'
      }
      return labels[type] || type
    }
    
    const getDeviceTypeTagType = (type) => {
      const types = {
        'adb': 'primary',
        'bluetooth': 'success',
        'wifi': 'warning',
        'starflash': 'info'
      }
      return types[type] || 'info'
    }
    
    const getStatusLabel = (status) => {
      const labels = {
        'online': '在线',
        'offline': '离线',
        'occupied': '占用'
      }
      return labels[status] || status
    }
    
    const getStatusTagType = (status) => {
      const types = {
        'online': 'success',
        'offline': 'danger',
        'occupied': 'warning'
      }
      return types[status] || 'info'
    }
    
    const formatTime = (timeStr) => {
      return new Date(timeStr).toLocaleString('zh-CN')
    }
    
    const getUsageDuration = (startTime) => {
      const start = new Date(startTime)
      const now = new Date()
      const diff = now - start
      
      const hours = Math.floor(diff / (1000 * 60 * 60))
      const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))
      
      if (hours > 0) {
        return `${hours}小时${minutes}分钟`
      } else {
        return `${minutes}分钟`
      }
    }
    
    // Bluetooth operation methods
    const connectBluetooth = async () => {
      bluetoothLoading.value = true
      try {
        const response = await deviceAPI.bluetoothConnect(deviceId.value)
        ElMessage.success('蓝牙连接命令已发送')
        
        // Refresh device info after a short delay
        setTimeout(() => {
          loadDevice()
          loadLogs()
        }, 2000)
        
      } catch (error) {
        ElMessage.error(error.response?.data?.detail || '蓝牙连接失败')
      } finally {
        bluetoothLoading.value = false
      }
    }
    
    const disconnectBluetooth = async () => {
      bluetoothLoading.value = true
      try {
        const response = await deviceAPI.bluetoothDisconnect(deviceId.value)
        ElMessage.success('蓝牙断开命令已发送')
        
        // Refresh device info after a short delay
        setTimeout(() => {
          loadDevice()
          loadLogs()
        }, 2000)
        
      } catch (error) {
        ElMessage.error(error.response?.data?.detail || '蓝牙断开失败')
      } finally {
        bluetoothLoading.value = false
      }
    }
    
    const pairBluetooth = async () => {
      bluetoothLoading.value = true
      try {
        const response = await deviceAPI.bluetoothPair(deviceId.value)
        ElMessage.success('蓝牙配对命令已发送')

        // Refresh device info after a short delay
        setTimeout(() => {
          loadDevice()
          loadLogs()
        }, 3000)

      } catch (error) {
        ElMessage.error(error.response?.data?.detail || '蓝牙配对失败')
      } finally {
        bluetoothLoading.value = false
      }
    }

    const downloadFastApiLog = async () => {
      if (device.value.device_type !== 'adb') {
        ElMessage.warning('仅支持 ADB 设备日志拉取')
        return
      }

      logDownloading.value = true
      try {
        const response = await deviceAPI.downloadFastApiLog(deviceId.value)
        const contentType = response.headers['content-type'] || 'text/plain'
        const blob = new Blob([response.data], { type: contentType })
        let filename = `${deviceId.value}_log_FastAPI.log`
        const disposition = response.headers['content-disposition']
        if (disposition) {
          const match = disposition.match(/filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i)
          const encodedName = match?.[1] || match?.[2]
          if (encodedName) {
            try {
              filename = decodeURIComponent(encodedName)
            } catch (e) {
              filename = encodedName
            }
          }
        }

        const url = window.URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = filename
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        window.URL.revokeObjectURL(url)

        ElMessage.success('日志拉取成功')
        loadLogs()
      } catch (error) {
        console.error('Failed to download log:', error)
        let message = error.response?.data?.detail || '拉取日志失败'
        if (!message && error.response?.data instanceof Blob) {
          try {
            const text = await error.response.data.text()
            try {
              const parsed = JSON.parse(text)
              message = parsed?.detail || message
            } catch (parseErr) {
              message = text || message
            }
          } catch (blobError) {
            console.error('Failed to parse log error response:', blobError)
          }
        }
        ElMessage.error(message || '拉取日志失败')
      } finally {
        logDownloading.value = false
      }
    }

    const goBack = () => {
      // Try to go back to device list, fallback to home if no history
      if (window.history.length > 1) {
        router.push('/devices')
      } else {
        router.push('/')
      }
    }
    
    const getActionLabel = (action) => {
      const labels = {
        'occupy': '占用',
        'release': '释放',
        'bluetooth_connect': '蓝牙连接',
        'bluetooth_disconnect': '蓝牙断开',
        'bluetooth_pair': '蓝牙配对',
        'download_fastapi_log': '拉取FastAPI日志'
      }
      return labels[action] || action
    }

    const getActionTagType = (action) => {
      const types = {
        'occupy': 'warning',
        'release': 'success',
        'bluetooth_connect': 'primary',
        'bluetooth_disconnect': 'info',
        'bluetooth_pair': 'success',
        'download_fastapi_log': 'primary'
      }
      return types[action] || 'info'
    }
    
    onMounted(() => {
      loadDevice()
      loadLogs()
      store.connectWebSocket()

      unsubscribeFromDeviceUpdates = store.onDeviceUpdate(() => {
        if (websocketRefreshTimeout) return
        websocketRefreshTimeout = setTimeout(() => {
          loadDevice()
          loadLogs()
          websocketRefreshTimeout = null
        }, 500)
      })
    })

    onUnmounted(() => {
      if (unsubscribeFromDeviceUpdates) {
        unsubscribeFromDeviceUpdates()
      }
      if (websocketRefreshTimeout) {
        clearTimeout(websocketRefreshTimeout)
        websocketRefreshTimeout = null
      }
    })
    
    return {
      device,
      logs,
      loading,
      logsLoading,
      bluetoothLoading,
      filesystemInfo,
      filesystemLoading,
      filesystemError,
      versionInfo,
      versionLoading,
      versionError,
      logDownloading,
      store,
      loadDevice,
      loadLogs,
      loadFilesystemInfo,
      loadVersionInfo,
      occupyDevice,
      releaseDevice,
      connectBluetooth,
      disconnectBluetooth,
      pairBluetooth,
      downloadFastApiLog,
      goBack,
      getActionLabel,
      getActionTagType,
      getDeviceTypeLabel,
      getDeviceTypeTagType,
      getStatusLabel,
      getStatusTagType,
      formatTime,
      getUsageDuration,
      ArrowLeft,
      Refresh,
      Download
    }
  }
}
</script>

<style scoped>
.device-detail {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 30px;
}

.page-header h1 {
  margin: 0 0 5px 0;
  color: #333;
}

.device-id {
  margin: 0;
  color: #666;
  font-size: 14px;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.info-card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  margin-bottom: 20px;
}

.info-card h3 {
  margin: 0 0 20px 0;
  color: #333;
  border-bottom: 1px solid #eee;
  padding-bottom: 10px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.card-header h3 {
  margin: 0;
  border: none;
  padding: 0;
}

.card-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 20px;
}

.compact-grid {
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.info-item label {
  font-weight: 600;
  color: #666;
  font-size: 14px;
}

.connection-info .info-grid {
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
}

.bluetooth-info {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 15px;
}

.raw-info {
  background: #f5f7fa;
  padding: 15px;
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.4;
  overflow-x: auto;
  max-height: 300px;
}

.mount-options {
  word-break: break-all;
}

.text-muted {
  color: #999;
}

.empty-logs {
  text-align: center;
  padding: 40px 0;
}

.section-alert {
  margin-bottom: 15px;
}

.card-description {
  margin: 0;
  color: #666;
  font-size: 14px;
}

.bluetooth-controls {
  display: flex;
  gap: 10px;
  margin-left: 10px;
  padding-left: 10px;
  border-left: 2px solid #e4e7ed;
}
</style>