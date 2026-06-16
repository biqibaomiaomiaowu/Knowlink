import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:knowlink_client/features/lesson_detail/lesson_detail_page.dart';
import 'package:knowlink_client/features/quiz/quiz_page.dart';

void main() {
  testWidgets('lesson study renders video, materials, AI and handout', (
    tester,
  ) async {
    _useTestSurface(tester);

    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(
          home: LessonDetailPage(courseId: 'course-1', lessonId: 'lesson-1'),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('课时学习'), findsWidgets);
    expect(find.text('主视频'), findsOneWidget);
    expect(find.text('本节 AI 问答'), findsOneWidget);
    expect(find.text('本节资料'), findsOneWidget);
    expect(find.text('本节讲义'), findsOneWidget);
    expect(find.text('stack-queue-review.pdf'), findsWidgets);
    expect(find.text('根据资料生成讲义'), findsOneWidget);
  });

  testWidgets('lesson study can generate handout and ask AI', (tester) async {
    _useTestSurface(tester);

    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(
          home: LessonDetailPage(courseId: 'course-1', lessonId: 'lesson-1'),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('根据资料生成讲义'));
    await tester.pumpAndSettle();
    expect(find.text('基于资料生成的本节讲义'), findsOneWidget);
    expect(find.textContaining('核心概念'), findsOneWidget);

    await tester.ensureVisible(find.text('发送').last);
    await tester.enterText(find.byType(TextField), '循环队列怎么判满？');
    await tester.tap(find.text('发送'));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(find.text('本节 AI 问答'), findsOneWidget);
  });

  testWidgets('lesson study enters test center', (tester) async {
    _useTestSurface(tester);
    final router = GoRouter(
      routes: [
        GoRoute(
          path: '/',
          builder: (_, __) => const LessonDetailPage(
            courseId: 'course-1',
            lessonId: 'lesson-1',
          ),
        ),
        GoRoute(
          path: '/courses/:courseId/test',
          builder: (_, state) => QuizPage(
            courseId: state.pathParameters['courseId']!,
          ),
        ),
      ],
    );

    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('进入测试'));
    await tester.pumpAndSettle();

    expect(find.byType(QuizPage), findsOneWidget);
  });
}

void _useTestSurface(WidgetTester tester) {
  tester.view.physicalSize = const Size(1280, 1400);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}
