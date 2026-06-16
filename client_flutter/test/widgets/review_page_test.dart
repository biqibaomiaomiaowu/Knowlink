import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/features/review/review_page.dart';

void main() {
  testWidgets('review center renders retained review modules', (tester) async {
    _useTestSurface(tester);

    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(home: ReviewPage(courseId: 'course-1')),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('复习中心'), findsWidgets);
    expect(find.text('今日复习'), findsOneWidget);
    expect(find.text('薄弱点'), findsOneWidget);
    expect(find.text('掌握度'), findsOneWidget);
    expect(find.text('薄弱知识图谱'), findsOneWidget);
    expect(find.text('今日复习路径'), findsOneWidget);
    expect(find.text('导出与报告'), findsOneWidget);
  });

  testWidgets('review center actions show feedback', (tester) async {
    _useTestSurface(tester);

    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(home: ReviewPage(courseId: 'course-1')),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('生成今日复习'));
    await tester.pumpAndSettle();
    expect(find.text('今日复习已生成'), findsOneWidget);

    await tester.pump(const Duration(seconds: 4));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('导出错题本'));
    await tester.tap(find.text('导出错题本'), warnIfMissed: false);
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(find.text('导出错题本'), findsOneWidget);
  });
}

void _useTestSurface(WidgetTester tester) {
  tester.view.physicalSize = const Size(1280, 1400);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}
