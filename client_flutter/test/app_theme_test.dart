import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/app/theme/app_theme.dart';

void main() {
  test('AppTheme.light exposes the KnowLink prototype visual defaults', () {
    final theme = AppTheme.light();

    expect(theme.useMaterial3, isTrue);
    expect(theme.scaffoldBackgroundColor, AppTheme.page);
    expect(theme.appBarTheme.centerTitle, isFalse);
    expect(
      theme.cardTheme.shape,
      isA<RoundedRectangleBorder>().having(
        (shape) => shape.borderRadius,
        'borderRadius',
        BorderRadius.circular(32),
      ),
    );
    expect(theme.filledButtonTheme.style?.minimumSize?.resolve({}), const Size(52, 46));
    expect(theme.outlinedButtonTheme.style?.minimumSize?.resolve({}), const Size(52, 46));
  });
}
