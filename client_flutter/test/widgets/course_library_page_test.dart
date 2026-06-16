import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:knowlink_client/features/course_library/course_library_page.dart';
import 'package:knowlink_client/features/course_workbench/course_workbench_page.dart';

void main() {
  testWidgets('course library shows soft ui course cards', (tester) async {
    _useTestSurface(tester);

    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(home: CourseLibraryPage()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('课程库'), findsWidgets);
    expect(find.text('数据结构期末复习'), findsOneWidget);
    expect(find.text('操作系统核心概念'), findsOneWidget);
    expect(find.text('继续学习'), findsWidgets);
    expect(find.text('自主导入'), findsNothing);
    expect(find.text('智能课程推荐'), findsNothing);
  });

  testWidgets('course library continue opens workspace', (tester) async {
    _useTestSurface(tester);
    final router = GoRouter(
      routes: [
        GoRoute(path: '/', builder: (_, __) => const CourseLibraryPage()),
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

    await tester.tap(find.text('继续学习').first);
    await tester.pumpAndSettle();

    expect(find.byType(CourseWorkbenchPage), findsOneWidget);
    expect(find.text('课程工作区'), findsWidgets);
  });
}

void _useTestSurface(WidgetTester tester) {
  tester.view.physicalSize = const Size(1400, 1200);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}
