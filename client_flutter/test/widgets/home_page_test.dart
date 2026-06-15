import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:knowlink_client/features/course_library/course_library_page.dart';
import 'package:knowlink_client/features/course_workbench/course_workbench_page.dart';
import 'package:knowlink_client/features/home/home_page.dart';

void main() {
  testWidgets('home page renders the redesigned study overview', (
    tester,
  ) async {
    _useTestSurface(tester);

    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(home: HomePage()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('学习总览'), findsWidgets);
    expect(find.text('KNOWLINK / STUDY CENTER'), findsOneWidget);
    expect(find.text('今日学习计划'), findsOneWidget);
    expect(find.text('进入当前课时'), findsOneWidget);
    expect(find.text('推荐复习'), findsOneWidget);
    expect(find.text('最近课程'), findsOneWidget);

    expect(find.text('进入测试'), findsNothing);
    expect(find.text('下一步学习'), findsNothing);
    expect(find.text('课程数'), findsNothing);
    expect(find.text('今日计划'), findsNothing);
    expect(find.text('薄弱点'), findsNothing);
  });

  testWidgets('home can jump to library and create a course', (tester) async {
    _useTestSurface(tester);
    final router = GoRouter(
      routes: [
        GoRoute(path: '/', builder: (_, __) => const HomePage()),
        GoRoute(
            path: '/courses', builder: (_, __) => const CourseLibraryPage()),
        GoRoute(
          path: '/courses/:courseId',
          builder: (_, state) => CourseWorkbenchPage(
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

    await tester.tap(find.text('查看课程库'));
    await tester.pumpAndSettle();
    expect(find.byType(CourseLibraryPage), findsOneWidget);

    router.go('/');
    await tester.pumpAndSettle();
    await tester.tap(find.text('新建课程').last);
    await tester.pumpAndSettle();
    expect(find.text('新建课程'), findsWidgets);
    await tester.tap(find.text('取消'));
    await tester.pumpAndSettle();
  });
}

void _useTestSurface(WidgetTester tester) {
  tester.view.physicalSize = const Size(1280, 1400);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}
