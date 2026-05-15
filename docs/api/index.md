# API参考

MyEAP提供RESTful API用于系统集成。

## API端点

### 设备管理

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/api/v1/equipment` | 获取设备列表 |
| GET | `/api/v1/equipment/{id}` | 获取设备详情 |
| POST | `/api/v1/equipment` | 注册设备 |
| PUT | `/api/v1/equipment/{id}` | 更新设备 |
| GET | `/api/v1/equipment/{id}/status` | 获取设备状态 |

### 配方管理

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/api/v1/recipes` | 获取配方列表 |
| GET | `/api/v1/recipes/{id}` | 获取配方详情 |
| POST | `/api/v1/recipes` | 创建配方 |
| PUT | `/api/v1/recipes/{id}` | 更新配方 |
| POST | `/api/v1/recipes/{id}/upload` | 上传配方到设备 |

### 报警管理

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/api/v1/alarms` | 获取报警列表 |
| POST | `/api/v1/alarms/{id}/acknowledge` | 确认报警 |
| POST | `/api/v1/alarms/{id}/clear` | 清除报警 |

## 认证

API使用JWT Token认证：

```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/v1/equipment
```

## 错误响应

```json
{
  "error": {
    "code": "EAP_ERROR",
    "message": "Error description",
    "details": {}
  }
}
```

## 限流

API请求限流：1000请求/分钟
