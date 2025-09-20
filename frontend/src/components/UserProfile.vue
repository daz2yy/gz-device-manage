<template>
  <div class="user-profile">
    <div class="page-header">
      <h1>个人资料</h1>
    </div>
    
    <div class="profile-content">
      <el-row :gutter="20">
        <el-col :span="8">
          <div class="profile-card">
            <div class="avatar-section">
              <el-avatar :size="80" :src="avatarUrl">
                <el-icon><User /></el-icon>
              </el-avatar>
              <h3>{{ store.user?.username }}</h3>
              <el-tag :type="getRoleTagType(store.user?.role)">
                {{ getRoleLabel(store.user?.role) }}
              </el-tag>
            </div>
            
            <div class="user-info">
              <div class="info-item">
                <label>邮箱</label>
                <span>{{ store.user?.email }}</span>
              </div>
              <div class="info-item">
                <label>注册时间</label>
                <span>{{ formatTime(store.user?.created_at) }}</span>
              </div>
              <div class="info-item">
                <label>账户状态</label>
                <el-tag :type="store.user?.is_active ? 'success' : 'danger'">
                  {{ store.user?.is_active ? '正常' : '已禁用' }}
                </el-tag>
              </div>
            </div>
          </div>
        </el-col>
        
        <el-col :span="16">
          <div class="stats-card">
            <h3>使用统计</h3>
            <div class="stats-grid">
              <div class="stat-item">
                <div class="stat-number">{{ userStats.occupied_devices }}</div>
                <div class="stat-label">当前占用设备</div>
              </div>
              <div class="stat-item">
                <div class="stat-number">{{ userStats.total_occupations }}</div>
                <div class="stat-label">总占用次数</div>
              </div>
              <div class="stat-item">
                <div class="stat-number">{{ userStats.total_usage_hours }}h</div>
                <div class="stat-label">总使用时长</div>
              </div>
            </div>
          </div>
          
          <div class="occupied-devices-card">
            <div class="card-header">
              <h3>当前占用的设备</h3>
              <el-button @click="loadOccupiedDevices" :loading="loading">
                <el-icon><Refresh /></el-icon>
                刷新
              </el-button>
            </div>
            
            <el-table :data="occupiedDevices" v-loading="loading">
              <el-table-column prop="device_id" label="设备ID" width="200">
                <template #default="{ row }">
                  <el-button type="text" @click="$router.push(`/devices/${row.device_id}`)">
                    {{ row.device_id }}
                  </el-button>
                </template>
              </el-table-column>
              <el-table-column prop="name" label="设备名称" />
              <el-table-column prop="device_type" label="类型" width="100">
                <template #default="{ row }">
                  <el-tag :type="getDeviceTypeTagType(row.device_type)">
                    {{ getDeviceTypeLabel(row.device_type) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="occupied_at" label="占用时间" width="180">
                <template #default="{ row }">
                  {{ formatTime(row.occupied_at) }}
                </template>
              </el-table-column>
              <el-table-column label="使用时长" width="120">
                <template #default="{ row }">
                  {{ getUsageDuration(row.occupied_at) }}
                </template>
              </el-table-column>
              <el-table-column label="操作" width="100">
                <template #default="{ row }">
                  <el-button 
                    type="warning" 
                    size="small"
                    @click="releaseDevice(row.device_id)"
                  >
                    释放
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
            
            <div v-if="occupiedDevices.length === 0 && !loading" class="empty-devices">
              <el-empty description="暂无占用的设备" />
            </div>
          </div>
          
          <div class="recent-activity-card">
            <div class="card-header">
              <h3>最近活动</h3>
              <el-button @click="loadRecentActivity" :loading="activityLoading">
                <el-icon><Refresh /></el-icon>
                刷新
              </el-button>
            </div>
            
            <el-timeline>
              <el-timeline-item
                v-for="activity in recentActivity"
                :key="activity.id"
                :timestamp="formatTime(activity.timestamp)"
                :type="activity.action === 'occupy' ? 'warning' : 'success'"
              >
                <div class="activity-item">
                  <div class="activity-action">
                    <el-tag :type="activity.action === 'occupy' ? 'warning' : 'success'" size="small">
                      {{ activity.action === 'occupy' ? '占用' : '释放' }}
                    </el-tag>
                    <span class="device-name">{{ activity.device.name || activity.device.device_id }}</span>
                  </div>
                  <div v-if="activity.notes" class="activity-notes">
                    {{ activity.notes }}
                  </div>
                </div>
              </el-timeline-item>
            </el-timeline>
            
            <div v-if="recentActivity.length === 0 && !activityLoading" class="empty-activity">
              <el-empty description="暂无活动记录" />
            </div>
          </div>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { User, Refresh } from '@element-plus/icons-vue'
import { deviceAPI } from '../api.js'
import { store } from '../store.js'

export default {
  name: 'UserProfile',
  setup() {
    const occupiedDevices = ref([])
    const recentActivity = ref([])
    const loading = ref(false)
    const activityLoading = ref(false)
    let websocketRefreshTimeout
    let unsubscribeFromDeviceUpdates
    
    const userStats = ref({
      occupied_devices: 0,
      total_occupations: 0,
      total_usage_hours: 0
    })
    
    const avatarUrl = computed(() => {
      // Generate avatar URL based on username
      const username = store.user?.username || 'user'
      return `https://api.dicebear.com/7.x/initials/svg?seed=${username}`
    })
    
    const loadOccupiedDevices = async () => {
      loading.value = true
      try {
        const response = await deviceAPI.getDevices({ 
          status: 'occupied',
          limit: 100 
        })
        
        // Filter devices occupied by current user
        occupiedDevices.value = response.data.filter(
          device => device.occupied_by === store.user?.id
        )
        
        userStats.value.occupied_devices = occupiedDevices.value.length
        
      } catch (error) {
        console.error('Failed to load occupied devices:', error)
        ElMessage.error('加载占用设备失败')
      } finally {
        loading.value = false
      }
    }
    
    const loadRecentActivity = async () => {
      activityLoading.value = true
      try {
        // Get all devices and their logs to find user's recent activity
        // This is a simplified approach - in real app, API should support user-specific logs
        const devicesResponse = await deviceAPI.getDevices({ limit: 100 })
        const allActivity = []
        
        for (const device of devicesResponse.data) {
          try {
            const logsResponse = await deviceAPI.getDeviceLogs(device.device_id, { limit: 10 })
            const userLogs = logsResponse.data.filter(log => log.user_id === store.user?.id)
            allActivity.push(...userLogs)
          } catch (error) {
            // Ignore errors for individual device logs
          }
        }
        
        // Sort by timestamp and take recent 10
        recentActivity.value = allActivity
          .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
          .slice(0, 10)
        
        // Calculate stats
        userStats.value.total_occupations = allActivity.filter(a => a.action === 'occupy').length
        
        // Calculate total usage hours (simplified)
        let totalHours = 0
        const occupyLogs = allActivity.filter(a => a.action === 'occupy')
        const releaseLogs = allActivity.filter(a => a.action === 'release')
        
        occupyLogs.forEach(occupy => {
          const release = releaseLogs.find(r => 
            r.device_id === occupy.device_id && 
            new Date(r.timestamp) > new Date(occupy.timestamp)
          )
          
          if (release) {
            const duration = new Date(release.timestamp) - new Date(occupy.timestamp)
            totalHours += duration / (1000 * 60 * 60)
          }
        })
        
        userStats.value.total_usage_hours = Math.round(totalHours)
        
      } catch (error) {
        console.error('Failed to load recent activity:', error)
        ElMessage.error('加载活动记录失败')
      } finally {
        activityLoading.value = false
      }
    }
    
    const releaseDevice = async (deviceId) => {
      try {
        await deviceAPI.releaseDevice(deviceId)
        ElMessage.success('设备释放成功')
        loadOccupiedDevices()
        loadRecentActivity()
      } catch (error) {
        ElMessage.error(error.response?.data?.detail || '释放设备失败')
      }
    }
    
    const getRoleLabel = (role) => {
      const labels = {
        'admin': '管理员',
        'user': '普通用户'
      }
      return labels[role] || role
    }
    
    const getRoleTagType = (role) => {
      const types = {
        'admin': 'danger',
        'user': 'primary'
      }
      return types[role] || 'info'
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
        return `${hours}h${minutes}m`
      } else {
        return `${minutes}m`
      }
    }
    
    onMounted(() => {
      loadOccupiedDevices()
      loadRecentActivity()
      store.connectWebSocket()

      unsubscribeFromDeviceUpdates = store.onDeviceUpdate(() => {
        if (websocketRefreshTimeout) return
        websocketRefreshTimeout = setTimeout(() => {
          loadOccupiedDevices()
          loadRecentActivity()
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
      occupiedDevices,
      recentActivity,
      loading,
      activityLoading,
      userStats,
      avatarUrl,
      store,
      loadOccupiedDevices,
      loadRecentActivity,
      releaseDevice,
      getRoleLabel,
      getRoleTagType,
      getDeviceTypeLabel,
      getDeviceTypeTagType,
      formatTime,
      getUsageDuration,
      User,
      Refresh
    }
  }
}
</script>

<style scoped>
.user-profile {
  padding: 20px;
}

.page-header {
  margin-bottom: 30px;
}

.page-header h1 {
  margin: 0;
  color: #333;
}

.profile-card {
  background: white;
  border-radius: 8px;
  padding: 30px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  text-align: center;
}

.avatar-section {
  margin-bottom: 30px;
}

.avatar-section h3 {
  margin: 15px 0 10px 0;
  color: #333;
}

.user-info {
  text-align: left;
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid #f0f0f0;
}

.info-item:last-child {
  border-bottom: none;
}

.info-item label {
  font-weight: 600;
  color: #666;
}

.stats-card,
.occupied-devices-card,
.recent-activity-card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  margin-bottom: 20px;
}

.stats-card h3,
.occupied-devices-card h3,
.recent-activity-card h3 {
  margin: 0 0 20px 0;
  color: #333;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.card-header h3 {
  margin: 0;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}

.stat-item {
  text-align: center;
  padding: 20px;
  background: #f8f9fa;
  border-radius: 8px;
}

.stat-number {
  font-size: 32px;
  font-weight: bold;
  color: #409eff;
  margin-bottom: 5px;
}

.stat-label {
  color: #666;
  font-size: 14px;
}

.activity-item {
  margin-bottom: 10px;
}

.activity-action {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 5px;
}

.device-name {
  font-weight: 500;
}

.activity-notes {
  color: #666;
  font-size: 14px;
}

.empty-devices,
.empty-activity {
  text-align: center;
  padding: 40px 0;
}

@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>