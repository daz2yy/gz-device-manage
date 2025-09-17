<template>
  <div class="page">
    <header class="page-header">
      <h1>设备管理</h1>
      <div class="actions">
        <button @click="fetchAll" :disabled="loading">{{ loading ? '加载中…' : '刷新全部' }}</button>
      </div>
    </header>

    <section class="section">
      <h2>ADB 设备</h2>
      <div class="chips">
        <span v-if="adbDevices.length === 0 && !loading" class="muted">暂无设备</span>
        <span v-for="id in adbDevices" :key="id" class="chip">{{ id }}</span>
      </div>
    </section>

    <section class="section">
      <div class="section-header">
        <h2>蓝牙连接信息（bluetoothctl info）</h2>
        <small class="muted">支持多设备展示 · 结构化字段</small>
      </div>

      <div v-if="error" class="error">{{ error }}</div>

      <!-- Skeleton loader -->
      <div v-if="loading" class="cards">
        <div v-for="n in 3" :key="n" class="card skeleton">
          <div class="skeleton-line w-60"></div>
          <div class="skeleton-line w-40"></div>
          <div class="skeleton-line w-100"></div>
          <div class="skeleton-line w-80"></div>
          <div class="skeleton-line w-70"></div>
        </div>
      </div>

      <div v-else class="cards">
        <div v-for="adbDevice in btInfos" :key="adbDevice.device_id" class="card">
          <div class="card-header">
            <div>
              <div class="title">ADB 设备：{{ adbDevice.device_id || '默认（未指定）' }}</div>
              <div class="subtitle muted">
                <span v-if="adbDevice.error">查询失败</span>
                <span v-else-if="adbDevice.message">{{ adbDevice.message }}</span>
                <span v-else>找到 {{ adbDevice.bluetooth_devices?.length || 0 }} 个蓝牙设备</span>
              </div>
            </div>
            <div class="header-actions">
              <button class="btn secondary" @click="refreshOne(adbDevice.device_id)" :disabled="loadingOne[adbDevice.device_id]">{{ loadingOne[adbDevice.device_id] ? '刷新中…' : '刷新' }}</button>
            </div>
          </div>

          <div v-if="adbDevice.error" class="error small">{{ adbDevice.error }}</div>
          
          <!-- 蓝牙设备列表 -->
          <div v-if="adbDevice.bluetooth_devices && adbDevice.bluetooth_devices.length > 0" class="bluetooth-devices">
            <div v-for="btDevice in adbDevice.bluetooth_devices" :key="btDevice.mac" class="bluetooth-device">
              <div class="bt-header">
                <div class="bt-title">{{ btDevice.name || btDevice.mac }}</div>
                <div class="status" :class="{ ok: btDevice.parsed?.connected, warn: !btDevice.parsed?.connected }">
                  <span v-if="btDevice.error">查询失败</span>
                  <span v-else>{{ btDevice.parsed?.connected ? '已连接' : '未连接/未知' }}</span>
                </div>
                <button class="btn ghost small" @click="toggleRaw(adbDevice.device_id + '_' + btDevice.mac)">{{ showRaw[adbDevice.device_id + '_' + btDevice.mac] ? '收起原始' : '展开原始' }}</button>
              </div>
              
              <div v-if="btDevice.error" class="error small">{{ btDevice.error }}</div>
              
              <div v-else class="grid">
                <div class="grid-item">
                  <label>MAC 地址</label>
                  <div class="value">{{ btDevice.mac }}</div>
                </div>
                <div class="grid-item">
                  <label>名称</label>
                  <div class="value">{{ btDevice.parsed?.name || '-' }}</div>
                </div>
                <div class="grid-item">
                  <label>别名</label>
                  <div class="value">{{ btDevice.parsed?.alias || '-' }}</div>
                </div>
                <div class="grid-item">
                  <label>配对</label>
                  <div class="value">{{ boolText(btDevice.parsed?.paired) }}</div>
                </div>
                <div class="grid-item">
                  <label>信任</label>
                  <div class="value">{{ boolText(btDevice.parsed?.trusted) }}</div>
                </div>
                <div class="grid-item">
                  <label>阻止</label>
                  <div class="value">{{ boolText(btDevice.parsed?.blocked) }}</div>
                </div>
                <div class="grid-item">
                  <label>RSSI</label>
                  <div class="value">{{ btDevice.parsed?.rssi ?? '-' }}</div>
                </div>
                <div class="grid-item">
                  <label>Tx Power</label>
                  <div class="value">{{ btDevice.parsed?.tx_power ?? '-' }}</div>
                </div>
                <div class="grid-item">
                  <label>Services Resolved</label>
                  <div class="value">{{ boolText(btDevice.parsed?.services_resolved) }}</div>
                </div>
                <div class="grid-item wide">
                  <label>UUIDs</label>
                  <div class="tags">
                    <span v-if="!btDevice.parsed?.uuids || btDevice.parsed.uuids.length === 0" class="muted">-</span>
                    <span v-for="u in (btDevice.parsed?.uuids || [])" :key="u.uuid" class="tag" :title="u.desc || u.uuid">{{ u.desc || u.uuid }}</span>
                  </div>
                </div>
              </div>

              <transition name="fade">
                <pre v-if="showRaw[adbDevice.device_id + '_' + btDevice.mac]" class="output">{{ btDevice.output }}</pre>
              </transition>
            </div>
          </div>
        </div>
      </div>

      <div v-if="!loading && btInfos.length === 0" class="empty">
        <div class="illustration">🛰️</div>
        <div class="muted">暂无蓝牙信息，请连接设备并点击“刷新全部”。</div>
      </div>
    </section>
  </div>
</template>

