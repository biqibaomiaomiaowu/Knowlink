import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:knowlink_client/core/network/api_client.dart';
import 'package:knowlink_client/features/course_workbench/course_workbench_page.dart';
import 'package:knowlink_client/shared/models/course_lesson_models.dart';
import 'package:knowlink_client/shared/providers/course_recommend_provider.dart';

void main() {
  testWidgets('course workbench groups primary and secondary entries',
      (tester) async {
    _useTestSurface(tester, const Size(1200, 1600));
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(_CourseWorkbenchFakeApiClient()),
        ],
        child: const MaterialApp(
          home: CourseWorkbenchPage(courseId: '101'),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('数据库系统'), findsOneWidget);
    expect(find.textContaining('进度 33%'), findsOneWidget);
    expect(find.textContaining('6 课时'), findsOneWidget);
    expect(find.text('当前课时'), findsOneWidget);
    expect(find.text('课程资料'), findsOneWidget);
    expect(find.text('数据库教材.pdf'), findsOneWidget);
    expect(find.text('课时列表'), findsOneWidget);
    expect(find.text('第 2 课'), findsOneWidget);
    expect(find.text('正在学习'), findsOneWidget);
    expect(find.text('关系模型'), findsWidgets);
    expect(find.text('主要入口'), findsOneWidget);
    final primaryEntries =
        find.byKey(const Key('course_workbench_primary_entries'));
    expect(
      find.descendant(of: primaryEntries, matching: find.text('课时学习')),
      findsOneWidget,
    );
    expect(
      find.descendant(of: primaryEntries, matching: find.text('AI 问答')),
      findsOneWidget,
    );
    expect(
      find.descendant(of: primaryEntries, matching: find.text('测试中心')),
      findsOneWidget,
    );
    expect(
      find.descendant(of: primaryEntries, matching: find.text('复习中心')),
      findsOneWidget,
    );
    expect(find.text('更多工具'), findsOneWidget);
    expect(find.text('课程图谱'), findsOneWidget);
    expect(find.text('学习报告'), findsOneWidget);
    expect(find.text('课程导出'), findsOneWidget);
    expect(find.text('课程设置'), findsOneWidget);
    expect(find.text('全课程 QA'), findsNothing);
    expect(find.text('综合测验'), findsNothing);
    expect(find.text('课程总复习'), findsNothing);
    expect(find.text('课程级讲义工作台'), findsNothing);
    expect(find.text('继续学习关系模型'), findsOneWidget);
  });

  testWidgets('quick entry uses backend route for lesson study',
      (tester) async {
    _useTestSurface(tester, const Size(1200, 1600));
    final router = _workbenchRouter();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(
          _CourseWorkbenchFakeApiClient(
            quickEntries: [
              {
                'key': 'lesson_study',
                'title': 'Lesson study',
                'status': 'ready',
                'enabled': true,
                'route': '/courses/101/lessons/42/handout',
                'target': '/courses/101/lessons/42',
                'action': 'open_lesson_study',
                'message': 'Continue the current lesson',
              },
            ],
          ),
        ),
      ],
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.widgetWithText(OutlinedButton, '课时学习'));
    await tester.pumpAndSettle();

    expect(find.text('lesson-handout-route 101 42'), findsOneWidget);
    expect(find.text('review-route 101'), findsNothing);
  });

  testWidgets('lesson list opens the lesson handout route', (tester) async {
    _useTestSurface(tester, const Size(1200, 1600));
    final router = _workbenchRouter();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(_CourseWorkbenchFakeApiClient()),
      ],
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.widgetWithText(ListTile, '第 2 课'));
    await tester.pumpAndSettle();

    expect(find.text('lesson-handout-route 101 l-2'), findsOneWidget);
    expect(find.text('lesson-root-route 101 l-2'), findsNothing);
  });

  testWidgets('placeholder quick entry without enabled is not clickable',
      (tester) async {
    _useTestSurface(tester, const Size(1200, 1600));
    final router = _workbenchRouter();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(
          _CourseWorkbenchFakeApiClient(
            quickEntries: [
              {
                'key': 'report',
                'title': 'Disabled report',
                'status': 'placeholder',
                'route': '/courses/101/review?kind=report',
                'target': '/courses/101/review',
                'action': 'open_report',
                'message': 'Report is not ready',
              },
            ],
          ),
        ),
      ],
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();

    final button = find.widgetWithText(TextButton, '学习报告');
    expect(button, findsOneWidget);
    expect(tester.widget<TextButton>(button).onPressed, isNull);

    await tester.tap(button);
    await tester.pumpAndSettle();

    expect(find.byType(CourseWorkbenchPage), findsOneWidget);
    expect(find.text('review-route 101'), findsNothing);
  });
}

