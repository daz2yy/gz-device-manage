<template>
  <div id="app">
    <!-- Login page -->
    <router-view v-if="$route.name === 'Login'" />
    
    <!-- Main layout -->
    <el-container v-else class="main-layout">
      <!-- Header -->
      <el-header class="main-header">
        <div class="header-left">
          <h1 class="logo">设备管理系统</h1>
          <el-menu
            :default-active="$route.path"
            mode="horizontal"
            router
            class="main-nav"
            :ellipsis="false"
          >
            <el-menu-item index="/dashboard">
              <el-icon><Monitor /></el-icon>
              <span>仪表盘</span>
            </el-menu-item>
            <el-menu-item index="/devices">
              <el-icon><List /></el-icon>
              <span>设备列表</span>
            </el-menu-item>
          </el-menu>
        </div>
        
        <div class="header-right">
          <!-- Connection status -->
          <div class="connection-status">
            <el-tooltip :content="wsConnected ? 'WebSocket已连接' : 'WebSocket未连接'">
              <el-icon :class="{ connected: wsConnected, disconnected: !wsConnected }">
                <Connection />
              </el-icon>
            </el-tooltip>
          </div>
          
          <!-- User menu -->
          <el-dropdown @command="handleUserCommand">
            <div class="user-info">
              <el-avatar :size="32" :src="avatarUrl">
                <el-icon><User /></el-icon>
              </el-avatar>
              <span class="username">{{ store.user?.username }}</span>
              <el-icon><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">
                  <el-icon><User /></el-icon>
                  个人资料
                </el-dropdown-item>
                <el-dropdown-item divided command="logout">
                  <el-icon><SwitchButton /></el-icon>
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      
      <!-- Main content -->
      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
    
    <!-- Global loading -->
    <el-loading
      v-loading="store.loading"
      element-loading-text="加载中..."
      element-loading-background="rgba(0, 0, 0, 0.8)"
    />
  </div>
</template>

<script>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { 
  Monitor, 
  List, 
  User, 
  ArrowDown, 
  SwitchButton, 
  Connection 
} from '@element-plus/icons-vue'
import { store } from './store.js'
import { authAPI } from './api.js'

export default {
  name: 'App',
  setup() {
    const router = useRouter()
    const wsConnected = ref(false)
    
    const avatarUrl = computed(() => {
      const username = store.user?.username || 'user'
      return `https://api.dicebear.com/7.x/initials/svg?seed=${username}`
    })
    
    const handleUserCommand = (command) => {
      switch (command) {
        case 'profile':
          router.push('/profile')
          break
        case 'logout':
          logout()
          break
      }
    }
    
    const logout = () => {
      store.clearAuth()
      store.disconnectWebSocket()
      router.push('/login')
      ElMessage.success('已退出登录')
    }

    const initializeAuth = async () => {
      if (store.token) {
        try {
          // Verify token by getting user info
          const response = await authAPI.getMe()
          store.setAuth(store.token, response.data)
          
          // Connect WebSocket
          store.connectWebSocket()
          
        } catch (error) {
          // Token is invalid, clear auth
          store.clearAuth()
          if (router.currentRoute.value.path !== '/login') {
            router.push('/login')
          }
        }
      }
    }
    
    // Monitor WebSocket connection
    const checkWebSocketConnection = () => {
      wsConnected.value = store.ws && store.ws.readyState === WebSocket.OPEN
    }
    
    let wsCheckInterval
    
    onMounted(() => {
      initializeAuth()
      
      // Check WebSocket connection every 5 seconds
      wsCheckInterval = setInterval(checkWebSocketConnection, 5000)
    })
    
    onUnmounted(() => {
      if (wsCheckInterval) {
        clearInterval(wsCheckInterval)
      }
    })
    
    return {
      store,
      avatarUrl,
      wsConnected,
      handleUserCommand,
      logout,
      Monitor,
      List,
      User,
      ArrowDown,
      SwitchButton,
      Connection
    }
  }
}
</script>

<style>
/* Global styles */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  background-color: #f5f7fa;
}

#app {
  min-height: 100vh;
}

.main-layout {
  min-height: 100vh;
}

.main-header {
  background: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 40px;
}

.logo {
  margin: 0;
  color: #409eff;
  font-size: 20px;
  font-weight: 600;
}

.main-nav {
  border-bottom: none;
}

.main-nav .el-menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 20px;
}

.connection-status .el-icon {
  font-size: 18px;
  cursor: pointer;
}

.connection-status .connected {
  color: #67c23a;
}

.connection-status .disconnected {
  color: #f56c6c;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 8px;
  border-radius: 4px;
  transition: background-color 0.3s;
}

.user-info:hover {
  background-color: #f5f7fa;
}

.username {
  font-weight: 500;
  color: #333;
}

.main-content {
  background-color: #f5f7fa;
  min-height: calc(100vh - 60px);
}

/* Element Plus customization */
.el-header {
  height: 60px !important;
  line-height: 60px;
}

.el-main {
  padding: 0;
}

/* Responsive */
@media (max-width: 768px) {
  .header-left {
    gap: 20px;
  }
  
  .logo {
    font-size: 16px;
  }
  
  .username {
    display: none;
  }
}
</style>
