import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/core/config/app_config.dart';

void main() {
  test('AppConfig falls back to local week 1 defaults', () {
    expect(AppConfig.apiBaseUrl, 'http://localhost:8000');
    expect(AppConfig.demoToken, 'knowlink-demo-token');
  });
}
