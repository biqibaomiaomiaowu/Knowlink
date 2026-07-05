import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:knowlink_client/app/theme/app_theme.dart';
import 'package:knowlink_client/core/network/api_client.dart';
import 'package:knowlink_client/features/course_library/course_library_page.dart';
import 'package:knowlink_client/shared/models/course_lesson_models.dart';
import 'package:knowlink_client/shared/providers/course_flow_providers.dart';
import 'package:knowlink_client/shared/providers/course_library_provider.dart';
import 'package:knowlink_client/shared/providers/course_recommend_provider.dart';

void main() {
  testWidgets('course library follows the Soft UI library layout',
      (tester) async {
    _useTestSurface(tester);
    final api = _CourseLibraryFakeApiClient();
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(api),
        ],
        child: const MaterialApp(home: CourseLibraryPage()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('课程库'), findsWidgets);
    expect(
        find.byKey(const Key('course_library_search_field')), findsOneWidget);
    expect(find.text('全部课程'), findsOneWidget);
    expect(find.text('全部来源'), findsOneWidget);
    expect(find.text('未归档'), findsOneWidget);
    expect(find.text('最近学习优先'), findsOneWidget);
    expect(find.text('数据结构期末复习'), findsOneWidget);
    expect(find.text('当前课程'), findsOneWidget);
    expect(find.text('6 课时'), findsOneWidget);
    expect(find.textContaining('学习状态：learning_ready'), findsNothing);
    expect(find.textContaining('课程资料 3'), findsNothing);
    expect(find.textContaining('生成进度：handout / running'), findsNothing);
    expect(find.text('继续学习'), findsOneWidget);
    expect(find.widgetWithText(OutlinedButton, '进入工作台'), findsNothing);
    expect(find.byKey(const Key('course_tile_surface_101')), findsOneWidget);

    final tile = tester.widget<AnimatedContainer>(
      find.byKey(const Key('course_tile_surface_101')),
    );
    final decoration = tile.decoration! as BoxDecoration;
    expect(decoration.color, AppTheme.surface);
    expect(decoration.borderRadius, BorderRadius.circular(28));
  });

  testWidgets(
      'course library continues current lesson and keeps workbench entry',
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

    final continueButton = find.text('继续学习');
    await tester.ensureVisible(continueButton);
    await tester.tap(continueButton);
    await tester.pumpAndSettle();

    expect(find.text('lesson-handout-101-l-2'), findsOneWidget);
    expect(container.read(courseFlowProvider).courseId, '101');
    expect(container.read(activeLessonProvider)?.lessonId, 'l-2');

    router.go('/courses');
    await tester.pumpAndSettle();
    final courseTitle = find.text('数据结构期末复习');
    await tester.ensureVisible(courseTitle);
    await tester.tap(courseTitle);
    await tester.pumpAndSettle();

    expect(find.text('workbench-101'), findsOneWidget);
  });

  testWidgets('course library applies query controls to fetches',
      (tester) async {
    _useTestSurface(tester);
    final api = _CourseLibraryFakeApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(api),
      ],
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: CourseLibraryPage()),
      ),
    );
    await tester.pumpAndSettle();

    await tester.enterText(
      find.byKey(const Key('course_library_search_field')),
      '线代',
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('course_library_status_filter')));
    await tester.pumpAndSettle();
    expect(
        find.byKey(const Key('course_library_status_archived')), findsNothing);
    await tester.tap(
      find.byKey(const Key('course_library_status_learning_ready')).last,
    );
    await tester.pumpAndSettle();
    await _selectDropdown(
      tester,
      triggerKey: const Key('course_library_source_filter'),
      itemKey: const Key('course_library_source_bilibili'),
    );
    await _selectDropdown(
      tester,
      triggerKey: const Key('course_library_archived_filter'),
      itemKey: const Key('course_library_archived_only'),
    );
    await _selectDropdown(
      tester,
      triggerKey: const Key('course_library_sort_filter'),
      itemKey: const Key('course_library_sort_title_asc'),
    );

    final query = container.read(courseLibraryQueryProvider);
    expect(query.query, '线代');
    expect(query.learningStatus, 'learning_ready');
    expect(query.source, 'bilibili');
    expect(query.archived, 'only');
    expect(query.sort, 'title_asc');
    expect(
        api.fetchRequests.last,
        const _CourseLibraryFetchRequest(
          query: '线代',
          learningStatus: 'learning_ready',
          source: 'bilibili',
          archived: 'only',
          sort: 'title_asc',
        ));
  });

  testWidgets('course library archives and restores with current query',
      (tester) async {
    _useTestSurface(tester);
    final api = _CourseLibraryFakeApiClient();
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(api),
        ],
        child: const MaterialApp(home: CourseLibraryPage()),
      ),
    );
    await tester.pumpAndSettle();

    await tester.enterText(
      find.byKey(const Key('course_library_search_field')),
      '线代',
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('归档'));
    await tester.pumpAndSettle();

    expect(api.archivedCourseIds, ['101']);
    expect(api.fetchRequests.last.query, '线代');

    await _selectDropdown(
      tester,
      triggerKey: const Key('course_library_archived_filter'),
      itemKey: const Key('course_library_archived_only'),
    );
    await tester.tap(find.text('恢复'));
    await tester.pumpAndSettle();

    expect(api.restoredCourseIds, ['101']);
    expect(api.fetchRequests.last.archived, 'only');
  });

  testWidgets('course library supports selecting and deleting courses',
      (tester) async {
    _useTestSurface(tester);
    final api = _CourseLibraryFakeApiClient();
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(api),
        ],
        child: const MaterialApp(home: CourseLibraryPage()),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('删除课程'));
    await tester.pumpAndSettle();

    expect(find.text('已选 0 / 1'), findsOneWidget);
    expect(find.text('删除所选'), findsOneWidget);

    await tester.tap(find.text('选择课程'));
    await tester.pumpAndSettle();

    expect(find.text('已选 1 / 1'), findsOneWidget);
    await tester.tap(find.text('删除所选'));
    await tester.pumpAndSettle();

    expect(find.text('删除课程'), findsOneWidget);
    expect(api.deleteImpactCourseIds, ['101']);
    expect(find.textContaining('课时 2'), findsOneWidget);
    expect(find.textContaining('资料 1'), findsOneWidget);
    await tester.tap(find.widgetWithText(FilledButton, '删除'));
    await tester.pumpAndSettle();

    expect(api.deletedCourseIds, ['101']);
  });
}

