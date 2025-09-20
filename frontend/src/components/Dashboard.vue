<template>
  <div class="dashboard">
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon online">
          <el-icon><Monitor /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-number">{{ stats.total_devices }}</div>
          <div class="stat-label">总设备数</div>
        </div>
      </div>
      
      <div class="stat-card">
        <div class="stat-icon success">
          <el-icon><CircleCheck /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-number">{{ stats.online_devices }}</div>
          <div class="stat-label">在线设备</div>
        </div>
      </div>
      
      <div class="stat-card">
        <div class="stat-icon warning">
          <el-icon><User /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-number">{{ stats.occupied_devices }}</div>
          <div class="stat-label">占用设备</div>
        </div>
      </div>
      
      <div class="stat-card">
        <div class="stat-icon danger">
          <el-icon><CircleClose /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-number">{{ stats.offline_devices }}</div>
          <div class="stat-label">离线设备</div>
        </div>
      </div>
    </div>
    
    <div class="charts-section">
      <div class="chart-card">
        <h3>设备类型分布</h3>
        <div class="device-types">
          <div 
            v-for="(count, type) in stats.devices_by_type" 
            :key="type"
            class="device-type-item"
          >
            <div class="device-type-label">{{ getDeviceTypeLabel(type) }}</div>
            <div class="device-type-count">{{ count }}</div>
          </div>
        </div>
      </div>
      
      <div class="chart-card">
        <h3>设备状态分布</h3>
        <div class="status-chart">
          <div class="status-item online">
            <div class="status-bar" :style="{ width: getStatusPercentage('online') + '%' }"></div>
            <span>在线 ({{ stats.online_devices }})</span>
          </div>
          <div class="status-item occupied">
            <div class="status-bar" :style="{ width: getStatusPercentage('occupied') + '%' }"></div>
            <span>占用 ({{ stats.occupied_devices }})</span>
          </div>
          <div class="status-item offline">
            <div class="status-bar" :style="{ width: getStatusPercentage('offline') + '%' }"></div>
            <span>离线 ({{ stats.offline_devices }})</span>
          </div>
        </div>
      </div>
    </div>
    
    <div class="recent-devices">
      <div class="section-header">
        <h3>最近设备活动</h3>
        <el-button type="primary" @click="$router.push('/devices')">
          查看全部设备
        </el-button>
      </div>
      
      <el-table :data="recentDevices" style="width: 100%">
        <el-table-column prop="device_id" label="设备ID" width="200" />
        <el-table-column prop="name" label="设备名称" />
        <el-table-column prop="device_type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="getDeviceTypeTagType(row.device_type)">
              {{ getDeviceTypeLabel(row.device_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusTagType(row.status)">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="user" label="使用者" width="120">
          <template #default="{ row }">
            <span v-if="row.user">{{ row.user.username }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="last_seen" label="最后活动" width="180">
          <template #default="{ row }">
            {{ formatTime(row.last_seen) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button 
              v-if="!row.occupied_by && row.status === 'online'"
              type="primary" 
              size="small"
              @click="occupyDevice(row.device_id)"
            >
              占用
            </el-button>
            <el-button 
              v-else-if="row.occupied_by === store.user?.id"
              type="warning" 
              size="small"
              @click="releaseDevice(row.device_id)"
            >
              释放
            </el-button>
            <el-button 
              v-else-if="row.occupied_by && store.user?.role === 'admin'"
              type="danger" 
              size="small"
              @click="releaseDevice(row.device_id)"
            >
              强制释放
            </el-button>
            <el-button 
              type="info" 
              size="small"
              @click="$router.push(`/devices/${row.device_id}`)"
            >
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Monitor, CircleCheck, CircleClose, User } from '@element-plus/icons-vue'
import { deviceAPI } from '../api.js'
import { store } from '../store.js'

export default {
  name: 'Dashboard',
  setup() {
    const stats = ref({
      total_devices: 0,
      online_devices: 0,
      occupied_devices: 0,
      offline_devices: 0,
      devices_by_type: {}
    })
    
    const recentDevices = ref([])
    
    const loadStats = async () => {
      try {
        const response = await deviceAPI.getStats()
        stats.value = response.data
      } catch (error) {
        console.error('Failed to load stats:', error)
      }
    }
    
    const loadRecentDevices = async () => {
      try {
        const response = await deviceAPI.getDevices({ limit: 10 })
        recentDevices.value = response.data
      } catch (error) {
        console.error('Failed to load recent devices:', error)
      }
    }
    
    const occupyDevice = async (deviceId) => {
      try {
        await deviceAPI.occupyDevice(deviceId, '从仪表盘占用')
        ElMessage.success('设备占用成功')
        loadRecentDevices()
        loadStats()
      } catch (error) {
        ElMessage.error(error.response?.data?.detail || '占用设备失败')
      }
    }
    
    const releaseDevice = async (deviceId) => {
      try {
        await deviceAPI.releaseDevice(deviceId)
        ElMessage.success('设备释放成功')
        loadRecentDevices()
        loadStats()
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
    
    const getStatusPercentage = (status) => {
      const total = stats.value.total_devices
      if (total === 0) return 0
      
      const counts = {
        'online': stats.value.online_devices,
        'occupied': stats.value.occupied_devices,
        'offline': stats.value.offline_devices
      }
      
      return Math.round((counts[status] / total) * 100)
    }
    
    const formatTime = (timeStr) => {
      return new Date(timeStr).toLocaleString('zh-CN')
    }
    
    // Auto refresh
    let refreshInterval
    let websocketRefreshTimeout
    let unsubscribeFromDeviceUpdates
    
    onMounted(() => {
      loadStats()
      loadRecentDevices()
      
      // Ensure WebSocket connection is active
      store.connectWebSocket()

      unsubscribeFromDeviceUpdates = store.onDeviceUpdate(() => {
        if (websocketRefreshTimeout) return
        websocketRefreshTimeout = setTimeout(() => {
          loadStats()
          loadRecentDevices()
          websocketRefreshTimeout = null
        }, 500)
      })

      // Auto refresh every 30 seconds as a fallback
      refreshInterval = setInterval(() => {
        loadStats()
        loadRecentDevices()
      }, 30000)
    })

    onUnmounted(() => {
      if (unsubscribeFromDeviceUpdates) {
        unsubscribeFromDeviceUpdates()
      }
      if (websocketRefreshTimeout) {
        clearTimeout(websocketRefreshTimeout)
        websocketRefreshTimeout = null
      }
      if (refreshInterval) {
        clearInterval(refreshInterval)
      }
    })
    
    return {
      stats,
      recentDevices,
      store,
      occupyDevice,
      releaseDevice,
      getDeviceTypeLabel,
      getDeviceTypeTagType,
      getStatusLabel,
      getStatusTagType,
      getStatusPercentage,
      formatTime,
      Monitor,
      CircleCheck,
      CircleClose,
      User
    }
  }
}
</script>

<style scoped>
.dashboard {
  padding: 20px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 20px;
  margin-bottom: 30px;
}

.stat-card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  display: flex;
  align-items: center;
  gap: 15px;
}

.stat-icon {
  width: 50px;
  height: 50px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  color: white;
}

.stat-icon.online { background: #409eff; }
.stat-icon.success { background: #67c23a; }
.stat-icon.warning { background: #e6a23c; }
.stat-icon.danger { background: #f56c6c; }

.stat-number {
  font-size: 28px;
  font-weight: bold;
  color: #333;
}

.stat-label {
  color: #666;
  font-size: 14px;
}

.charts-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 30px;
}

.chart-card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.chart-card h3 {
  margin-bottom: 20px;
  color: #333;
}

.device-types {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.device-type-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px;
  background: #f5f7fa;
  border-radius: 4px;
}

.device-type-count {
  font-weight: bold;
  color: #409eff;
}

.status-chart {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.status-item {
  position: relative;
  padding: 8px 0;
}

.status-bar {
  height: 20px;
  border-radius: 10px;
  margin-bottom: 5px;
  transition: width 0.3s ease;
}

.status-item.online .status-bar { background: #67c23a; }
.status-item.occupied .status-bar { background: #e6a23c; }
.status-item.offline .status-bar { background: #f56c6c; }

.recent-devices {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.section-header h3 {
  margin: 0;
  color: #333;
}

.text-muted {
  color: #999;
}

@media (max-width: 768px) {
  .charts-section {
    grid-template-columns: 1fr;
  }
  
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>