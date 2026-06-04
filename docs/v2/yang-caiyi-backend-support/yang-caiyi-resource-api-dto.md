# 杨彩艺 资源接口 DTO 文档

来源：`docs/contracts/api-contract.md`

用途：整理资源上传、上传完成、资源列表、播放地址和资源删除接口 DTO，供杨彩艺做接口文档、Android 联调记录和测试数据整理。本文只整理已有 contract，不改对象存储、MinIO、播放或删除核心逻辑。

## 接口清单

| 接口 | 方法 | 路径 | 用途 | 幂等要求 |
|---|---|---|---|---|
| 上传初始化 | `POST` | `/api/v1/courses/{courseId}/resources/upload-init` | 获取对象存储预签名上传地址 | 未列入幂等清单 |
| 上传完成 | `POST` | `/api/v1/courses/{courseId}/resources/upload-complete` | 通知后端资源已上传完成 | 必须支持 `Idempotency-Key` |
| 资源列表 | `GET` | `/api/v1/courses/{courseId}/resources` | 获取课程资源列表 | 无 |
| 播放地址 | `GET` | `/api/v1/course-resources/{resourceId}/playback` | 获取视频资源可播放预签名地址 | 无 |
| 删除资源 | `DELETE` | `/api/v1/courses/{courseId}/resources/{resourceId}` | 删除课程资源 | 无 |

## 上传初始化请求 DTO

接口：`POST /api/v1/courses/{courseId}/resources/upload-init`

| 字段 | 位置 | 类型 | 必填 | 示例 | 说明 |
|---|---|---|---|---|---|
| `courseId` | path | number | 是 | `101` | 课程 ID |
| `resourceType` | body | string | 是 | `pdf` | 资源类型：`mp4`、`pdf`、`pptx`、`docx`、`srt` |
| `filename` | body | string | 是 | `chapter-1.pdf` | 原始文件名 |
| `mimeType` | body | string | 是 | `application/pdf` | MIME 类型 |
| `sizeBytes` | body | number | 是 | `32768` | 文件大小 |
| `checksum` | body | string | 是 | `sha256:demo` | 文件校验值 |

## 上传初始化响应 DTO

| 字段 | 类型 | 示例 | 说明 |
|---|---|---|---|
| `uploadUrl` | string | `http://127.0.0.1:9000/...` | 对象存储预签名上传地址 |
| `objectKey` | string | `raw/1/101/temp/chapter-1.pdf` | 对象存储 key |
| `headers` | object | `{ "x-amz-meta-course-id": "101" }` | 上传时需要附带的 header |
| `expiresAt` | string, datetime | `2026-04-18T15:15:00+00:00` | 上传地址过期时间 |

联调注意：

| 项目 | 要求 |
|---|---|
| 本地 Docker 联调 | `uploadUrl` 必须使用浏览器或设备可访问的 `KNOWLINK_MINIO_PUBLIC_ENDPOINT` 签名 |
| 禁止 | 返回容器内部 hostname `minio:9000` |

## 上传完成请求 DTO

接口：`POST /api/v1/courses/{courseId}/resources/upload-complete`

| 字段 | 位置 | 类型 | 必填 | 示例 |
|---|---|---|---|---|
| `courseId` | path | number | 是 | `101` |
| `resourceType` | body | string | 是 | `pdf` |
| `objectKey` | body | string | 是 | `raw/1/101/temp/chapter-1.pdf` |
| `originalName` | body | string | 是 | `chapter-1.pdf` |
| `mimeType` | body | string | 是 | `application/pdf` |
| `sizeBytes` | body | number | 是 | `32768` |
| `checksum` | body | string | 是 | `sha256:demo` |

## 上传完成响应 DTO

| 字段 | 类型 | 示例 | 说明 |
|---|---|---|---|
| `resourceId` | number | `501` | 资源 ID |
| `ingestStatus` | string | `ready` | 入库状态 |
| `validationStatus` | string | `passed` | 校验状态 |
| `processingStatus` | string | `pending` | 后续处理状态 |

## 资源列表响应 DTO

接口：`GET /api/v1/courses/{courseId}/resources`

| 字段 | 类型 | 说明 |
|---|---|---|
| `items` | array | 课程资源列表 |

`items[]`：

| 字段 | 类型 | 示例 | 说明 |
|---|---|---|---|
| `resourceId` | number | `501` | 资源 ID |
| `resourceType` | string | `pdf` | 资源类型 |
| `originalName` | string | `chapter-1.pdf` | 原始文件名 |
| `objectKey` | string | `raw/1/101/temp/chapter-1.pdf` | 对象存储 key |
| `ingestStatus` | string | `ready` | 入库状态 |
| `validationStatus` | string | `passed` | 校验状态 |
| `processingStatus` | string | `pending` | 处理状态 |

## 播放地址响应 DTO

接口：`GET /api/v1/course-resources/{resourceId}/playback`

| 字段 | 类型 | 示例 | 说明 |
|---|---|---|---|
| `resourceId` | number | `501` | 资源 ID |
| `resourceType` | string | `mp4` | 必须为视频资源 |
| `playbackUrl` | string | `http://127.0.0.1:9000/...` | 对象存储预签名 GET 地址 |
| `mimeType` | string | `video/mp4` | MIME 类型 |
| `expiresAt` | string, datetime | `2026-04-18T16:00:00+00:00` | 播放地址过期时间 |
| `durationSec` | number/null | `null` | 当前无稳定字段时返回 `null` |

错误码：

| 错误码 | 含义 |
|---|---|
| `resource.not_found` | 资源不存在或不属于当前用户可访问课程 |
| `resource.not_video` | 资源存在但 `resourceType` 不是 `mp4` |
| `resource.playback_unavailable` | 对象存储不可用或播放地址生成失败 |

## 删除资源响应 DTO

接口：`DELETE /api/v1/courses/{courseId}/resources/{resourceId}`

| 字段 | 类型 | 示例 | 说明 |
|---|---|---|---|
| `deleted` | boolean | `true` | 是否已删除 |
| `resourceId` | number | `501` | 被删除资源 ID |

错误码：

| 错误码 | 含义 |
|---|---|
| `resource.not_found` | 资源不存在或不属于当前课程 |
| `resource.has_dependents` | 资源已被解析段落、向量文档、讲义引用、QA 引用、测验引用、复习引用或学习进度等产物引用 |

说明：当前删除接口不做级联删除。

## 联调记录模板

| 记录项 | 填写内容 |
|---|---|
| 测试时间 |  |
| 课程 ID |  |
| 资源类型 |  |
| 文件名 |  |
| upload-init 状态码 |  |
| `uploadUrl` host |  |
| `objectKey` |  |
| upload-complete 状态码 |  |
| `resourceId` |  |
| 资源列表是否出现 |  |
| playback 是否可达 |  |
| 错误码 |  |
| 证据 | 响应 JSON、截图或录屏 |

## 杨彩艺边界

| 可做 | 不做 |
|---|---|
| 整理上传和资源 DTO | 改 MinIO 存储核心逻辑 |
| 记录 URL 可达性 | 实现对象上传或播放逻辑 |
| 整理错误码和联调证据 | 实现 range request |
| 标注 `minio:9000` 不可作为设备访问地址 | 设计级联删除策略 |
