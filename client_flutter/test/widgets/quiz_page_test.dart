import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/features/quiz/quiz_page.dart';

void main() {
  testWidgets('test center renders history and active paper', (tester) async {
    _useTestSurface(tester);

    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(home: QuizPage(courseId: 'course-1')),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('测试中心'), findsWidgets);
    expect(find.text('历史测试'), findsOneWidget);
    expect(find.text('栈与队列阶段测验'), findsWidgets);
    expect(find.textContaining('循环队列长度的正确计算方式'), findsOneWidget);
    expect(find.textContaining('薄弱点 循环队列'), findsOneWidget);
  });

  testWidgets('test center generates a new test from controls', (
    tester,
  ) async {
    _useTestSurface(tester);

    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(home: QuizPage(courseId: 'course-1')),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('困难'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('生成测试').last);
    await tester.pumpAndSettle();

    expect(find.textContaining('新测验'), findsWidgets);
    expect(find.text('困难'), findsWidgets);
    expect(find.text('未完成'), findsOneWidget);
  });

  testWidgets('test center regenerate modal creates a test', (tester) async {
    _useTestSurface(tester);

    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(home: QuizPage(courseId: 'course-1')),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('重新生成测验'));
    await tester.pumpAndSettle();
    expect(find.text('重新生成综合测验'), findsOneWidget);

    await tester.tap(find.text('生成测验'));
    await tester.pumpAndSettle();

    expect(find.textContaining('新测验'), findsWidgets);
  });
}

void _useTestSurface(WidgetTester tester) {
  tester.view.physicalSize = const Size(1280, 1400);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}
