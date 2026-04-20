import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/core/widgets/app_error_view.dart';
import 'package:knowlink_client/core/widgets/app_loading_view.dart';

void main() {
  testWidgets('AppLoadingView renders spinner and label', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: AppLoadingView(label: '正在获取推荐'),
        ),
      ),
    );

    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(find.text('正在获取推荐'), findsOneWidget);
  });

  testWidgets('AppErrorView renders message and retry action', (tester) async {
    var retried = false;

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: AppErrorView(
            message: '推荐接口暂不可用',
            onRetry: () => retried = true,
          ),
        ),
      ),
    );

    expect(find.text('推荐接口暂不可用'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, '重试'), findsOneWidget);

    await tester.tap(find.widgetWithText(FilledButton, '重试'));
    await tester.pump();

    expect(retried, isTrue);
  });
}
