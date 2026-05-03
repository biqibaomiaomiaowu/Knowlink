# 首版资料清单

本文件记录当前首版资料集对应的项目内联调资料映射。二进制文件只保留在项目内的 gitignored 本地目录，不纳入 Git 跟踪。

## 1. 资料来源与用途

- 来源说明：用户提供的首版资料目录
- 本地副本目录：`local_assets/first-edition/what-is-set/`
- 绑定手动导入课程标题：`KnowLink 固定联调课`
- 适用场景：Week 1 固定联调资料集、手动导入演示、PDF/PPTX/DOCX/视频混合引用验证

## 2. 文件映射

| 资源类型 | 原始文件名 | 规范文件名 | MIME | sizeBytes | checksum |
|---|---|---|---|---:|---|
| `mp4` | `集合的初见.mp4` | `knowlink-demo-main.mp4` | `video/mp4` | 38985139 | `sha256:55fa962beef83f57d1568f4ee9d7fcaf9d86e8f90521b65da0c577f2ad9b6a17` |
| `pdf` | `1_1_what_is_set.pdf` | `knowlink-demo-handout.pdf` | `application/pdf` | 135310 | `sha256:5c4e50b9d6de0ed739b3a45be876f958c6d194a0ff87e66fe2f18f32242c7da8` |
| `pptx` | `1_1_what_is_set.pptx` | `knowlink-demo-slides.pptx` | `application/vnd.openxmlformats-officedocument.presentationml.presentation` | 88576 | `sha256:30ea64e0775ee77dcfc26794173c1393520b53bed6ece46c0cef43cb9d4f7641` |
| `docx` | `集合论基础_讲义.docx` | `knowlink-demo-docx.docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | 62255 | `sha256:ab9985c054b9170a118fc19ffef31f93082ea176bf48dbbae6e40705dd8c0d8a` |

## 3. 维护约束

- 仓库只跟踪文档与 `server/seeds/demo_assets_manifest.json`，不跟踪 `local_assets/**` 下的二进制文件。
- 如果文件内容更新，必须同步更新本文件和 manifest 中的 `sizeBytes` 与 `checksum`。
- 演示时统一使用规范文件名，避免不同设备上出现命名分叉。

## 4. 手动 smoke preflight

脚本：`scripts/demo_assets_smoke.py`

仅校验本地资料是否齐全：

```bash
python scripts/demo_assets_smoke.py --asset-check-only
```

完整手动 smoke 前置检查：

```bash
python scripts/demo_assets_smoke.py --api-base-url http://127.0.0.1:8000
```

完整检查要求：

- API 已启动且 `GET /health` 返回成功：`python -m uvicorn server.app:app --reload`
- MinIO 可连接，并设置 `KNOWLINK_MINIO_ENDPOINT`、`KNOWLINK_MINIO_ACCESS_KEY`、`KNOWLINK_MINIO_SECRET_KEY`
- Vivo 联网解析配置齐全：`KNOWLINK_ENABLE_VIVO_OCR=true`、`KNOWLINK_ENABLE_VIVO_VISION=true`、`KNOWLINK_ENABLE_VIVO_ASR=true`、`KNOWLINK_VIVO_APP_ID`、`KNOWLINK_VIVO_APP_KEY`
- `local_assets/first-edition/what-is-set/` 下四个文件存在，且 size/checksum 与 `server/seeds/demo_assets_manifest.json` 一致

脚本 exit code：

- `0`：manifest、本地资料通过；默认完整模式下还表示手动 smoke 前置条件均通过，脚本会打印后续手动上传、解析、轮询路径
- `1`：manifest 缺失、JSON 非法或字段结构非法
- `2`：本地资料缺失、size 不一致或 checksum 不一致
- `3`：本地资料可用，但 API、MinIO 或 Vivo key/开关等运行前置缺失

如果本轮最终验收不跑完整 smoke，需要在汇报中明确写出：

- 未运行命令或只运行了 `--asset-check-only`
- 阻塞原因，例如缺 Vivo key、API/MinIO 未启动，或固定资料目录不存在
- 已经验证到哪一层，例如 manifest + 本地 size/checksum 已通过
- 未覆盖的风险，例如未验证真实上传、MinIO PUT、Vivo OCR/Vision/ASR 和 parse pipeline 轮询结果
