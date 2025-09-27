import { createRouter, createWebHistory } from 'vue-router'
import { store } from './store.js'

// Import components
import Login from './components/Login.vue'
import Dashboard from './components/Dashboard.vue'
import DeviceList from './components/DeviceList.vue'
import DeviceDetail from './components/DeviceDetail.vue'
import DeviceTerminal from './components/DeviceTerminal.vue'
import UserProfile from './components/UserProfile.vue'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { requiresGuest: true }
  },
  {
    path: '/',
    redirect: '/devices'
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: Dashboard,
    meta: { requiresAuth: true }
  },
  {
    path: '/devices',
    name: 'DeviceList',
    component: DeviceList,
    meta: { requiresAuth: true }
  },
  {
    path: '/devices/:deviceId',
    name: 'DeviceDetail',
    component: DeviceDetail,
    meta: { requiresAuth: true }
  },
  {
    path: '/devices/:deviceId/terminal',
    name: 'DeviceTerminal',
    component: DeviceTerminal,
    meta: { requiresAuth: true }
  },
  {
    path: '/profile',
    name: 'UserProfile',
    component: UserProfile,
    meta: { requiresAuth: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Navigation guards
router.beforeEach((to, from, next) => {
  const isAuthenticated = !!store.token
  
  if (to.meta.requiresAuth && !isAuthenticated) {
    next('/login')
  } else if (to.meta.requiresGuest && isAuthenticated) {
    next('/devices')
  } else {
    next()
  }
})

export default router
