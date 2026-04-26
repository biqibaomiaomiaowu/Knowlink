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
| `docx` | `集合的初见.docx` | `knowlink-demo-notes.docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | 40485 | `sha256:0b29a64b87c88bbe2597af046ef754ad1010d24f467f9a13e0ad397725555326` |

## 3. 维护约束

- 仓库只跟踪文档与 `server/seeds/demo_assets_manifest.json`，不跟踪 `local_assets/**` 下的二进制文件。
- 如果文件内容更新，必须同步更新本文件和 manifest 中的 `sizeBytes` 与 `checksum`。
- 演示时统一使用规范文件名，避免不同设备上出现命名分叉。
