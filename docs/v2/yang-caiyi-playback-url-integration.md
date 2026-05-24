# Yang Caiyi Playback URL Integration

本文整理任务 7：播放地址接口联调说明。只说明播放 DTO、MinIO public endpoint 和 Android 可达性，不改对象存储实现。

## Source

| Source | Purpose |
|---|---|
| `docs/contracts/api-contract.md` | `GET /api/v1/course-resources/{resourceId}/playback` contract |
| `server/api/routers/resources.py` | router entry |
| `server/domain/services/resources.py` | playback service |
| `server/infra/storage/object_store.py` | object storage adapter |

## API

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/course-resources/{resourceId}/playback` | 获取视频资源播放地址 |

## Response DTO

| Field | Type | Meaning | Notes |
|---|---|---|---|
| `resourceId` | integer | 资源 id | path 中的 `resourceId` 对应资源 |
| `resourceType` | string | 资源类型 | 播放接口只接受 `mp4` |
| `playbackUrl` | string | 预签名播放地址 | 必须是客户端可访问地址 |
| `mimeType` | string | 媒体类型 | 常见为 `video/mp4` |
| `expiresAt` | datetime | 播放地址过期时间 | 默认约 1 小时，按服务端实现为准 |
| `durationSec` | integer or null | 视频时长 | 当前无稳定字段时返回 `null` |

## Errors

| HTTP | `errorCode` | Meaning |
|---|---|---|
| 404 | `resource.not_found` | 资源不存在或不属于当前用户可访问课程 |
| 409 | `resource.not_video` | 资源存在但不是 `mp4` |
| 503 | `resource.playback_unavailable` | 对象存储不可用或播放地址生成失败 |

## Android Connectivity Checklist

| Scenario | Check |
|---|---|
| Android emulator | `playbackUrl` 不能返回容器内 `minio:9000`；需要模拟器可访问 host |
| Real device | 手机和开发机需在同一 Wi-Fi；`playbackUrl` 使用开发机局域网 IP 或可访问域名 |
| Flutter Web | 本地通常可访问 `http://127.0.0.1:9000/...` |
| MinIO public endpoint | 后端应使用 `KNOWLINK_MINIO_PUBLIC_ENDPOINT` 生成预签名 URL |
| URL expiry | 过期后前端重新请求 playback 接口，不缓存长期播放地址 |

## Yang Caiyi Boundary

| Item | Status |
|---|---|
| 整理播放 DTO 和联调 checklist | 可做 |
| 记录 Android 真机是否能打开 `playbackUrl` | 可做 |
| 修改 MinIO 签名、存储 adapter 或对象权限策略 | 不做 |
