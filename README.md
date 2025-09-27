# 设备管理系统 (Device Management System)

一个现代化的设备管理平台，支持ADB设备和蓝牙设备的统一管理、占用控制和使用监控。

## 🚀 快速启动

### 一键启动（推荐）

**Linux/macOS:**
```bash
./start.sh start
```

**Windows:**
```cmd
start.bat start
```

### 手动启动

**后端服务:**
```bash
cd backend
pip install -r requirements.txt
python start.py
```

**前端服务:**
```bash
cd frontend
npm install
npm run dev
```

## 📋 系统要求

### 必需依赖
- **Python 3.8+** - 后端服务
- **Node.js 16+** - 前端构建
- **npm** - 包管理器

### 可选依赖
- **ADB (Android Debug Bridge)** - Android设备管理
- **bluetoothctl** - 蓝牙设备信息（在目标Android设备上）

## 🌐 访问地址

启动成功后，可通过以下地址访问：

- **Web界面**: http://localhost:5173
- **API文档**: http://localhost:8001/docs
- **API基础URL**: http://localhost:8001/api

## 🔑 默认账户

- **用户名**: `admin`
- **密码**: `admin123`

> ⚠️ **安全提醒**: 首次登录后请立即修改默认密码

## 📖 功能特性

### 🎯 核心功能
- **设备自动发现** - 自动扫描ADB和蓝牙设备
- **设备占用管理** - 防冲突的设备预订系统
- **实时状态监控** - WebSocket实时更新设备状态
- **使用日志审计** - 完整的设备使用记录

### 👥 用户管理
- **角色权限控制** - 管理员和普通用户权限
- **JWT认证** - 安全的token认证机制
- **个人仪表盘** - 使用统计和设备管理

### 📊 设备管理
- **设备分组** - 按项目或类型组织设备
- **标签系统** - 灵活的设备标记
- **批量操作** - 同时管理多个设备
- **高级搜索** - 多条件筛选和搜索
- **条件筛选** - 支持按设备ID、名称、型号、状态精准过滤

### 🖥️ 远程调试
- **一键远程重启** - 通过 Web 发送安全的 `adb reboot`
- **APK 上传安装** - 浏览器直传 APK，支持覆盖安装
- **Logcat 导出** - 选择缓冲区与行数，下载实时日志并可选清空
- **交互式 ADB Terminal** - 基于 WebSocket + xterm 的在线终端，具备会话超时与危险命令拦截

## 🛠️ 启动脚本命令

### 基本命令
```bash
./start.sh start      # 启动所有服务
./start.sh stop       # 停止所有服务
./start.sh restart    # 重启所有服务
./start.sh status     # 查看服务状态
```

### 高级命令
```bash
./start.sh install    # 安装所有依赖
./start.sh logs backend   # 查看后端日志
./start.sh logs frontend  # 查看前端日志
```

## 🧹 初始化工程整理

- 日志文件（`backend.log`、`frontend.log` 等）已从版本库中移除，并通过 `.gitignore` 默认忽略，避免污染仓库。
- 后端后台任务与数据库初始化改为在 FastAPI 启动阶段执行，确保在开发与测试场景下行为一致。
- 建议在本地运行前执行 `./start.sh install` 安装依赖，并根据需要创建 `.env`/配置文件。

## 🔧 开发模式

### 后端开发
```bash
cd backend
python start.py  # 自动重载模式
```

### 前端开发
```bash
cd frontend
npm run dev      # 热重载开发服务器
```

## 📁 项目结构

```
devices-manage/
├── backend/              # FastAPI后端服务
│   ├── main_enhanced.py  # 主应用文件
│   ├── database.py       # 数据库模型
│   ├── models.py         # API数据模型
│   ├── auth.py          # 认证系统
│   └── start.py         # 启动脚本
├── frontend/            # Vue.js前端应用
│   ├── src/
│   │   ├── components/  # Vue组件
│   │   ├── api.js      # API客户端
│   │   └── router.js   # 路由配置
│   └── package.json
├── start.sh            # Linux/macOS启动脚本
├── start.bat           # Windows启动脚本
└── README.md           # 项目说明
```

## 🚨 故障排除

### 常见问题

**端口占用错误**
```bash
# 检查端口占用
lsof -i :8001  # 后端端口
lsof -i :5173  # 前端端口

# 强制停止服务
./start.sh stop
```

**依赖安装失败**
```bash
# 重新安装依赖
./start.sh install
```

**ADB设备检测不到**
- 确保Android设备已启用USB调试
- 检查ADB是否正确安装：`adb version`
- 重新连接设备并授权

**数据库错误**
```bash
# 删除数据库文件重新初始化
rm backend/devices.db
./start.sh restart
```

### 日志查看
```bash
# 实时查看后端日志
./start.sh logs backend

# 实时查看前端日志
./start.sh logs frontend

# 查看启动日志
tail -f backend.log
tail -f frontend.log
```

## 🔒 安全配置

### 生产环境部署
1. 修改默认管理员密码
2. 更新JWT密钥：编辑 `backend/auth.py` 中的 `SECRET_KEY`
3. 配置HTTPS证书
4. 设置防火墙规则

### 环境变量
```bash
export DATABASE_URL="sqlite:///./devices.db"
export SECRET_KEY="your-secret-key-here"
export ACCESS_TOKEN_EXPIRE_MINUTES=30
```

## 📞 技术支持

如有问题或建议，请查看：
- **开发文档**: `CODEBUDDY.md`
- **API文档**: http://localhost:8001/docs
- **项目配置**: 各目录下的配置文件

---

**版本**: 1.0.0  
**最后更新**: 2025-09-10  
**开发工具**: CodeBuddy Code# gz-device-manage
