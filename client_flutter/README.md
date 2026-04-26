# knowlink_client

KnowLink MVP Flutter client.

## Local Development

Use Flutter `3.41.5` so local analysis matches GitHub Actions.

Recommended checks:

```powershell
flutter --version
flutter pub get
flutter analyze
flutter test
```

## Week 1 Validation

Recommended validation order:

```powershell
flutter pub get
flutter analyze
flutter test test/core/network/api_client_test.dart
flutter test test/widgets/course_recommend_page_test.dart
flutter test
```

Manual recommendation smoke:

```powershell
# terminal 1
uvicorn server.app:app --reload

# terminal 2
cd client_flutter
flutter run --dart-define=KNOWLINK_API_BASE_URL=http://localhost:8000
```

Then open the recommendation page, fetch recommendations, confirm a course, and verify the app shows the created course result and can still navigate to the import page.

## Troubleshooting

- Flutter writes SDK cache lock files under `<flutter-sdk>\\bin\\cache`. If the SDK path is not writable for the current process, commands can appear to hang before printing output.
- In restricted shells or sandboxes, this often happens when the Flutter SDK sits outside the writable workspace. Run Flutter from a normal host shell or move the SDK into a writable location.
- If Git reports `dubious ownership` for the Flutter SDK checkout, trust the SDK repo first:

```powershell
git config --global --add safe.directory D:/flutter
```

- If you cannot update global Git config, use a temporary PowerShell override for the current shell:

```powershell
$env:GIT_CONFIG_COUNT='1'
$env:GIT_CONFIG_KEY_0='safe.directory'
$env:GIT_CONFIG_VALUE_0='D:/flutter'
```
