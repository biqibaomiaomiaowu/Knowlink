# 杨彩艺 Android 联调后端地址说明

来源：

- `docs/contracts/api-contract.md`
- `docs/engineering/development-scaffold.md`

用途：整理 Android 模拟器、真机和 Wi-Fi 场景访问本地后端、MinIO 上传/播放地址的联调注意事项。本文只做联调说明，不修改网络配置、不实现后端逻辑。

## 联调目标

| 目标 | 说明 |
|---|---|
| App 能访问 FastAPI | 至少能访问健康检查、课程、资源、讲义等接口 |
| 上传 URL 设备可达 | `uploadUrl` 不能返回容器内部 host |
| 播放 URL 设备可达 | `playbackUrl` 不能返回容器内部 host |
| 状态可记录 | 记录接口、地址、响应状态、错误码和证据 |

## 后端地址场景

| 场景 | App 中建议访问地址 | 适用情况 | 联调记录重点 |
|---|---|---|---|
| Android 模拟器访问宿主机后端 | `http://10.0.2.2:8000` | Android Studio 模拟器访问本机 FastAPI | 记录模拟器名称、API 版本、后端端口 |
| Android 真机 USB 调试 | `http://127.0.0.1:8000` 或 App 配置的本地地址，配合 `adb reverse tcp:8000 tcp:8000` | 真机通过 USB 访问电脑本地后端 | 记录是否执行 `adb reverse`，以及真机型号 |
| Android 真机 Wi-Fi | `http://<宿主机局域网IP>:8000` | 手机和电脑在同一局域网 | 记录宿主机 IP、手机网络、端口是否可达 |
| Flutter Web 本地联调 | `http://127.0.0.1:8000` | 浏览器访问本机后端 | FastAPI 当前默认允许本地 Flutter Web origin |

说明：

- 如果使用真机 Wi-Fi，`<宿主机局域网IP>` 需要替换为电脑在当前网络中的实际 IP。
- 如果端口不是 `8000`，联调记录中必须写清楚实际端口。
- 生产或测试分发环境的 HTTPS、明文 HTTP 策略不在本文处理范围内。

## MinIO URL 可达性要求

`api-contract.md` 已冻结以下要求：

| URL 类型 | 字段 | 要求 | 禁止情况 |
|---|---|---|---|
| 上传预签名 URL | `uploadUrl` | 本地 Docker 联调时必须使用浏览器或设备可访问的 `KNOWLINK_MINIO_PUBLIC_ENDPOINT` 签名，例如 `http://127.0.0.1:9000/...` | 不能返回容器内部 hostname `minio:9000` |
| 播放预签名 URL | `playbackUrl` | 必须返回设备可访问的对象存储预签名 GET 地址，默认 1 小时有效 | 不能返回容器内部 hostname `minio:9000` |

Android 真机场景特别注意：

| 场景 | `KNOWLINK_MINIO_PUBLIC_ENDPOINT` 建议 | 说明 |
|---|---|---|
| 模拟器 | `http://10.0.2.2:9000` 或后端实际返回的可达地址 | 模拟器访问宿主机通常不能直接用宿主机 `127.0.0.1` |
| 真机 USB reverse | 根据实际 reverse 方案确认 | 需要同时确认 FastAPI 和 MinIO 端口是否都可达 |
| 真机 Wi-Fi | `http://<宿主机局域网IP>:9000` | 手机需要能访问宿主机的 MinIO 端口 |
| Flutter Web | `http://127.0.0.1:9000` | 浏览器在宿主机本地访问 |

## 需要重点验证的接口

| 模块 | 方法 | 路径 | 验证重点 |
|---|---|---|---|
| 健康检查 | `GET` | `/health` | 后端是否可达 |
| 最近课程 | `GET` | `/api/v1/courses/recent` | 鉴权、课程列表、基础状态字段 |
| 当前课程 | `GET` | `/api/v1/courses/current` | 当前课程是否可读取 |
| 课程详情 | `GET` | `/api/v1/courses/{courseId}` | 课程 ID、标题、状态字段 |
| 资源列表 | `GET` | `/api/v1/courses/{courseId}/resources` | 资源是否可展示 |
| 上传初始化 | `POST` | `/api/v1/courses/{courseId}/resources/upload-init` | `uploadUrl` 是否设备可达 |
| 播放地址 | `GET` | `/api/v1/course-resources/{resourceId}/playback` | `playbackUrl` 是否设备可播放 |
| 解析状态 | `GET` | `/api/v1/courses/{courseId}/pipeline-status` | 轮询状态、进度、下一步 |
| 最新讲义 | `GET` | `/api/v1/courses/{courseId}/handouts/latest` | 讲义状态 |
| 讲义目录 | `GET` | `/api/v1/courses/{courseId}/handouts/latest/outline` | 目录是否可展示 |

## 联调记录模板

| 记录项 | 填写内容 |
|---|---|
| 测试时间 |  |
| 设备类型 | 模拟器 / 真机 USB / 真机 Wi-Fi / Flutter Web |
| 设备信息 | 型号、Android 版本、模拟器名称 |
| FastAPI 地址 | 例如 `http://10.0.2.2:8000` |
| MinIO public endpoint | 例如 `http://10.0.2.2:9000` |
| demo token | 是否已配置 `KNOWLINK_DEMO_TOKEN`，不要在文档中记录真实 token |
| 健康检查结果 | 状态码、响应摘要 |
| 课程接口结果 | 状态码、响应摘要 |
| 上传 URL 可达性 | 可达 / 不可达；错误信息 |
| 播放 URL 可达性 | 可播放 / 不可播放；错误信息 |
| CORS 或网络错误 | 原始错误信息 |
| 截图或录屏 | 文件名或保存位置 |
| 待处理问题 | 归属前端 / 后端地址配置 / MinIO endpoint / 其他 |

## 常见问题排查

| 现象 | 可能原因 | 记录方式 |
|---|---|---|
| App 访问后端失败 | 地址使用了错误 host、端口未开放、服务未启动 | 记录当前地址、设备类型、状态码或错误 |
| 上传 URL 失败 | `uploadUrl` 返回了宿主机或容器不可达地址 | 记录完整 host，不需要记录签名参数 |
| 视频播放失败 | `playbackUrl` 不可达、MIME 不正确、对象不存在 | 记录 `resourceId`、URL host、错误提示 |
| 真机 Wi-Fi 可访问 FastAPI 但不能访问 MinIO | `KNOWLINK_MINIO_PUBLIC_ENDPOINT` 未使用局域网 IP | 记录 FastAPI host 和 MinIO host 是否一致可达 |
| 浏览器可用但 Android 不可用 | `127.0.0.1` 对 Android 设备含义不同 | 记录设备场景并改用对应地址方案 |

## 杨彩艺边界

| 可做 | 不做 |
|---|---|
| 整理 Android 联调地址和记录模板 | 修改后端网络实现 |
| 记录 URL 可达性和错误信息 | 改 MinIO 存储核心逻辑 |
| 检查接口返回 host 是否设备可达 | 实现视频播放或 range request |
| 整理截图、录屏和响应样例 | 处理生产 HTTPS 或安全策略 |
| 汇总需要曹乐或前端处理的问题 | 修改 B站下载、ffmpeg、AI、图谱、SSE、主观题判卷逻辑 |
