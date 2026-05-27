# KnowLink Flutter 客户端

KnowLink Flutter APP 客户端。当前仓库按 Flutter APP 交付组织，不承接快应用工程。

## 当前状态

- V1 主链路页面、路由、provider 和 API read model 已接入：推荐、创建 / 切换课程、上传、解析进度、问询、讲义、QA、测验、复习与首页聚合。
- V2 阶段一的 B站导入区块已接入自主导入页：登录态、扫码二维码会话、资源预览、分 P 选择、创建导入、状态轮询、取消、重试和导入后资源列表刷新。
- V2 阶段二的知识图谱、流式输出和主观题判卷页面尚未作为当前客户端可验收能力落地；对应后端 contract / read model 冻结后再接入。

## 本地开发

使用 Flutter `3.41.5`，保证本地分析结果与 GitHub Actions 保持一致。

推荐检查命令：

```powershell
flutter --version
flutter pub get
flutter analyze
flutter test
```

## Week 1 验证

推荐验证顺序；其中 B站导入相关用例覆盖当前 V2 阶段一前端状态：

```powershell
flutter pub get
flutter analyze
flutter test test/core/network/api_client_test.dart
flutter test test/widgets/course_recommend_page_test.dart
flutter test test/widgets/bilibili_import_page_test.dart
flutter test test/shared/bilibili_import_provider_test.dart
flutter test
```

Windows PowerShell 手动 smoke：

```powershell
# terminal 1
cd "D:\Flutter learning\Knowlink"
python -m uvicorn server.app:app --reload --host 0.0.0.0 --port 8000

# terminal 2
cd "D:\Flutter learning\Knowlink\client_flutter"
flutter run -d web-server `
  --web-port=52853 `
  --dart-define=KNOWLINK_API_BASE_URL=http://localhost:8000 `
  --dart-define=KNOWLINK_DEMO_TOKEN=knowlink-demo-token

# terminal 3
Start-Process "http://localhost:52853"
```

然后打开 `http://localhost:52853`，进入智能课程推荐页，获取推荐，确认入课，并验证页面能展示已创建课程结果，且可跳转到自主导入页。已有课程下的自主导入页会展示 B站导入区块；公共可访问视频可直接预览，账号态内容按二维码登录状态处理。

## 故障排查

- Flutter 会在 `<flutter-sdk>\\bin\\cache` 下写入 SDK cache 锁文件。如果当前进程没有该 SDK 路径的写权限，命令可能会在输出前卡住。
- 在受限 shell 或沙箱中，如果 Flutter SDK 位于不可写的工作区之外，容易出现上述问题。请在普通宿主机 shell 中运行 Flutter，或把 SDK 移到可写位置。
- FastAPI 默认允许 `http://localhost:*` 和 `http://127.0.0.1:*` 的 Flutter Web origin。若仍出现跨域预检失败，先检查后端是否运行在当前 `.env` 下，以及 `KNOWLINK_CORS_ALLOW_ORIGINS` 是否被收紧到不包含当前 Web 端口。
- 如果 Git 对 Flutter SDK checkout 报 `dubious ownership`，先信任该 SDK 仓库：

```powershell
git config --global --add safe.directory D:/flutter
```

- 如果不能修改全局 Git 配置，可以在当前 PowerShell 会话中使用临时覆盖：

```powershell
$env:GIT_CONFIG_COUNT='1'
$env:GIT_CONFIG_KEY_0='safe.directory'
$env:GIT_CONFIG_VALUE_0='D:/flutter'
```
