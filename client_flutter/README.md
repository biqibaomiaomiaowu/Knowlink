# knowlink_client

KnowLink MVP Flutter 客户端。

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

推荐验证顺序：

```powershell
flutter pub get
flutter analyze
flutter test test/core/network/api_client_test.dart
flutter test test/widgets/course_recommend_page_test.dart
flutter test
```

Windows PowerShell 手动推荐页 smoke：

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
$profile = "$env:TEMP\knowlink_chrome_cors_off"
Remove-Item -Recurse -Force $profile -ErrorAction SilentlyContinue
& "C:\Program Files\Google\Chrome\Application\chrome.exe" `
  --disable-web-security `
  --disable-site-isolation-trials `
  --user-data-dir="$profile" `
  http://localhost:52853
```

然后打开 `http://localhost:52853`，进入智能课程推荐页，获取推荐，确认入课，并验证页面能展示已创建课程结果，且仍可跳转到自主导入页。

独立 Chrome 命令仅用于 FastAPI scaffold 尚未配置 CORS 时的本地 Flutter Web 验收，可在 Week 1 smoke 测试中避免修改后端代码。

## 故障排查

- Flutter 会在 `<flutter-sdk>\\bin\\cache` 下写入 SDK cache 锁文件。如果当前进程没有该 SDK 路径的写权限，命令可能会在输出前卡住。
- 在受限 shell 或沙箱中，如果 Flutter SDK 位于不可写的工作区之外，容易出现上述问题。请在普通宿主机 shell 中运行 Flutter，或把 SDK 移到可写位置。
- 如果后端日志出现 `OPTIONS ... 405 Method Not Allowed`，说明页面是在普通浏览器会话中打开的。请使用上面的独立 Chrome 命令重新打开。
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
