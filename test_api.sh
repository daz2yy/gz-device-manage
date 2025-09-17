#!/bin/bash

# API端点测试脚本

echo "🔍 测试设备管理系统API端点"
echo "================================"

BASE_URL="http://localhost:8001"

# 测试基础端点（无需认证）
echo -e "\n1. 测试基础端点（无需认证）"
echo "GET /docs"
curl -s -I "$BASE_URL/docs" | head -1

echo "GET /openapi.json"
curl -s -I "$BASE_URL/openapi.json" | head -1

# 测试认证端点
echo -e "\n2. 测试认证端点"
echo "POST /auth/login"
LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/login" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=admin&password=admin123")

echo "Login response: $LOGIN_RESPONSE"

# 提取token
TOKEN=$(echo "$LOGIN_RESPONSE" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

if [ -z "$TOKEN" ]; then
    echo "❌ 无法获取认证token"
    exit 1
fi

echo "✓ 获取到token: ${TOKEN:0:20}..."

# 测试需要认证的端点
echo -e "\n3. 测试需要认证的API端点"

echo "GET /auth/me"
curl -s -H "Authorization: Bearer $TOKEN" "$BASE_URL/auth/me" | head -100

echo -e "\nGET /api/devices/stats"
curl -s -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/devices/stats"

echo -e "\nGET /api/devices"
curl -s -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/devices" | head -200

echo -e "\nPOST /api/devices/scan"
curl -s -X POST -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/devices/scan"

# 检查所有可用的API端点
echo -e "\n4. 检查OpenAPI文档中的所有端点"
echo "可用的API端点："
curl -s "$BASE_URL/openapi.json" | grep -o '"/[^"]*"' | grep -E '"/api|/auth' | sort | uniq

echo -e "\n✅ API测试完成"