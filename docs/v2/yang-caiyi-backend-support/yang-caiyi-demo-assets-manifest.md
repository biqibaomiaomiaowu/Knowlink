# Yang Caiyi Demo Assets Manifest

本文整理任务 21：固定联调资料 manifest 说明。只整理清单，不提交二进制资料。

## Source

| Source | Purpose |
|---|---|
| `docs/contracts/week1-cao-le-freeze.md` | 固定联调资料集基线 |
| `server/seeds/demo_assets_manifest.json` | demo asset manifest |

## Manifest Summary

| Field | Value |
|---|---|
| `assetSetId` | `first-edition-what-is-set` |
| `manualImportCourseTitle` | `KnowLink 固定联调课` |
| `localBaseDir` | `local_assets/first-edition/what-is-set` |
| Binary files tracked in git | no |

## Assets

| `resourceType` | `normalizedName` | `originalName` | `mimeType` | `sizeBytes` | `sourceKind` |
|---|---|---|---|---:|---|
| `mp4` | `knowlink-demo-main.mp4` | `集合的初见.mp4` | `video/mp4` | 38985139 | `original` |
| `pdf` | `knowlink-demo-handout.pdf` | `1_1_what_is_set.pdf` | `application/pdf` | 135310 | `original` |
| `pptx` | `knowlink-demo-slides.pptx` | `1_1_what_is_set.pptx` | `application/vnd.openxmlformats-officedocument.presentationml.presentation` | 88576 | `original` |
| `docx` | `knowlink-demo-docx.docx` | `集合论基础_讲义.docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | 62255 | `original` |

## Field Notes

| Field | Meaning |
|---|---|
| `resourceType` | 与资源上传 contract 的类型一致 |
| `normalizedName` | 联调时使用的标准文件名 |
| `originalName` | 原始展示名 |
| `relativePath` | 相对 `localBaseDir` 的文件位置 |
| `mimeType` | 上传时应传入的 MIME |
| `sizeBytes` | 文件大小，用于 upload-complete 校验 |
| `checksum` | sha256 校验值 |
| `trackedInGit` | 是否提交二进制文件；当前均为 `false` |
| `sourceKind` | 资料来源类型 |

## Integration Checklist

| Step | Check |
|---|---|
| 1 | 本地准备 `local_assets/first-edition/what-is-set` 目录 |
| 2 | 文件名与 `normalizedName` 对齐 |
| 3 | 上传时使用 manifest 中的 `resourceType`、`mimeType`、`sizeBytes`、`checksum` |
| 4 | 上传完成后刷新 `GET /api/v1/courses/{courseId}/resources` |
| 5 | 视频资源可继续用 playback 接口检查 MinIO public endpoint |

## Yang Caiyi Boundary

| Item | Status |
|---|---|
| 整理 manifest 字段、联调步骤和测试记录 | 可做 |
| 提交 mp4/pdf/pptx/docx 二进制资料 | 不做 |
| 修改解析策略或资料生成策略 | 不做 |
