#!/bin/bash

# ADB Bluetooth API测试脚本

echo "🔍 测试ADB设备蓝牙信息API"
echo "================================"

BASE_URL="http://localhost:8001"

# 获取认证token
echo -e "\n1. 获取认证token"
LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/login" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=admin&password=admin123")

TOKEN=$(echo "$LOGIN_RESPONSE" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

if [ -z "$TOKEN" ]; then
    echo "❌ 无法获取认证token"
    exit 1
fi

echo "✓ 获取到token: ${TOKEN:0:20}..."

# 获取设备列表
echo -e "\n2. 获取设备列表"
DEVICES_RESPONSE=$(curl -s -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/devices")
echo "设备列表响应: $DEVICES_RESPONSE" | head -300

# 提取ADB设备ID
ADB_DEVICES=$(echo "$DEVICES_RESPONSE" | grep -o '"device_id":"[^"]*"' | grep -v bluetooth | head -3)
echo -e "\n找到的ADB设备: $ADB_DEVICES"

# 测试每个ADB设备的蓝牙信息
echo -e "\n3. 测试ADB设备蓝牙信息API"
echo "$ADB_DEVICES" | while read -r device_line; do
    if [ -n "$device_line" ]; then
        DEVICE_ID=$(echo "$device_line" | cut -d'"' -f4)
        echo -e "\n测试设备: $DEVICE_ID"
        echo "GET /api/devices/$DEVICE_ID/bluetooth/info"
        
        BLUETOOTH_INFO=$(curl -s -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/devices/$DEVICE_ID/bluetooth/info")
        echo "蓝牙信息响应: $BLUETOOTH_INFO"
        
        # 检查响应是否包含预期字段
        if echo "$BLUETOOTH_INFO" | grep -q "bluetooth_info"; then
            echo "✓ 成功获取蓝牙信息"
        else
            echo "❌ 蓝牙信息获取失败或格式不正确"
        fi
    fi
done

echo -e "\n✅ ADB蓝牙API测试完成"