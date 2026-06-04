# 杨彩艺 V2 接口总览与联调说明

本文基于以下文档整理：

- docs/contracts/api-contract.md 
- docs/contracts/week1-cao-le-freeze.md 
- docs/engineering/development-scaffold.md 
- server 目录结构 

目标：

- 给前端 / 联调 / 测试提供统一接口视图
- 明确 V1 已实现能力与 V2 待补 contract 边界
- 明确杨彩艺可参与范围（仅文档 / DTO / 查询接口 / 联调）

---

# 1. 接口总览

## 1.1 推荐模块

| 接口 | 方法 | 说明 |
|------|------|------|
| /api/v1/recommendations/courses | POST | 获取课程推荐 |
| /api/v1/recommendations/{catalogId}/confirm | POST | 确认入课 |

---

## 1.2 课程与首页模块

| 接口 | 方法 | 说明 |
|------|------|------|
| /api/v1/courses | POST | 创建课程 |
| /api/v1/courses/recent | GET | 最近课程 |
| /api/v1/home/dashboard | GET | 首页聚合数据 |

---

## 1.3 资源模块

| 接口 | 方法 | 说明 |
|------|------|------|
| /api/v1/courses/{courseId}/resources/upload-init | POST | 初始化上传 |
| /api/v1/courses/{courseId}/resources/upload-complete | POST | 上传完成 |
| /api/v1/courses/{courseId}/resources | GET | 资源列表 |
| /api/v1/course-resources/{resourceId}/playback | GET | 获取播放地址 |
| /api/v1/courses/{courseId}/resources/{resourceId} | DELETE | 删除资源 |

---

## 1.4 解析与任务模块

| 接口 | 方法 | 说明 |
|------|------|------|
| /api/v1/courses/{courseId}/parse/start | POST | 启动解析 |
| /api/v1/parse-runs/{parseRunId} | GET | 解析状态 |
| /api/v1/courses/{courseId}/pipeline-status | GET | 主流程状态 |
| /api/v1/courses/{courseId}/parse/summary | GET | 解析摘要 |
| /api/v1/async-tasks/{taskId}/retry | POST | 重试任务 |

---

## 1.5 问询模块

| 接口 | 方法 | 说明 |
|------|------|------|
| /api/v1/courses/{courseId}/inquiry/questions | GET | 获取问题 |
| /api/v1/courses/{courseId}/inquiry/answers | POST | 提交答案 |

---

## 1.6 讲义模块

| 接口 | 方法 | 说明 |
|------|------|------|
| /api/v1/courses/{courseId}/handouts/generate | POST | 生成讲义 |
| /api/v1/handout-versions/{id}/status | GET | 讲义状态 |
| /api/v1/courses/{courseId}/handouts/latest | GET | 最新讲义 |
| /api/v1/courses/{courseId}/handouts/latest/outline | GET | 讲义目录 |
| /api/v1/courses/{courseId}/handouts/latest/blocks | GET | 讲义块 |
| /api/v1/handout-blocks/{blockId}/generate | POST | 生成块 |
| /api/v1/handout-blocks/{blockId}/status | GET | 块状态 |
| /api/v1/handout-blocks/{blockId}/jump-target | GET | 跳转目标 |

---

## 1.7 QA 模块

| 接口 | 方法 | 说明 |
|------|------|------|
| /api/v1/qa/messages | POST | 提问 |
| /api/v1/qa/sessions/{sessionId}/messages | GET | 获取历史 |

---

## 1.8 测验模块

| 接口 | 方法 | 说明 |
|------|------|------|
| /api/v1/courses/{courseId}/quizzes/generate | POST | 生成测验 |
| /api/v1/quizzes/{quizId} | GET | 获取测验 |
| /api/v1/quizzes/{quizId}/attempts | POST | 提交答案 |

---

## 1.9 复习模块

| 接口 | 方法 | 说明 |
|------|------|------|
| /api/v1/courses/{courseId}/review-tasks | GET | 获取复习任务 |
| /api/v1/courses/{courseId}/review-tasks/regenerate | POST | 重新生成 |
| /api/v1/review-task-runs/{id}/status | GET | 状态 |
| /api/v1/review-tasks/{id}/complete | POST | 完成 |

---

## 1.10 学习进度

| 接口 | 方法 | 说明 |
|------|------|------|
| /api/v1/courses/{courseId}/progress | GET | 获取进度 |
| /api/v1/courses/{courseId}/progress | POST | 保存进度 |

---

## 1.11 B站接口（V1 Stub）

| 接口 | 方法 | 说明 |
|------|------|------|
| /api/v1/courses/{courseId}/resources/imports/bilibili | POST | 导入（501） |
| /api/v1/bilibili-import-runs/{id}/status | GET | 状态 |
| /api/v1/bilibili/auth/qr/sessions | POST | 扫码 |
| /api/v1/bilibili/auth/session | GET | 登录状态 |

说明：

- 当前全部返回 `501 bilibili.not_implemented`
- V2 才接入真实能力

---

# 2. 核心状态枚举

## lifecycleStatus

- draft
- resource_ready
- inquiry_ready
- learning_ready
- archived
- failed

## pipelineStage

- idle
- upload
- parse
- inquiry
- handout

## pipelineStatus

- idle
- queued
- running
- partial_success
- succeeded
- failed

## async_tasks.status

- queued
- running
- succeeded
- failed
- retrying
- canceled
- skipped

---

# 3. 异步任务统一模型

所有异步接口统一返回：

```json
{
  "taskId": 7001,
  "status": "queued",
  "nextAction": "poll",
  "entity": {
    "type": "parse_run",
    "id": 9001
  }
}