<script>
export default {
  data() {
    return {
      adbDevices: [],
      btInfos: [],
      loading: false,
      loadingOne: {},
      showRaw: {},
      error: ''
    };
  },
  methods: {
    boolText(v) {
      if (v === true) return '是';
      if (v === false) return '否';
      return '-';
    },
    async fetchAll() {
      this.loading = true;
      this.error = '';
      try {
        const adbResponse = await fetch('/api/devices');
        const adbData = await adbResponse.json();
        this.adbDevices = Array.isArray(adbData.devices) ? adbData.devices : [];

        const infosResp = await fetch('/api/bluetooth/infos');
        const infosData = await infosResp.json();
        this.btInfos = Array.isArray(infosData.results) ? infosData.results : [];

        // 初始化 showRaw 与 loadingOne
        const map = {};
        const map2 = {};
        for (const adbDevice of this.btInfos) {
          map2[adbDevice.device_id] = false;
          if (adbDevice.bluetooth_devices) {
            for (const btDevice of adbDevice.bluetooth_devices) {
              map[adbDevice.device_id + '_' + btDevice.mac] = false;
            }
          }
        }
        this.showRaw = map;
        this.loadingOne = map2;
      } catch (err) {
        console.error('获取信息失败:', err);
        this.error = '获取信息失败，请检查后端服务是否运行以及ADB是否可用。';
      } finally {
        this.loading = false;
      }
    },
    async refreshOne(deviceId) {
      if (!deviceId) return; // 仅对有明确设备ID的卡片提供单独刷新
      this.$set(this.loadingOne, deviceId, true);
      try {
        const resp = await fetch(`/api/bluetooth/info?device_id=${encodeURIComponent(deviceId)}`);
        const data = await resp.json();
        const idx = this.btInfos.findIndex(x => x.device_id === deviceId);
        if (idx !== -1) {
          this.$set(this.btInfos, idx, data);
        }
      } catch (e) {
        console.error('单设备刷新失败', e);
      } finally {
        this.$set(this.loadingOne, deviceId, false);
      }
    },
    toggleRaw(deviceId) {
      const current = !!this.showRaw[deviceId];
      this.$set(this.showRaw, deviceId, !current);
    }
  },
  mounted() {
    this.fetchAll();
  }
};
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 24px;
}
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.actions button { min-width: 120px; }
.section { text-align: left; }
.section-header { display: flex; align-items: baseline; gap: 12px; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip { padding: 4px 10px; border-radius: 999px; background: rgba(99, 102, 241, 0.15); color: #646cff; font-size: 12px; }
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; margin-top: 12px; }
.card { background: rgba(255, 255, 255, 0.04); border: 1px solid rgba(100, 108, 255, 0.15); border-radius: 12px; padding: 12px; }
.card-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 8px; }
.header-actions { display: flex; align-items: center; gap: 8px; }
.title { font-weight: 600; }
.subtitle { font-size: 12px; }
.status { font-size: 12px; padding: 2px 8px; border-radius: 999px; border: 1px solid transparent; }
.status.ok { color: #16a34a; background: rgba(22, 163, 74, 0.12); border-color: rgba(22, 163, 74, 0.35); }
.status.warn { color: #ca8a04; background: rgba(202, 138, 4, 0.12); border-color: rgba(202, 138, 4, 0.35); }
.grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.bluetooth-devices { margin-top: 12px; }
.bluetooth-device { background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(100, 108, 255, 0.08); border-radius: 8px; padding: 12px; margin-bottom: 12px; }
.bluetooth-device:last-child { margin-bottom: 0; }
.bt-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 8px; }
.bt-title { font-weight: 500; font-size: 14px; }
.btn.small { padding: 4px 8px; font-size: 12px; }
.grid-item { background: rgba(255, 255, 255, 0.03); border: 1px dashed rgba(100, 108, 255, 0.2); border-radius: 8px; padding: 10px; }
.grid-item.wide { grid-column: span 4; }
label { display: block; font-size: 12px; opacity: 0.7; margin-bottom: 4px; }
.value { font-weight: 600; }
.output { max-height: 260px; overflow: auto; background: rgba(0, 0, 0, 0.2); border-radius: 8px; padding: 8px; white-space: pre-wrap; }
.error { color: #ef4444; }
.error.small { font-size: 12px; opacity: 0.9; }
.muted { opacity: 0.7; }
.empty { text-align: center; opacity: 0.8; margin-top: 8px; }
.illustration { font-size: 42px; margin-bottom: 8px; }
.btn { border-radius: 8px; border: 1px solid transparent; padding: 0.4em 0.9em; font-size: 0.9em; cursor: pointer; background: #1a1a1a; }
.btn.secondary { background: #0f172a; border-color: rgba(148, 163, 184, 0.3); }
.btn.ghost { background: transparent; border-color: rgba(148, 163, 184, 0.3); }
.fade-enter-active, .fade-leave-active { transition: opacity .2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

/* Skeleton styles */
.skeleton { position: relative; overflow: hidden; }
.skeleton::after { content: ''; position: absolute; inset: 0; background: linear-gradient(90deg, transparent, rgba(255,255,255,0.08), transparent); transform: translateX(-100%); animation: shimmer 1.5s infinite; }
.skeleton-line { height: 12px; background: rgba(255,255,255,0.07); border-radius: 6px; margin: 10px 0; }
.skeleton-line.w-60 { width: 60%; } .skeleton-line.w-40 { width: 40%; } .skeleton-line.w-100 { width: 100%; } .skeleton-line.w-80 { width: 80%; } .skeleton-line.w-70 { width: 70%; }
@keyframes shimmer { 100% { transform: translateX(100%); } }
</style>