void _useTestSurface(WidgetTester tester, Size size) {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

GoRouter _workbenchRouter() {
  return GoRouter(
    initialLocation: '/courses/101',
    routes: [
      GoRoute(
        path: '/courses/:courseId',
        builder: (context, state) => CourseWorkbenchPage(
          courseId: state.pathParameters['courseId']!,
        ),
      ),
      GoRoute(
        path: '/courses/:courseId/lessons/:lessonId/handout',
        builder: (context, state) => Text(
          'lesson-handout-route '
          '${state.pathParameters['courseId']} '
          '${state.pathParameters['lessonId']}',
        ),
      ),
      GoRoute(
        path: '/courses/:courseId/lessons/:lessonId',
        builder: (context, state) => Text(
          'lesson-root-route '
          '${state.pathParameters['courseId']} '
          '${state.pathParameters['lessonId']}',
        ),
      ),
      GoRoute(
        path: '/courses/:courseId/review',
        builder: (context, state) =>
            Text('review-route ${state.pathParameters['courseId']}'),
      ),
    ],
  );
}

class _CourseWorkbenchFakeApiClient extends ApiClient {
  _CourseWorkbenchFakeApiClient({this.quickEntries});

  final List<Map<String, dynamic>>? quickEntries;

  @override
  Future<CourseWorkbenchModel> fetchCourseWorkbench(String courseId) async {
    return CourseWorkbenchModel.fromJson({
      'course': {
        'courseId': courseId,
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
      },
      'progress': {
        'completedLessonCount': 2,
        'totalLessonCount': 6,
        'progressPct': 33,
        'lastPositionSec': 125,
      },
      'currentLesson': _lesson(),
      'lessons': [_lesson()],
      'courseResources': [
        {
          'resourceId': 501,
          'courseId': courseId,
          'resourceType': 'pdf',
          'originalName': '数据库教材.pdf',
          'scopeType': 'course',
          'lessonId': null,
          'usageRole': 'course_material',
          'visibleToCourseQa': true,
          'durationSec': null,
          'sortOrder': 1,
        },
      ],
      'quickEntries': quickEntries ??
          [
            {
              'key': 'course_qa',
              'title': '全课程 QA',
              'status': 'ready',
              'message': '基于全部课时提问',
            },
            {
              'key': 'course_graph',
              'title': '课程图谱',
              'status': 'placeholder',
              'message': '图谱生成暂未启用',
            },
            {
              'key': 'comprehensive_quiz',
              'title': '综合测验',
              'status': 'placeholder',
              'message': '综合测验等待生成',
            },
            {
              'key': 'course_review',
              'title': '课程总复习',
              'status': 'generating',
              'message': '复习计划生成中',
            },
            {
              'key': 'course_summary_handout',
              'title': '课程级讲义工作台',
              'status': 'ready',
              'message': '整课讲义入口',
            },
            {
              'key': 'report',
              'title': '学习报告',
              'status': 'placeholder',
              'message': '报告暂未启用',
            },
            {
              'key': 'export',
              'title': '课程导出',
              'status': 'placeholder',
              'message': '导出暂未启用',
            },
            {
              'key': 'settings',
              'title': '课程设置',
              'status': 'ready',
              'message': '调整课程信息',
            },
          ],
      'nextActions': [
        {
          'type': 'continue_lesson',
          'lessonId': 'l-2',
          'title': '关系模型',
        },
      ],
      'placeholderStates': {},
    });
  }

  Map<String, dynamic> _lesson() {
    return {
      'lessonId': 'l-2',
      'courseId': 101,
      'title': '关系模型',
      'orderIndex': 2,
      'lessonStatus': 'learning_ready',
      'primaryVideoResourceId': 601,
      'primaryVideoStartSec': 0,
      'primaryVideoEndSec': 1800,
      'handoutStatus': 'ready',
      'quizStatus': 'not_generated',
      'reviewStatus': 'due',
      'masteryScore': 0.64,
      'lastPositionSec': 125,
      'lastActivityAt': '2026-06-01T09:30:00+08:00',
      'nextAction': {
        'type': 'resume_video',
        'label': '继续看视频',
        'route': '/courses/101/lessons/l-2',
        'reason': '上次看到 02:05',
      },
    };
  }
}
