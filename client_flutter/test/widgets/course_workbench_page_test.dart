import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:knowlink_client/features/course_qa/course_qa_page.dart';
import 'package:knowlink_client/features/course_workbench/course_workbench_page.dart';
import 'package:knowlink_client/features/lesson_detail/lesson_detail_page.dart';

void main() {
  testWidgets('course workspace renders lessons and course materials', (
    tester,
  ) async {
    _useTestSurface(tester);

    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(home: CourseWorkbenchPage(courseId: 'course-1')),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('数据结构期末复习'), findsWidgets);
    expect(find.text('课程工作区'), findsWidgets);
    expect(find.text('课时列表'), findsOneWidget);
    expect(find.text('课程资料'), findsWidgets);
    expect(find.text('栈与队列专项复习'), findsOneWidget);
    expect(find.text('data-structure-final-outline.docx'), findsOneWidget);
  });

  testWidgets('course workspace opens lesson and AI chat', (tester) async {
    _useTestSurface(tester);
    final router = GoRouter(
      routes: [
        GoRoute(
          path: '/',
          builder: (_, __) => const CourseWorkbenchPage(courseId: 'course-1'),
        ),
        GoRoute(
          path: '/courses/:courseId/lessons/:lessonId',
          builder: (_, state) => LessonDetailPage(
            courseId: state.pathParameters['courseId']!,
            lessonId: state.pathParameters['lessonId']!,
          ),
        ),
        GoRoute(
          path: '/courses/:courseId/chat',
          builder: (_, state) => CourseQaPage(
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

    await tester.tap(find.text('进入 AI 问答'));
    await tester.pumpAndSettle();
    expect(find.byType(CourseQaPage), findsOneWidget);

    router.go('/');
    await tester.pumpAndSettle();
    await tester.tap(find.text('栈与队列专项复习').first);
    await tester.pumpAndSettle();
    expect(find.byType(LessonDetailPage), findsOneWidget);
  });
}

void _useTestSurface(WidgetTester tester) {
  tester.view.physicalSize = const Size(1400, 1200);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}
