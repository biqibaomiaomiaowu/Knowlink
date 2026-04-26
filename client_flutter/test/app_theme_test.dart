import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/app/theme/app_theme.dart';

void main() {
  test('AppTheme.light exposes the frozen week 1 visual defaults', () {
    final theme = AppTheme.light();

    expect(theme.useMaterial3, isTrue);
    expect(theme.scaffoldBackgroundColor, const Color(0xFFF6F8F7));
    expect(theme.appBarTheme.centerTitle, isFalse);
    expect(
      theme.cardTheme.shape,
      isA<RoundedRectangleBorder>().having(
        (shape) => shape.borderRadius,
        'borderRadius',
        BorderRadius.circular(20),
      ),
    );
  });
}
