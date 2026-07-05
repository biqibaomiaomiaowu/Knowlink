import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:knowlink_client/core/network/api_client.dart';
import 'package:knowlink_client/features/course_library/course_library_page.dart';
import 'package:knowlink_client/shared/models/course_lesson_models.dart';
import 'package:knowlink_client/shared/providers/course_flow_providers.dart';
import 'package:knowlink_client/shared/providers/course_recommend_provider.dart';

void main() {
  testWidgets('course library displays V2 course metadata', (tester) async {
    _useTestSurface(tester);
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(_CourseLibraryFakeApiClient()),
        ],
        child: const MaterialApp(home: CourseLibraryPage()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('课程库'), findsWidgets);
    expect(find.text('数据库系统'), findsOneWidget);
    expect(find.text('当前课程'), findsOneWidget);
    expect(find.textContaining('学习状态：learning_ready'), findsOneWidget);
    expect(find.textContaining('最近活动：2026-06-01'), findsOneWidget);
    expect(find.textContaining('课时 6'), findsOneWidget);
    expect(find.textContaining('课程资料 3'), findsOneWidget);
    expect(find.textContaining('当前课时：关系模型'), findsOneWidget);
    expect(find.textContaining('掌握度 72%'), findsOneWidget);
    expect(find.textContaining('待复习 4'), findsOneWidget);
    expect(find.textContaining('生成进度：handout / running'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, '继续学习'), findsOneWidget);
    expect(find.widgetWithText(OutlinedButton, '进入工作台'), findsOneWidget);
  });

  testWidgets('course library continues current lesson and keeps workbench entry',
      (tester) async {
    _useTestSurface(tester);
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(_CourseLibraryFakeApiClient()),
      ],
    );
    addTearDown(container.dispose);
    final router = GoRouter(
      initialLocation: '/courses',
      routes: [
        GoRoute(
          path: '/courses',
          builder: (context, state) => const CourseLibraryPage(),
        ),
        GoRoute(
          path: '/courses/:courseId',
          builder: (context, state) =>
              Text('workbench-${state.pathParameters['courseId']}'),
        ),
        GoRoute(
          path: '/courses/:courseId/lessons/:lessonId/handout',
          builder: (context, state) => Text(
            'lesson-handout-${state.pathParameters['courseId']}-'
            '${state.pathParameters['lessonId']}',
          ),
        ),
      ],
    );

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();

    final continueButton = find.widgetWithText(FilledButton, '继续学习');
    await tester.ensureVisible(continueButton);
    await tester.tap(continueButton);
    await tester.pumpAndSettle();

    expect(find.text('lesson-handout-101-l-2'), findsOneWidget);
    expect(container.read(courseFlowProvider).courseId, '101');
    expect(container.read(activeLessonProvider)?.lessonId, 'l-2');

    router.go('/courses');
    await tester.pumpAndSettle();
    final workbenchButton = find.widgetWithText(OutlinedButton, '进入工作台');
    await tester.ensureVisible(workbenchButton);
    await tester.tap(workbenchButton);
    await tester.pumpAndSettle();

    expect(find.text('workbench-101'), findsOneWidget);
  });
}

void _useTestSurface(WidgetTester tester) {
  tester.view.physicalSize = const Size(1200, 900);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

class _CourseLibraryFakeApiClient extends ApiClient {
  @override
  Future<List<CourseLibraryItemModel>> fetchCourseLibrary({
    String? query,
    String? learningStatus,
    String? source,
    String archived = 'exclude',
    String sort = 'recent_activity_desc',
  }) async {
    return [
      CourseLibraryItemModel.fromJson({
        'courseId': 101,
        'title': '数据库系统',
        'isCurrent': true,
        'entryType': 'bilibili',
        'learningStatus': 'learning_ready',
        'lastActivityAt': '2026-06-01T09:30:00+08:00',
        'lessonCount': 6,
        'courseResourceCount': 3,
        'currentLessonId': 'l-2',
        'currentLessonTitle': '关系模型',
        'overallMasteryScore': 0.72,
        'pendingReviewCount': 4,
        'pipelineStage': 'handout',
        'pipelineStatus': 'running',
        'lifecycleStatus': 'learning_ready',
        'archivedAt': null,
      }),
    ];
  }
}
