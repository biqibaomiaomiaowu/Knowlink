class AppConfig {
  static const apiBaseUrl = String.fromEnvironment(
    'KNOWLINK_API_BASE_URL',
    defaultValue: 'http://localhost:8000',
  );

  static const demoToken = String.fromEnvironment(
    'KNOWLINK_DEMO_TOKEN',
    defaultValue: 'knowlink-demo-token',
  );
}
