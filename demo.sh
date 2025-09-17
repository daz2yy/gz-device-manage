#!/bin/bash

# Device Management System - Demo Script
# 演示系统主要功能的测试脚本

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🎯 设备管理系统功能演示${NC}"
echo "=================================="

# 1. 获取访问令牌
echo -e "\n${YELLOW}1. 管理员登录${NC}"
TOKEN_RESPONSE=$(curl -s -X POST "http://localhost:8001/auth/login" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=admin&password=admin123")

TOKEN=$(echo $TOKEN_RESPONSE | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

if [ -n "$TOKEN" ]; then
    echo -e "${GREEN}✓ 登录成功${NC}"
else
    echo "❌ 登录失败"
    exit 1
fi

# 2. 获取设备统计
echo -e "\n${YELLOW}2. 获取设备统计${NC}"
STATS=$(curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8001/api/devices/stats")
echo "设备统计: $STATS"

# 3. 获取设备列表
echo -e "\n${YELLOW}3. 获取设备列表${NC}"
DEVICES=$(curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8001/api/devices")
echo "设备列表: $DEVICES"

# 4. 触发设备扫描
echo -e "\n${YELLOW}4. 触发设备扫描${NC}"
SCAN_RESULT=$(curl -s -X POST -H "Authorization: Bearer $TOKEN" "http://localhost:8001/api/devices/scan")
echo "扫描结果: $SCAN_RESULT"

# 5. 获取用户信息
echo -e "\n${YELLOW}5. 获取当前用户信息${NC}"
USER_INFO=$(curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8001/auth/me")
echo "用户信息: $USER_INFO"

# 6. 测试WebSocket连接（简单测试）
echo -e "\n${YELLOW}6. 测试WebSocket端点${NC}"
WS_TEST=$(curl -s -I "http://localhost:8001/ws" | head -1)
echo "WebSocket端点: $WS_TEST"

echo -e "\n${GREEN}🎉 演示完成！${NC}"
echo "=================================="
echo -e "${BLUE}访问地址:${NC}"
echo "• Web界面: http://localhost:5173"
echo "• API文档: http://localhost:8001/docs"
echo ""
echo -e "${BLUE}默认账户:${NC}"
echo "• 用户名: admin"
echo "• 密码: admin123"