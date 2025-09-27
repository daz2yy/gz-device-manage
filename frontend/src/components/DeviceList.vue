<template>
  <div class="device-list">
    <div class="page-header">
      <h1>设备管理</h1>
      <div class="header-actions">
        <el-button type="primary" @click="scanDevices" :loading="scanning">
          <el-icon><Refresh /></el-icon>
          {{ scanning ? '扫描中...' : '扫描设备' }}
        </el-button>
      </div>
    </div>
    
    <!-- Filters -->
    <div class="filters">
      <el-row :gutter="20">
        <el-col :span="6">
          <el-input
            v-model="filters.search"
            placeholder="搜索设备ID或名称"
            clearable
            @input="handleSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </el-col>
        <el-col :span="4">
          <el-input
            v-model="filters.model"
            placeholder="搜索设备型号"
            clearable
            @input="handleSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </el-col>
        <el-col :span="4">
          <el-select v-model="filters.device_type" placeholder="设备类型" clearable @change="loadDevices">
            <el-option label="全部" value="" />
            <el-option label="ADB" value="adb" />
            <el-option label="蓝牙" value="bluetooth" />
            <el-option label="Wi-Fi" value="wifi" />
            <el-option label="星闪" value="starflash" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-select v-model="filters.status" placeholder="设备状态" clearable @change="loadDevices">
            <el-option label="全部" value="" />
            <el-option label="在线" value="online" />
            <el-option label="离线" value="offline" />
            <el-option label="占用" value="occupied" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-select v-model="filters.group" placeholder="设备分组" clearable @change="loadDevices">
            <el-option label="全部" value="" />
            <el-option v-for="group in groups" :key="group" :label="group" :value="group" />
          </el-select>
        </el-col>
        <el-col :span="6">
          <el-button @click="resetFilters">重置筛选</el-button>
          <el-button type="primary" @click="showBatchDialog = true" :disabled="selectedDevices.length === 0">
            批量操作 ({{ selectedDevices.length }})
          </el-button>
        </el-col>
      </el-row>
      
      <!-- Filter Status Info -->
      <div v-if="filters.status === 'online'" class="filter-info">
        <el-icon><component :is="'SuccessFilled'" /></el-icon>
        <span>当前显示在线设备</span>
      </div>
    </div>
    
    <!-- Grouped Device Display -->
    <div v-loading="loading">
      <div v-for="group in groupedDevices" :key="group.adbDevice?.device_id || 'orphaned'" class="device-group">
        <!-- ADB Device Header -->
        <el-card v-if="group.adbDevice" class="adb-device-card" shadow="hover">
          <template #header>
            <div class="adb-device-header">
              <div class="device-info">
                <el-tag type="primary" size="large">
                  <el-icon><component :is="'Cellphone'" /></el-icon>
                  相机设备
                </el-tag>
                <h3 class="device-name">{{ group.adbDevice.name }}</h3>
                <span class="device-id">ID: {{ group.adbDevice.device_id }}</span>
                <span v-if="group.adbDevice.model" class="device-model">型号: {{ group.adbDevice.model }}</span>
                <el-tag :type="getStatusTagType(group.adbDevice.status)" class="status-tag">
                  {{ getStatusLabel(group.adbDevice.status) }}
                </el-tag>
              </div>
              
              <div class="device-actions">
                <el-button 
                  v-if="!group.adbDevice.occupied_by && group.adbDevice.status === 'online'"
                  type="primary" 
                  size="small"
                  @click="occupyDevice(group.adbDevice.device_id)"
                >
                  占用设备
                </el-button>
                <el-button 
                  v-else-if="group.adbDevice.occupied_by && (group.adbDevice.occupied_by === store.user?.id || store.user?.role === 'admin')"
                  type="warning" 
                  size="small"
                  @click="releaseDevice(group.adbDevice.device_id)"
                >
                  释放设备
                </el-button>
                <el-button 
                  type="info" 
                  size="small"
                  @click="$router.push(`/devices/${group.adbDevice.device_id}`)"
                >
                  查看详情
                </el-button>
              </div>
            </div>
          </template>
          
          <div class="adb-device-content">
            <!-- Bluetooth Status -->
            <div class="info-section">
              <h4><el-icon><component :is="'Connection'" /></el-icon> 蓝牙状态</h4>
              <div v-if="getAdbBluetoothInfo(group.adbDevice)" class="bluetooth-info">
                <div class="status-row">
                  <el-icon :class="getAdbBluetoothEnabledClass(group.adbDevice)">
                    <component :is="getAdbBluetoothEnabledIcon(group.adbDevice)" />
                  </el-icon>
                  <span class="status-text">
                    {{ getAdbBluetoothName(group.adbDevice) || '蓝牙控制器' }}
                  </span>
                </div>
                
                <div v-if="getAdbConnectedDevices(group.adbDevice).length > 0" class="status-row secondary">
                  <el-icon class="text-success">
                    <component :is="'Link'" />
                  </el-icon>
                  <span class="status-text small">
                    已连接 {{ getAdbConnectedDevices(group.adbDevice).length }} 个设备
                  </span>
                </div>
                
                <div v-else class="status-row secondary">
                  <el-icon class="text-muted">
                    <component :is="'Connection'" />
                  </el-icon>
                  <span class="status-text small">无连接设备</span>
                </div>
              </div>
              <div v-else class="status-row">
                <el-icon class="text-muted">
                  <component :is="'CloseBold'" />
                </el-icon>
                <span class="status-text small text-muted">蓝牙不可用</span>
              </div>
            </div>
            
            <!-- WiFi AP Status -->
            <div class="info-section">
              <h4><el-icon><component :is="'Promotion'" /></el-icon> WiFi AP 状态</h4>
              <div v-if="hasAdbWifiApConfig(group.adbDevice)" class="wifi-ap-info">
                <div class="status-row">
                  <el-icon class="text-success">
                    <component :is="'SuccessFilled'" />
                  </el-icon>
                  <span class="status-text">
                    {{ getAdbWifiApName(group.adbDevice) || 'WiFi AP' }}
                  </span>
                </div>
                <div v-if="getAdbWifiApPassword(group.adbDevice)" class="status-row secondary">
                  <el-icon class="text-primary">
                    <component :is="'CircleCheckFilled'" />
                  </el-icon>
                  <span class="status-text small">
                    密码: {{ getAdbWifiApPassword(group.adbDevice) }}
                  </span>
                </div>
              </div>
              <div v-else class="status-row">
                <el-icon class="text-muted">
                  <component :is="'CloseBold'" />
                </el-icon>
                <span class="status-text small text-muted">WiFi AP 未配置</span>
              </div>
            </div>
          </div>
        </el-card>
        
        <!-- Bluetooth Devices Table -->
        <div v-if="group.bluetoothDevices.length > 0" class="bluetooth-devices-section">
          <h4 class="section-title">
            <el-icon><component :is="'Connection'" /></el-icon>
            关联蓝牙设备 ({{ group.bluetoothDevices.length }})
          </h4>
          <el-table 
            :data="group.bluetoothDevices" 
            size="small"
            style="width: 100%"
          >
            <el-table-column prop="device_id" label="MAC地址" width="180">
              <template #default="{ row }">
                <el-button type="text" @click="$router.push(`/devices/${row.device_id}`)">
                  {{ row.device_id }}
                </el-button>
              </template>
            </el-table-column>
            
            <el-table-column prop="name" label="设备名称" />
            
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getStatusTagType(row.status)">
                  {{ getStatusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            
            <el-table-column label="连接状态" width="120">
              <template #default="{ row }">
                <div class="bluetooth-status">
                  <el-icon :class="getBluetoothConnectionClass(row)">
                    <component :is="getBluetoothConnectionIcon(row)" />
                  </el-icon>
                  <span class="status-text">
                    {{ getBluetoothConnectionText(row) }}
                  </span>
                </div>
              </template>
            </el-table-column>
            
            <el-table-column label="配对状态" width="120">
              <template #default="{ row }">
                <div v-if="getBluetoothPairingStatus(row)" class="bluetooth-pairing">
                  <el-icon :class="getBluetoothPairingClass(row)">
                    <component :is="getBluetoothPairingIcon(row)" />
                  </el-icon>
                  <span class="status-text small">
                    {{ getBluetoothPairingText(row) }}
                  </span>
                </div>
                <span v-else class="text-muted">-</span>
              </template>
            </el-table-column>
            
            <el-table-column label="操作" width="200">
              <template #default="{ row }">
                <div class="bluetooth-actions">
                  <el-button 
                    size="small" 
                    type="primary"
                    :loading="bluetoothLoading[row.device_id]"
                    @click="connectBluetooth(row.device_id)"
                  >
                    连接
                  </el-button>
                  <el-button 
                    size="small" 
                    type="warning"
                    :loading="bluetoothLoading[row.device_id]"
                    @click="disconnectBluetooth(row.device_id)"
                  >
                    断开
                  </el-button>
                  <el-button 
                    size="small" 
                    type="info"
                    :loading="bluetoothLoading[row.device_id]"
                    @click="pairBluetooth(row.device_id)"
                  >
                    配对
                  </el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
      
      <!-- Orphaned Bluetooth Devices -->
      <div v-if="groupedDevices.some(g => !g.adbDevice)" class="orphaned-devices-section">
        <h3 class="section-title">
          <el-icon><component :is="'QuestionFilled'" /></el-icon>
          未关联蓝牙设备
        </h3>
        <el-table 
          :data="groupedDevices.find(g => !g.adbDevice)?.bluetoothDevices || []" 
          size="small"
          style="width: 100%"
        >
          <!-- Same columns as above -->
          <el-table-column prop="device_id" label="MAC地址" width="180">
            <template #default="{ row }">
              <el-button type="text" @click="$router.push(`/devices/${row.device_id}`)">
                {{ row.device_id }}
              </el-button>
            </template>
          </el-table-column>
          
          <el-table-column prop="name" label="设备名称" />
          
          <el-table-column prop="status" label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="getStatusTagType(row.status)">
                {{ getStatusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          
          <el-table-column label="连接状态" width="120">
            <template #default="{ row }">
              <div class="bluetooth-status">
                <el-icon :class="getBluetoothConnectionClass(row)">
                  <component :is="getBluetoothConnectionIcon(row)" />
                </el-icon>
                <span class="status-text">
                  {{ getBluetoothConnectionText(row) }}
                </span>
              </div>
            </template>
          </el-table-column>
          
          <el-table-column label="配对状态" width="120">
            <template #default="{ row }">
              <div v-if="getBluetoothPairingStatus(row)" class="bluetooth-pairing">
                <el-icon :class="getBluetoothPairingClass(row)">
                  <component :is="getBluetoothPairingIcon(row)" />
                </el-icon>
                <span class="status-text small">
                  {{ getBluetoothPairingText(row) }}
                </span>
              </div>
              <span v-else class="text-muted">-</span>
            </template>
          </el-table-column>
          
          <el-table-column label="操作" width="200">
            <template #default="{ row }">
              <div class="bluetooth-actions">
                <el-button 
                  size="small" 
                  type="primary"
                  :loading="bluetoothLoading[row.device_id]"
                  @click="connectBluetooth(row.device_id)"
                >
                  连接
                </el-button>
                <el-button 
                  size="small" 
                  type="warning"
                  :loading="bluetoothLoading[row.device_id]"
                  @click="disconnectBluetooth(row.device_id)"
                >
                  断开
                </el-button>
                <el-button 
                  size="small" 
                  type="info"
                  :loading="bluetoothLoading[row.device_id]"
                  @click="pairBluetooth(row.device_id)"
                >
                  配对
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>


    
    <!-- Pagination -->
    <div class="pagination">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[10, 20, 50, 100]"
        :total="total"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadDevices"
        @current-change="loadDevices"
      />
    </div>
    
    <!-- Edit Device Dialog -->
    <el-dialog v-model="showEditDialog" title="编辑设备" width="600px">
      <el-form :model="editForm" label-width="80px">
        <el-form-item label="设备名称">
          <el-input v-model="editForm.name" />
        </el-form-item>
        <el-form-item label="设备分组">
          <el-select v-model="editForm.group_name" filterable allow-create style="width: 100%">
            <el-option v-for="group in groups" :key="group" :label="group" :value="group" />
          </el-select>
        </el-form-item>
        <el-form-item label="设备标签">
          <el-select 
            v-model="editForm.tags" 
            multiple 
            filterable 
            allow-create 
            style="width: 100%"
            placeholder="输入标签并回车添加"
          >
            <el-option v-for="tag in allTags" :key="tag" :label="tag" :value="tag" />
          </el-select>
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="showEditDialog = false">取消</el-button>
        <el-button type="primary" @click="saveDevice" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
    
    <!-- Batch Operations Dialog -->
    <el-dialog v-model="showBatchDialog" title="批量操作" width="400px">
      <div class="batch-operations">
        <p>已选择 {{ selectedDevices.length }} 个设备</p>
        
        <el-button 
          type="primary" 
          @click="batchOccupy"
          :disabled="!canBatchOccupy"
          style="width: 100%; margin-bottom: 10px;"
        >
          批量占用
        </el-button>
        
        <el-button 
          type="warning" 
          @click="batchRelease"
          :disabled="!canBatchRelease"
          style="width: 100%; margin-bottom: 10px;"
        >
          批量释放
        </el-button>
        
        <el-button 
          v-if="store.user?.role === 'admin'"
          type="info" 
          @click="showBatchEditForm = true"
          style="width: 100%;"
        >
          批量编辑
        </el-button>
      </div>
      
      <!-- Batch Edit Form -->
      <div v-if="showBatchEditForm" style="margin-top: 20px;">
        <el-divider>批量编辑</el-divider>
        <el-form :model="batchEditForm" label-width="80px">
          <el-form-item label="设备分组">
            <el-select v-model="batchEditForm.group_name" filterable allow-create style="width: 100%">
              <el-option label="不修改" value="" />
              <el-option v-for="group in groups" :key="group" :label="group" :value="group" />
            </el-select>
          </el-form-item>
          <el-form-item label="添加标签">
            <el-select 
              v-model="batchEditForm.add_tags" 
              multiple 
              filterable 
              allow-create 
              style="width: 100%"
            >
              <el-option v-for="tag in allTags" :key="tag" :label="tag" :value="tag" />
            </el-select>
          </el-form-item>
        </el-form>
        
        <el-button type="primary" @click="batchEdit" :loading="batchEditing" style="width: 100%;">
          应用批量编辑
        </el-button>
      </div>
      
      <template #footer>
        <el-button @click="closeBatchDialog">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  Refresh, 
  Search,
  SuccessFilled,
  WarningFilled,
  QuestionFilled,
  CircleCloseFilled,
  CircleCheckFilled,
  CirclePlusFilled,
  Promotion,
  SemiSelect,
  Remove,
  CloseBold,
  Minus,
  Link,
  Connection,
  Cellphone
} from '@element-plus/icons-vue'
import { deviceAPI } from '../api.js'
import { store } from '../store.js'

export default {
  name: 'DeviceList',
  setup() {
    const devices = ref([])
    const loading = ref(false)
    const scanning = ref(false)
    const saving = ref(false)
    const batchEditing = ref(false)
    const bluetoothLoading = ref({})
    
    const currentPage = ref(1)
    const pageSize = ref(20)
    const total = ref(0)
    
    const selectedDevices = ref([])
    const showEditDialog = ref(false)
    const showBatchDialog = ref(false)
    const showBatchEditForm = ref(false)
    
    const filters = reactive({
      search: '',
      model: '',
      device_type: '',
      status: 'online',  // 默认显示在线设备
      group: ''
    })
    
    const editForm = reactive({
      device_id: '',
      name: '',
      group_name: '',
      tags: []
    })
    
    const batchEditForm = reactive({
      group_name: '',
      add_tags: []
    })
    
    const groups = ref([])
    const allTags = ref([])
    
    let searchTimeout
    let websocketRefreshTimeout
    let unsubscribeFromDeviceUpdates
    
    const canBatchOccupy = computed(() => {
      return selectedDevices.value.some(device => 
        !device.occupied_by && device.status === 'online'
      )
    })
    
    const canBatchRelease = computed(() => {
      return selectedDevices.value.some(device => 
        device.occupied_by && (
          device.occupied_by === store.user?.id || 
          store.user?.role === 'admin'
        )
      )
    })
    
    const hasBluetoothCapableDevices = computed(() => {
      return devices.value.some(device => 
        device.device_type === 'bluetooth' || 
        (device.device_type === 'adb' && device.connection_info?.bluetooth_info)
      )
    })
    
    // Group devices by ADB host for better organization
    const groupedDevices = computed(() => {
      const groups = []
      const adbDevices = devices.value.filter(device => device.device_type === 'adb')
      const bluetoothDevices = devices.value.filter(device => device.device_type === 'bluetooth')
      
      // Create groups for each ADB device
      adbDevices.forEach(adbDevice => {
        const relatedBluetoothDevices = bluetoothDevices.filter(btDevice => 
          btDevice.connection_info?.adb_host === adbDevice.device_id
        )
        
        groups.push({
          adbDevice: adbDevice,
          bluetoothDevices: relatedBluetoothDevices,
          allDevices: [adbDevice, ...relatedBluetoothDevices]
        })
      })
      
      // Add orphaned Bluetooth devices (without ADB host)
      const orphanedBluetoothDevices = bluetoothDevices.filter(btDevice => 
        !btDevice.connection_info?.adb_host || 
        !adbDevices.some(adb => adb.device_id === btDevice.connection_info.adb_host)
      )
      
      if (orphanedBluetoothDevices.length > 0) {
        groups.push({
          adbDevice: null,
          bluetoothDevices: orphanedBluetoothDevices,
          allDevices: orphanedBluetoothDevices
        })
      }
      
      return groups
    })
    
    const loadDevices = async () => {
      loading.value = true
      try {
        const params = {
          skip: (currentPage.value - 1) * pageSize.value,
          limit: pageSize.value,
          ...filters
        }
        
        // Remove empty filters
        Object.keys(params).forEach(key => {
          if (params[key] === '' || params[key] === null || params[key] === undefined) {
            delete params[key]
          }
        })
        
        const response = await deviceAPI.getDevices(params)
        devices.value = response.data
        
        // Fetch Bluetooth and WiFi AP info for ADB devices
        const adbDevices = response.data.filter(device => device.device_type === 'adb')
        if (adbDevices.length > 0) {
          const infoPromises = adbDevices.map(async (device) => {
            try {
              // Get both Bluetooth and WiFi AP info
              const [bluetoothResponse, wifiApResponse] = await Promise.allSettled([
                deviceAPI.getBluetoothInfo(device.device_id),
                deviceAPI.getWifiApInfo(device.device_id)
              ])
              
              // Update device with info
              const deviceIndex = devices.value.findIndex(d => d.device_id === device.device_id)
              if (deviceIndex !== -1) {
                if (!devices.value[deviceIndex].connection_info) {
                  devices.value[deviceIndex].connection_info = {}
                }
                
                if (bluetoothResponse.status === 'fulfilled') {
                  devices.value[deviceIndex].connection_info.bluetooth_info = bluetoothResponse.value.data.bluetooth_info
                }
                
                if (wifiApResponse.status === 'fulfilled') {
                  devices.value[deviceIndex].connection_info.wifi_ap_info = wifiApResponse.value.data.wifi_ap_info
                }
              }
            } catch (error) {
              console.warn(`Failed to get device info for ${device.device_id}:`, error)
            }
          })
          
          // Wait for all info requests to complete
          await Promise.allSettled(infoPromises)
        }
        
        // Extract groups and tags for filters
        const groupSet = new Set()
        const tagSet = new Set()
        
        response.data.forEach(device => {
          if (device.group_name) groupSet.add(device.group_name)
          if (device.tags) device.tags.forEach(tag => tagSet.add(tag))
        })
        
        groups.value = Array.from(groupSet)
        allTags.value = Array.from(tagSet)
        
        // For pagination, we need to get total count
        // This is a simplified approach - in real app, API should return total
        total.value = response.data.length
        
      } catch (error) {
        console.error('Failed to load devices:', error)
        ElMessage.error('加载设备列表失败')
      } finally {
        loading.value = false
      }
    }
    
    const handleSearch = () => {
      clearTimeout(searchTimeout)
      searchTimeout = setTimeout(() => {
        currentPage.value = 1
        loadDevices()
      }, 500)
    }
    
    const resetFilters = () => {
      Object.assign(filters, {
        search: '',
        model: '',
        device_type: '',
        status: 'online',  // 重置时也默认显示在线设备
        group: ''
      })
      currentPage.value = 1
      loadDevices()
    }
    
    const scanDevices = async () => {
      scanning.value = true
      try {
        await deviceAPI.scanDevices()
        ElMessage.success('设备扫描完成')
        loadDevices()
      } catch (error) {
        ElMessage.error('设备扫描失败')
      } finally {
        scanning.value = false
      }
    }
    
    const occupyDevice = async (deviceId) => {
      try {
        await deviceAPI.occupyDevice(deviceId, '从设备列表占用')
        ElMessage.success('设备占用成功')
        loadDevices()
      } catch (error) {
        ElMessage.error(error.response?.data?.detail || '占用设备失败')
      }
    }
    
    const releaseDevice = async (deviceId) => {
      try {
        await deviceAPI.releaseDevice(deviceId)
        ElMessage.success('设备释放成功')
        loadDevices()
      } catch (error) {
        ElMessage.error(error.response?.data?.detail || '释放设备失败')
      }
    }
    
    const editDevice = (device) => {
      Object.assign(editForm, {
        device_id: device.device_id,
        name: device.name,
        group_name: device.group_name || '',
        tags: device.tags || []
      })
      showEditDialog.value = true
    }
    
    const saveDevice = async () => {
      saving.value = true
      try {
        await deviceAPI.updateDevice(editForm.device_id, {
          name: editForm.name,
          group_name: editForm.group_name,
          tags: editForm.tags
        })
        ElMessage.success('设备更新成功')
        showEditDialog.value = false
        loadDevices()
      } catch (error) {
        ElMessage.error('设备更新失败')
      } finally {
        saving.value = false
      }
    }
    
    const handleSelectionChange = (selection) => {
      selectedDevices.value = selection
    }
    
    const batchOccupy = async () => {
      const occupyableDevices = selectedDevices.value.filter(device => 
        !device.occupied_by && device.status === 'online'
      )
      
      if (occupyableDevices.length === 0) {
        ElMessage.warning('没有可占用的设备')
        return
      }
      
      try {
        await ElMessageBox.confirm(
          `确定要占用 ${occupyableDevices.length} 个设备吗？`,
          '批量占用确认',
          { type: 'warning' }
        )
        
        const promises = occupyableDevices.map(device => 
          deviceAPI.occupyDevice(device.device_id, '批量占用')
        )
        
        await Promise.all(promises)
        ElMessage.success(`成功占用 ${occupyableDevices.length} 个设备`)
        closeBatchDialog()
        loadDevices()
        
      } catch (error) {
        if (error !== 'cancel') {
          ElMessage.error('批量占用失败')
        }
      }
    }
    
    const batchRelease = async () => {
      const releasableDevices = selectedDevices.value.filter(device => 
        device.occupied_by && (
          device.occupied_by === store.user?.id || 
          store.user?.role === 'admin'
        )
      )
      
      if (releasableDevices.length === 0) {
        ElMessage.warning('没有可释放的设备')
        return
      }
      
      try {
        await ElMessageBox.confirm(
          `确定要释放 ${releasableDevices.length} 个设备吗？`,
          '批量释放确认',
          { type: 'warning' }
        )
        
        const promises = releasableDevices.map(device => 
          deviceAPI.releaseDevice(device.device_id)
        )
        
        await Promise.all(promises)
        ElMessage.success(`成功释放 ${releasableDevices.length} 个设备`)
        closeBatchDialog()
        loadDevices()
        
      } catch (error) {
        if (error !== 'cancel') {
          ElMessage.error('批量释放失败')
        }
      }
    }
    
    const batchEdit = async () => {
      if (!batchEditForm.group_name && batchEditForm.add_tags.length === 0) {
        ElMessage.warning('请至少选择一项要修改的内容')
        return
      }
      
      batchEditing.value = true
      try {
        const promises = selectedDevices.value.map(device => {
          const updateData = {}
          
          if (batchEditForm.group_name) {
            updateData.group_name = batchEditForm.group_name
          }
          
          if (batchEditForm.add_tags.length > 0) {
            const existingTags = device.tags || []
            const newTags = [...new Set([...existingTags, ...batchEditForm.add_tags])]
            updateData.tags = newTags
          }
          
          return deviceAPI.updateDevice(device.device_id, updateData)
        })
        
        await Promise.all(promises)
        ElMessage.success(`成功编辑 ${selectedDevices.value.length} 个设备`)
        closeBatchDialog()
        loadDevices()
        
      } catch (error) {
        ElMessage.error('批量编辑失败')
      } finally {
        batchEditing.value = false
      }
    }
    
    const closeBatchDialog = () => {
      showBatchDialog.value = false
      showBatchEditForm.value = false
      Object.assign(batchEditForm, {
        group_name: '',
        add_tags: []
      })
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
    
    // Bluetooth status helper methods
    const getBluetoothInfo = (device) => {
      if (device.device_type !== 'bluetooth' || !device.connection_info) {
        return null
      }
      return device.connection_info.bluetooth_info || {}
    }
    
    const getBluetoothConnectionText = (device) => {
      const info = getBluetoothInfo(device)
      if (!info) return '-'
      
      if (info.connected === true) return '已连接'
      if (info.connected === false) return '未连接'
      return '未知'
    }
    
    const getBluetoothConnectionClass = (device) => {
      const info = getBluetoothInfo(device)
      if (!info) return 'text-muted'
      
      if (info.connected === true) return 'text-success'
      if (info.connected === false) return 'text-warning'
      return 'text-muted'
    }
    
    const getBluetoothConnectionIcon = (device) => {
      const info = getBluetoothInfo(device)
      if (!info) return 'QuestionFilled'
      
      if (info.connected === true) return 'SuccessFilled'
      if (info.connected === false) return 'WarningFilled'
      return 'QuestionFilled'
    }
    
    const getBluetoothPairingStatus = (device) => {
      const info = getBluetoothInfo(device)
      return info && (info.paired !== undefined || info.trusted !== undefined)
    }
    
    const getBluetoothPairingText = (device) => {
      const info = getBluetoothInfo(device)
      if (!info) return ''
      
      const status = []
      if (info.paired === true) status.push('已配对')
      if (info.trusted === true) status.push('已信任')
      if (info.blocked === true) status.push('已阻止')
      
      return status.length > 0 ? status.join(', ') : ''
    }
    
    const getBluetoothPairingClass = (device) => {
      const info = getBluetoothInfo(device)
      if (!info) return 'text-muted'
      
      if (info.blocked === true) return 'text-danger'
      if (info.paired === true && info.trusted === true) return 'text-success'
      if (info.paired === true) return 'text-primary'
      return 'text-muted'
    }
    
    const getBluetoothPairingIcon = (device) => {
      const info = getBluetoothInfo(device)
      if (!info) return 'QuestionFilled'
      
      if (info.blocked === true) return 'CircleCloseFilled'
      if (info.paired === true && info.trusted === true) return 'CircleCheckFilled'
      if (info.paired === true) return 'CirclePlusFilled'
      return 'QuestionFilled'
    }
    
    const getBluetoothRSSI = (device) => {
      const info = getBluetoothInfo(device)
      return info && info.rssi ? info.rssi : null
    }
    
    const getSignalIcon = (device) => {
      const rssi = getBluetoothRSSI(device)
      if (!rssi) return 'Minus'
      
      // RSSI signal strength classification
      if (rssi >= -50) return 'Promotion'  // Excellent
      if (rssi >= -70) return 'SemiSelect' // Good
      if (rssi >= -85) return 'Remove'     // Fair
      return 'CloseBold'                   // Poor
    }
    
    // Bluetooth operation methods
    const connectBluetooth = async (deviceId) => {
      bluetoothLoading.value[deviceId] = true
      try {
        const response = await deviceAPI.bluetoothConnect(deviceId)
        ElMessage.success('蓝牙连接命令已发送')
        
        // Refresh devices after a short delay to see updated status
        setTimeout(() => {
          loadDevices()
        }, 2000)
        
      } catch (error) {
        ElMessage.error(error.response?.data?.detail || '蓝牙连接失败')
      } finally {
        bluetoothLoading.value[deviceId] = false
      }
    }
    
    const disconnectBluetooth = async (deviceId) => {
      bluetoothLoading.value[deviceId] = true
      try {
        const response = await deviceAPI.bluetoothDisconnect(deviceId)
        ElMessage.success('蓝牙断开命令已发送')
        
        // Refresh devices after a short delay to see updated status
        setTimeout(() => {
          loadDevices()
        }, 2000)
        
      } catch (error) {
        ElMessage.error(error.response?.data?.detail || '蓝牙断开失败')
      } finally {
        bluetoothLoading.value[deviceId] = false
      }
    }
    
    const pairBluetooth = async (deviceId) => {
      bluetoothLoading.value[deviceId] = true
      try {
        const response = await deviceAPI.bluetoothPair(deviceId)
        ElMessage.success('蓝牙配对命令已发送')
        
        // Refresh devices after a short delay to see updated status
        setTimeout(() => {
          loadDevices()
        }, 3000)
        
      } catch (error) {
        ElMessage.error(error.response?.data?.detail || '蓝牙配对失败')
      } finally {
        bluetoothLoading.value[deviceId] = false
      }
    }
    
    // ADB Bluetooth helper methods
    const getAdbBluetoothInfo = (device) => {
      if (device.device_type !== 'adb' || !device.connection_info) {
        return null
      }
      return device.connection_info.bluetooth_info || null
    }
    
    const getAdbBluetoothName = (device) => {
      const info = getAdbBluetoothInfo(device)
      return info?.bluetooth_name || null
    }
    
    const getAdbBluetoothEnabledClass = (device) => {
      const info = getAdbBluetoothInfo(device)
      if (!info) return 'text-muted'
      
      return info.bluetooth_enabled ? 'text-success' : 'text-warning'
    }
    
    const getAdbBluetoothEnabledIcon = (device) => {
      const info = getAdbBluetoothInfo(device)
      if (!info) return 'QuestionFilled'
      
      return info.bluetooth_enabled ? 'SuccessFilled' : 'WarningFilled'
    }
    
    const getAdbConnectedDevices = (device) => {
      const info = getAdbBluetoothInfo(device)
      return info?.connected_devices || []
    }
    
    // ADB WiFi AP helper methods
    const getAdbWifiApInfo = (device) => {
      if (device.device_type !== 'adb' || !device.connection_info) {
        return null
      }
      return device.connection_info.wifi_ap_info || null
    }
    
    const getAdbWifiApName = (device) => {
      const info = getAdbWifiApInfo(device)
      return info?.ap_name || null
    }
    
    const getAdbWifiApPassword = (device) => {
      const info = getAdbWifiApInfo(device)
      return info?.ap_password || null
    }
    
    const hasAdbWifiApConfig = (device) => {
      const info = getAdbWifiApInfo(device)
      return info?.config_found || false
    }
    
    // Auto refresh
    let refreshInterval
    
    onMounted(() => {
      loadDevices()

      // Ensure WebSocket connection is active
      store.connectWebSocket()

      unsubscribeFromDeviceUpdates = store.onDeviceUpdate(() => {
        if (websocketRefreshTimeout) return
        websocketRefreshTimeout = setTimeout(() => {
          loadDevices()
          websocketRefreshTimeout = null
        }, 500)
      })

      // Auto refresh every 30 seconds as a fallback
      refreshInterval = setInterval(loadDevices, 30000)
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
      if (searchTimeout) {
        clearTimeout(searchTimeout)
      }
    })
    
    return {
      devices,
      loading,
      scanning,
      saving,
      batchEditing,
      currentPage,
      pageSize,
      total,
      selectedDevices,
      showEditDialog,
      showBatchDialog,
      showBatchEditForm,
      filters,
      editForm,
      batchEditForm,
      groups,
      allTags,
      canBatchOccupy,
      canBatchRelease,
      hasBluetoothCapableDevices,
      groupedDevices,
      store,
      loadDevices,
      handleSearch,
      resetFilters,
      scanDevices,
      occupyDevice,
      releaseDevice,
      editDevice,
      saveDevice,
      handleSelectionChange,
      batchOccupy,
      batchRelease,
      batchEdit,
      closeBatchDialog,
      getDeviceTypeLabel,
      getDeviceTypeTagType,
      getStatusLabel,
      getStatusTagType,
      formatTime,
      getBluetoothInfo,
      getBluetoothConnectionText,
      getBluetoothConnectionClass,
      getBluetoothConnectionIcon,
      getBluetoothPairingStatus,
      getBluetoothPairingText,
      getBluetoothPairingClass,
      getBluetoothPairingIcon,
      getBluetoothRSSI,
      getSignalIcon,
      bluetoothLoading,
      connectBluetooth,
      disconnectBluetooth,
      pairBluetooth,
      getAdbBluetoothInfo,
      getAdbBluetoothName,
      getAdbBluetoothEnabledClass,
      getAdbBluetoothEnabledIcon,
      getAdbConnectedDevices,
      getAdbWifiApInfo,
      getAdbWifiApName,
      getAdbWifiApPassword,
      hasAdbWifiApConfig,
      Refresh,
      Search,
      SuccessFilled,
      WarningFilled,
      QuestionFilled,
      CircleCloseFilled,
      CircleCheckFilled,
      CirclePlusFilled,
      Promotion,
      SemiSelect,
      Remove,
      CloseBold,
      Minus,
      Link,
      Connection,
      Cellphone
    }
  }
}
</script>

<style scoped>
.device-list {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h1 {
  margin: 0;
  color: #333;
}

.filters {
  background: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  margin-bottom: 20px;
}

.filter-info {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
  padding: 8px 12px;
  background: #f0f9ff;
  border: 1px solid #67c23a;
  border-radius: 4px;
  color: #67c23a;
  font-size: 12px;
}

.pagination {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}

.text-muted {
  color: #999;
}

.batch-operations p {
  margin-bottom: 15px;
  color: #666;
}

/* Bluetooth Status Styles */
.bluetooth-status {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.status-row {
  display: flex;
  align-items: center;
  font-size: 12px;
  line-height: 1.2;
}

.status-row.secondary {
  opacity: 0.8;
}

.status-text {
  font-size: 12px;
}

.status-text.small {
  font-size: 11px;
}

.text-success {
  color: #67c23a;
}

.text-warning {
  color: #e6a23c;
}

.text-danger {
  color: #f56c6c;
}

.text-primary {
  color: #409eff;
}

.signal-icon {
  font-size: 10px;
}

/* Action buttons layout */
.action-buttons {
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: flex-start;
}

.button-group {
  display: flex;
  gap: 4px;
  align-items: center;
  flex-wrap: wrap;
}

.bluetooth-controls {
  border-left: 2px solid #e4e7ed;
  padding-left: 8px;
}

/* Tags container to prevent collapsing */
.tags-container {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  min-height: 24px;
  align-items: center;
}

.tag-item {
  margin: 0;
  flex-shrink: 0;
}

/* Device Group Styles */
.device-group {
  margin-bottom: 30px;
}

.adb-device-card {
  margin-bottom: 15px;
}

.adb-device-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.device-info {
  display: flex;
  align-items: center;
  gap: 15px;
}

.device-name {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #333;
}

.device-id {
  font-size: 12px;
  color: #666;
  background: #f5f7fa;
  padding: 2px 8px;
  border-radius: 4px;
}

.device-model {
  font-size: 12px;
  color: #909399;
}

.status-tag {
  margin-left: auto;
}

.device-actions {
  display: flex;
  gap: 8px;
}

.adb-device-content {
  display: flex;
  gap: 30px;
  margin-top: 15px;
}

.info-section {
  flex: 1;
}

.info-section h4 {
  margin: 0 0 10px 0;
  font-size: 14px;
  font-weight: 600;
  color: #333;
  display: flex;
  align-items: center;
  gap: 6px;
}

.bluetooth-info,
.wifi-ap-info {
  background: #f8f9fa;
  padding: 10px;
  border-radius: 6px;
  border-left: 3px solid #409eff;
}

.bluetooth-devices-section {
  margin-top: 15px;
}

.section-title {
  margin: 0 0 10px 0;
  font-size: 16px;
  font-weight: 600;
  color: #333;
  display: flex;
  align-items: center;
  gap: 8px;
}

.orphaned-devices-section {
  margin-top: 30px;
  padding-top: 20px;
  border-top: 2px dashed #e4e7ed;
}

.bluetooth-actions {
  display: flex;
  gap: 4px;
}

.bluetooth-pairing {
  display: flex;
  align-items: center;
  gap: 4px;
}
</style>
