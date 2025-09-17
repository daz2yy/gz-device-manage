import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import zhCn from 'element-plus/es/locale/lang/zh-cn'

import App from './App_enhanced.vue'
import router from './router.js'
import './style.css'

const app = createApp(App)

// Register Element Plus
app.use(ElementPlus, {
  locale: zhCn,
})

// Register all icons
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

// Register router
app.use(router)

app.mount('#app')