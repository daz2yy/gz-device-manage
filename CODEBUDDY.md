# Device Management System - Enhanced

## Quick Start

### Development Mode
```bash
# Backend
cd backend
pip install -r requirements.txt
python start.py  # Starts on http://localhost:8001

# Frontend (new terminal)
cd frontend
npm install
npm run dev  # Starts on http://localhost:5173
```

### Production Deployment
```bash
# Using Docker Compose
docker-compose up -d

# Manual deployment
cd backend && python start.py &
cd frontend && npm run build && npm run preview
```

### Default Credentials
- Username: `admin`
- Password: `admin123`

## Enhanced Architecture

### System Components
- **Database**: SQLite with SQLAlchemy ORM (Users, Devices, Usage Logs)
- **Authentication**: JWT tokens with role-based access control
- **Real-time Updates**: WebSocket connections for live device status
- **Background Tasks**: APScheduler for automatic device scanning (30s intervals)
- **API**: Comprehensive REST API with pagination, filtering, and search

### New Features Implemented

#### 1. User Management & Authentication
- **Registration/Login**: JWT-based authentication system
- **Role-based Access**: Admin and User roles with different permissions
- **User Profile**: Personal dashboard with usage statistics

#### 2. Device Management
- **Database Storage**: Persistent device information with metadata
- **Device Occupation**: Conflict-free device reservation system
- **Usage Logging**: Complete audit trail of device usage
- **Device Grouping**: Organize devices by projects or categories
- **Tagging System**: Flexible labeling for device organization

#### 3. Enhanced Web Interface
- **Modern UI**: Element Plus components with responsive design
- **Dashboard**: Real-time statistics and device overview
- **Device List**: Advanced filtering, search, and batch operations
- **Device Details**: Comprehensive device information and usage history
- **Real-time Updates**: Live status updates via WebSocket

#### 4. Advanced Features
- **Batch Operations**: Occupy/release multiple devices simultaneously
- **Search & Filter**: Find devices by ID, name, type, status, or group
- **Usage Statistics**: Track device utilization and user activity
- **Admin Controls**: Device management and user administration

## File Structure

### Backend (`/backend/`)
```
main_enhanced.py     # Enhanced FastAPI application with full features
database.py          # SQLAlchemy models and database setup
models.py           # Pydantic models for API validation
auth.py             # JWT authentication and authorization
start.py            # Startup script with dependency checks
requirements.txt    # Python dependencies
main.py             # Legacy simple API (backward compatibility)
```

### Frontend (`/frontend/`)
```
src/
├── components/
│   ├── Login.vue           # Authentication interface
│   ├── Dashboard.vue       # Main dashboard with statistics
│   ├── DeviceList.vue      # Advanced device management
│   ├── DeviceDetail.vue    # Individual device information
│   └── UserProfile.vue     # User account management
├── api.js                  # API client with interceptors
├── router.js               # Vue Router configuration
├── store.js                # Global state management
├── App_enhanced.vue        # Enhanced main application layout
└── main_enhanced.js        # Application entry point with Element Plus
```

## API Endpoints

### Authentication
- `POST /auth/register` - User registration
- `POST /auth/login` - User login
- `GET /auth/me` - Get current user info

### Device Management
- `GET /api/devices` - List devices with filtering and pagination
- `GET /api/devices/stats` - Get device statistics
- `POST /api/devices/{id}/occupy` - Occupy a device
- `POST /api/devices/{id}/release` - Release a device
- `PUT /api/devices/{id}` - Update device information (admin only)
- `GET /api/devices/{id}/logs` - Get device usage logs
- `POST /api/devices/scan` - Trigger manual device scan

### WebSocket
- `WS /ws` - Real-time device status updates

### Legacy Endpoints (Backward Compatibility)
- `GET /devices` - Simple ADB device list
- `GET /bluetooth/infos` - Bluetooth device information

## Development Commands

### Backend Development
```bash
cd backend
pip install -r requirements.txt
python start.py                    # Start with auto-reload
python -m pytest tests/            # Run tests (if implemented)
```

