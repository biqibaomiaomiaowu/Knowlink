# 固定联调资料集规范

本文件定义 KnowLink MVP 每周联调都复用的固定资料集命名、校验和用途。仓库只维护规范，不提交实际二进制样例。

## 1. 资料集组成

| 资源类型 | 是否纳入固定联调 | 建议文件名 | MIME 示例 | 说明 |
|---|---|---|---|---|
| `mp4` | 必须 | `knowlink-demo-main.mp4` | `video/mp4` | 主课程视频 |
| `pdf` | 必须 | `knowlink-demo-handout.pdf` | `application/pdf` | 主讲义 PDF |
| `pptx` | 必须 | `knowlink-demo-slides.pptx` | `application/vnd.openxmlformats-officedocument.presentationml.presentation` | 覆盖 `slideNo` 引用 |
| `docx` | 必须 | `knowlink-demo-notes.docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | 覆盖 `anchorKey` 引用 |
| `srt` | 可选 | `knowlink-demo-subtitle.srt` | `application/x-subrip` | 辅助字幕输入，不单独构成验收通过条件 |

## 2. 命名与校验规则

- 文件名统一使用 `knowlink-demo-*` 前缀，避免每周联调出现不同命名口径
- 每个文件都要记录 `checksum`，格式固定为 `sha256:<hex>`
- 上传接口演示时统一回填 `originalName`、`mimeType`、`sizeBytes`、`checksum`
- 固定资料集默认绑定手动导入课程标题 `KnowLink 固定联调课`
- 首版资料的项目内本地副本统一放在 `local_assets/first-edition/what-is-set/`

## 3. 使用约束

- 推荐演示使用 `server/seeds/course_catalog.json` 中的 seed 标题；固定资料集主要用于手动导入和全链路联调
- 即使某条推荐课程的 `defaultResourceManifest` 中把 `pptx` 或 `docx` 标为可选，固定联调资料集也必须携带这两类文件，以验证 mixed citation 与 jump-target 行为
- 不在仓库中提交任何演示二进制文件；真实样例可放在线下共享目录、对象存储或项目内 `local_assets/` 的 gitignored 本地目录
