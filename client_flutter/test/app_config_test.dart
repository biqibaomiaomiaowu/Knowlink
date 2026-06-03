import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/core/config/app_config.dart';

void main() {
  test('AppConfig falls back to local week 1 defaults', () {
    expect(AppConfig.apiBaseUrl, 'http://localhost:8000');
    expect(AppConfig.demoToken, 'knowlink-demo-token');
  });

  test('Android app allows local HTTP playback endpoints', () {
    final manifest = File('android/app/src/main/AndroidManifest.xml')
        .readAsStringSync();

    expect(
      manifest,
      contains('android:usesCleartextTraffic="true"'),
      reason:
          'video_player uses Android native networking, so local MinIO HTTP '
          'playback URLs such as http://127.0.0.1:9000 must be allowed.',
    );
  });
}
