#!/bin/bash

# 前端API代理测试脚本

echo "🔍 测试前端代理到后端API的连通性"
echo "========================================"

FRONTEND_URL="http://localhost:5173"
BACKEND_URL="http://localhost:8001"

# 测试前端服务状态
echo -e "\n1. 检查前端服务状态"
if curl -s -I "$FRONTEND_URL" | head -1 | grep -q "200 OK"; then
    echo "✅ 前端服务运行正常"
else
    echo "❌ 前端服务未运行"
    exit 1
fi

# 测试后端服务状态
echo -e "\n2. 检查后端服务状态"
if curl -s -I "$BACKEND_URL/docs" | head -1 | grep -q "200 OK"; then
    echo "✅ 后端服务运行正常"
else
    echo "❌ 后端服务未运行"
    exit 1
fi

# 测试前端代理 - 认证端点
echo -e "\n3. 测试前端代理 - 认证端点"
echo "POST $FRONTEND_URL/auth/login"
LOGIN_RESPONSE=$(curl -s -X POST "$FRONTEND_URL/auth/login" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=admin&password=admin123")

if echo "$LOGIN_RESPONSE" | grep -q "access_token"; then
    echo "✅ 认证代理工作正常"
    TOKEN=$(echo "$LOGIN_RESPONSE" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
    echo "   Token: ${TOKEN:0:20}..."
else
    echo "❌ 认证代理失败"
    echo "   Response: $LOGIN_RESPONSE"
    exit 1
fi

# 测试前端代理 - API端点
echo -e "\n4. 测试前端代理 - API端点"

echo "GET $FRONTEND_URL/api/devices/stats"
STATS_RESPONSE=$(curl -s -H "Authorization: Bearer $TOKEN" "$FRONTEND_URL/api/devices/stats")
if echo "$STATS_RESPONSE" | grep -q "total_devices"; then
    echo "✅ 设备统计代理正常"
    echo "   $(echo "$STATS_RESPONSE" | grep -o '"total_devices":[0-9]*')"
else
    echo "❌ 设备统计代理失败"
    echo "   Response: $STATS_RESPONSE"
fi

echo "POST $FRONTEND_URL/api/devices/scan"
SCAN_RESPONSE=$(curl -s -X POST -H "Authorization: Bearer $TOKEN" "$FRONTEND_URL/api/devices/scan")
if echo "$SCAN_RESPONSE" | grep -q "Device scan triggered successfully"; then
    echo "✅ 设备扫描代理正常"
    echo "   Response: $SCAN_RESPONSE"
else
    echo "❌ 设备扫描代理失败"
    echo "   Response: $SCAN_RESPONSE"
fi

echo "GET $FRONTEND_URL/api/devices"
DEVICES_RESPONSE=$(curl -s -H "Authorization: Bearer $TOKEN" "$FRONTEND_URL/api/devices")
if echo "$DEVICES_RESPONSE" | grep -q "device_id"; then
    DEVICE_COUNT=$(echo "$DEVICES_RESPONSE" | grep -o '"device_id"' | wc -l)
    echo "✅ 设备列表代理正常"
    echo "   找到 $DEVICE_COUNT 个设备"
else
    echo "❌ 设备列表代理失败"
    echo "   Response: ${DEVICES_RESPONSE:0:100}..."
fi

# 测试前端页面访问
echo -e "\n5. 测试前端页面访问"
if curl -s "$FRONTEND_URL/test_frontend.html" | grep -q "前端API连通性测试"; then
    echo "✅ 测试页面可访问: $FRONTEND_URL/test_frontend.html"
else
    echo "⚠️  测试页面不可访问"
fi

echo -e "\n🎉 前端代理测试完成！"
echo "========================================"
echo "✅ 前端地址: $FRONTEND_URL"
echo "✅ 后端地址: $BACKEND_URL"
echo "✅ 测试页面: $FRONTEND_URL/test_frontend.html"
echo ""
echo "🔧 如果遇到问题，请检查："
echo "1. 前端和后端服务是否都在运行"
echo "2. Vite代理配置是否正确"
echo "3. 认证token是否有效"