Future<void> _selectDropdown(
  WidgetTester tester, {
  required Key triggerKey,
  required Key itemKey,
}) async {
  await tester.tap(find.byKey(triggerKey));
  await tester.pumpAndSettle();
  await tester.tap(find.byKey(itemKey).last);
  await tester.pumpAndSettle();
}

void _useTestSurface(WidgetTester tester) {
  tester.view.physicalSize = const Size(1200, 900);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

class _CourseLibraryFakeApiClient extends ApiClient {
  final List<_CourseLibraryFetchRequest> fetchRequests = [];
  final Set<String> _archivedIds = <String>{};
  final List<String> deletedCourseIds = [];
  final List<String> deleteImpactCourseIds = [];
  final List<String> archivedCourseIds = [];
  final List<String> restoredCourseIds = [];

  @override
  Future<List<CourseLibraryItemModel>> fetchCourseLibrary({
    String? query,
    String? learningStatus,
    String? source,
    String archived = 'exclude',
    String sort = 'recent_activity_desc',
  }) async {
    fetchRequests.add(
      _CourseLibraryFetchRequest(
        query: query,
        learningStatus: learningStatus,
        source: source,
        archived: archived,
        sort: sort,
      ),
    );
    final isArchived = _archivedIds.contains('101');
    if (archived == 'exclude' && isArchived) {
      return [];
    }
    if (archived == 'only' && !isArchived) {
      return [];
    }
    return [_courseItem(archived: isArchived)];
  }

  @override
  Future<CourseDeleteImpactModel> fetchCourseDeleteImpact(
    String courseId,
  ) async {
    deleteImpactCourseIds.add(courseId);
    return CourseDeleteImpactModel.fromJson({
      'courseId': courseId,
      'canDelete': false,
      'blockerCount': 3,
      'blockers': {
        'lessons': 2,
        'resources': 1,
      },
    });
  }

  @override
  Future<CourseLibraryItemModel> archiveCourse(String courseId) async {
    archivedCourseIds.add(courseId);
    _archivedIds.add(courseId);
    return _courseItem(archived: true);
  }

  @override
  Future<CourseLibraryItemModel> restoreCourse(String courseId) async {
    restoredCourseIds.add(courseId);
    _archivedIds.remove(courseId);
    return _courseItem(archived: false);
  }

  @override
  Future<void> deleteCourse(String courseId) async {
    deletedCourseIds.add(courseId);
  }

  CourseLibraryItemModel _courseItem({required bool archived}) {
    return CourseLibraryItemModel.fromJson({
      'courseId': 101,
      'title': '数据结构期末复习',
      'isCurrent': true,
      'entryType': 'bilibili',
      'learningStatus': archived ? 'archived' : 'learning_ready',
      'lastActivityAt': '2026-06-01T09:30:00+08:00',
      'lessonCount': 6,
      'courseResourceCount': 3,
      'currentLessonId': 'l-2',
      'currentLessonTitle': '关系模型',
      'overallMasteryScore': 0.72,
      'pendingReviewCount': 4,
      'pipelineStage': 'handout',
      'pipelineStatus': 'running',
      'lifecycleStatus': archived ? 'archived' : 'learning_ready',
      'archivedAt': archived ? '2026-06-02T10:00:00+08:00' : null,
    });
  }
}

class _CourseLibraryFetchRequest {
  const _CourseLibraryFetchRequest({
    required this.query,
    required this.learningStatus,
    required this.source,
    required this.archived,
    required this.sort,
  });

  final String? query;
  final String? learningStatus;
  final String? source;
  final String archived;
  final String sort;

  @override
  bool operator ==(Object other) {
    return other is _CourseLibraryFetchRequest &&
        other.query == query &&
        other.learningStatus == learningStatus &&
        other.source == source &&
        other.archived == archived &&
        other.sort == sort;
  }

  @override
  int get hashCode => Object.hash(
        query,
        learningStatus,
        source,
        archived,
        sort,
      );
}