### Frontend Development
```bash
cd frontend
npm install
npm run dev                        # Development server with hot reload
npm run build                      # Production build
npm run preview                    # Preview production build
```

### Database Management
```bash
cd backend
python -c "from database import create_tables; create_tables()"  # Initialize DB
```

## Configuration

### Environment Variables
- `DATABASE_URL` - Database connection string (default: sqlite:///./devices.db)
- `SECRET_KEY` - JWT secret key (change in production)
- `ACCESS_TOKEN_EXPIRE_MINUTES` - Token expiration time (default: 30)

### External Dependencies
- **ADB (Android Debug Bridge)**: Required for Android device management
- **bluetoothctl**: Required for Bluetooth device information (on target devices)

## Deployment Notes

### Docker Deployment
- Use provided `docker-compose.yml` for complete stack deployment
- Includes nginx reverse proxy for production
- Persistent data storage in `./data` volume

### Security Considerations
- Change default admin password after first login
- Update JWT secret key in production
- Use HTTPS in production environment
- Implement proper firewall rules for device access

### Monitoring
- WebSocket connection status indicator in UI
- Background task logs for device scanning
- Usage statistics for system monitoring

## Migration from Legacy System

The enhanced system maintains backward compatibility with the original API endpoints. To migrate:

1. **Database**: Run `python start.py` to auto-create database tables
2. **Frontend**: Use `App_enhanced.vue` and `main_enhanced.js` for full features
3. **Backend**: Use `main_enhanced.py` instead of `main.py`
4. **Configuration**: Update Vite proxy to point to port 8001

## Troubleshooting

### Common Issues
- **ADB not found**: Install Android SDK Platform Tools
- **Database errors**: Ensure write permissions in backend directory  
- **WebSocket connection failed**: Check firewall settings for port 8001
- **Device not detected**: Verify USB debugging enabled on Android devices

### Performance Optimization
- Adjust device scan interval in `main_enhanced.py` (default: 30 seconds)
- Implement database indexing for large device counts
- Use Redis for session storage in high-traffic environments

## CodeBuddy Added Memories
- 需求文档完整实现完成 ✅

🎯 已完成的核心功能：
1. ✅ 设备接入与信息收集 - ADB/蓝牙设备自动扫描和解析
2. ✅ 本地设备管理服务 - SQLite数据库、完整API、后台监控任务
3. ✅ 网页管理界面 - 现代化Vue3+ElementPlus界面，支持仪表盘、设备列表、详情页
4. ✅ 用户管理与权限控制 - JWT认证、角色权限、用户注册登录
5. ✅ 设备占用与释放管理 - 防冲突机制、使用日志、批量操作
6. ✅ 优化功能 - 设备分组标签、实时WebSocket更新、搜索筛选

📁 文件结构：
- 后端：main_enhanced.py, database.py, models.py, auth.py, start.py
- 前端：完整Vue3应用，包含Login、Dashboard、DeviceList、DeviceDetail、UserProfile组件
- 部署：Docker配置、启动脚本、需求文档更新

🚀 系统特性：
- 支持200+设备管理
- 实时状态更新（30秒扫描间隔）
- 完整的用户权限体系
- 现代化响应式界面
- 完整的使用审计日志
- 🎉 设备管理系统启动成功！

✅ 完成状态：
- 后端服务：http://localhost:8001 ✓
- 前端服务：http://localhost:5173 ✓  
- API文档：http://localhost:8001/docs ✓
- 默认管理员：admin/admin123 ✓

🔧 创建的启动脚本：
- start.sh (Linux/macOS) - 一键启动脚本
- start.bat (Windows) - Windows启动脚本
- demo.sh - 功能演示脚本
- README.md - 完整使用说明

📊 系统检测到设备：
- 1个ADB设备 (dd61e83c) - 在线
- 2个蓝牙设备 (iPhone) - 离线

🚀 启动命令：
./start.sh start    # 启动所有服务
./start.sh status   # 查看状态
./demo.sh          # 功能演示
