import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/app/router/app_router.dart';
import 'package:knowlink_client/core/network/api_client.dart';
import 'package:knowlink_client/features/course_exports/course_exports_page.dart';
import 'package:knowlink_client/features/course_graph/course_graph_page.dart';
import 'package:knowlink_client/features/course_import/course_import_page.dart';
import 'package:knowlink_client/features/course_library/course_library_page.dart';
import 'package:knowlink_client/features/course_qa/course_qa_page.dart';
import 'package:knowlink_client/features/course_recommend/course_recommend_page.dart';
import 'package:knowlink_client/features/course_review/course_review_page.dart';
import 'package:knowlink_client/features/course_workbench/course_workbench_page.dart';
import 'package:knowlink_client/features/handout/handout_page.dart';
import 'package:knowlink_client/features/home/home_page.dart';
import 'package:knowlink_client/features/inquiry/inquiry_page.dart';
import 'package:knowlink_client/features/lesson_detail/lesson_detail_page.dart';
import 'package:knowlink_client/features/parse_progress/parse_progress_page.dart';
import 'package:knowlink_client/features/qa/qa_page.dart';
import 'package:knowlink_client/features/quiz/quiz_page.dart';
import 'package:knowlink_client/features/review/review_page.dart';
import 'package:knowlink_client/shared/models/bilibili_import_models.dart';
import 'package:knowlink_client/shared/models/course_lesson_models.dart';
import 'package:knowlink_client/shared/models/course_progress_models.dart';
import 'package:knowlink_client/shared/models/course_summary.dart';
import 'package:knowlink_client/shared/models/home_dashboard_models.dart';
import 'package:knowlink_client/shared/models/inquiry_models.dart';
import 'package:knowlink_client/shared/models/pipeline_status.dart';
import 'package:knowlink_client/shared/models/quiz_models.dart';
import 'package:knowlink_client/shared/models/review_models.dart';
import 'package:knowlink_client/shared/models/resource_upload_models.dart';
import 'package:knowlink_client/shared/providers/course_flow_providers.dart';
import 'package:knowlink_client/shared/providers/course_recommend_provider.dart';

void main() {
  testWidgets('frozen routes resolve to expected pages', (tester) async {
    final router = AppRouter.createRouter();
    final fakeApiClient = _RouterFakeApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(
          routerConfig: router,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byType(HomePage), findsOneWidget);

    final routes = <String, Finder>{
      '/import': find.byType(CourseImportPage),
      '/recommend': find.byType(CourseRecommendPage),
      '/courses': find.byType(CourseLibraryPage),
      '/courses/101': find.byType(CourseWorkbenchPage),
      '/courses/101/settings': find.byType(CourseGraphPage),
      '/courses/101/qa': find.byType(CourseQaPage),
      '/courses/101/graph': find.byType(CourseGraphPage),
      '/courses/101/review': find.byType(ReviewPage),
      '/courses/101/exports': find.byType(CourseExportsPage),
      '/courses/101/lessons/l-2': find.byType(LessonDetailPage),
      '/courses/101/lessons/l-2/qa': find.byType(CourseQaPage),
      '/courses/101/lessons/l-2/handout': find.byType(CourseReviewPage),
      '/courses/101/lessons/l-2/review': find.byType(CourseReviewPage),
      '/courses/101/lessons/l-2/graph': find.byType(CourseGraphPage),
      '/courses/101/progress': find.byType(ParseProgressPage),
      '/courses/101/inquiry': find.byType(InquiryPage),
      '/courses/101/handout': find.byType(HandoutPage),
      '/courses/101/quiz': find.byType(QuizPage),
      '/quizzes/8001': find.byType(QuizPage),
    };

    for (final entry in routes.entries) {
      router.go(entry.key);
      await tester.pumpAndSettle();
      expect(
        entry.value,
        findsOneWidget,
        reason: 'route ${entry.key} should resolve',
      );
      if (entry.key == '/courses/101') {
        expect(find.text('路由工作台 101'), findsOneWidget);
      }
    }

    router.go('/courses/101/review?kind=report');
    await tester.pumpAndSettle();
    expect(find.byType(CourseReviewPage), findsOneWidget);
    expect(find.text('学习报告'), findsOneWidget);

    router.go('/courses/101/review?kind=comprehensive_quiz');
    await tester.pumpAndSettle();
    expect(find.byType(CourseReviewPage), findsOneWidget);
    expect(find.text('综合测验'), findsOneWidget);

    router.go('/courses/101/review?kind=subjective_grading');
    await tester.pumpAndSettle();
    expect(find.byType(CourseReviewPage), findsOneWidget);
    expect(find.text('主观题判卷'), findsOneWidget);

    router.go('/courses/101/exports');
    await tester.pumpAndSettle();
    expect(find.text('导出占位 101'), findsOneWidget);

    router.go('/courses/202/exports');
    await tester.pumpAndSettle();
    expect(find.text('导出占位 202'), findsOneWidget);
    expect(fakeApiClient.exportPlaceholderCourseIds, contains('202'));

    router.go('/courses/205/qa/9876');
    await tester.pumpAndSettle();
    expect(find.byType(QaPage), findsOneWidget);
    expect(find.textContaining('QA'), findsOneWidget);
    expect(find.text('课程编号：205'), findsOneWidget);
    expect(find.text('QA 会话：9876'), findsOneWidget);
    expect(find.text('暂无会话消息'), findsOneWidget);
    final qaSendButton = find.byWidgetPredicate(
      (widget) => widget is IconButton && widget.tooltip == '发送',
    );
    expect(qaSendButton, findsOneWidget);
    expect(tester.widget<IconButton>(qaSendButton).onPressed, isNull);
    expect(find.textContaining('Push'), findsNothing);
    expect(find.textContaining('SqStack'), findsNothing);
    expect(find.text('第 1 章 绪论'), findsNothing);
    expect(find.text('教材 PDF 第 42 页'), findsNothing);
    expect(find.text('来源回看'), findsNothing);

    router.go('/quizzes/8001');
    await tester.pumpAndSettle();
    expect(find.byType(QuizPage), findsOneWidget);
    expect(find.textContaining('8001'), findsOneWidget);

    router.go('/');
    await tester.pumpAndSettle();
  });

  testWidgets('course routes sync URL courseId into course flow', (
    tester,
  ) async {
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(_RouterFakeApiClient()),
      ],
    );
    final router = AppRouter.createRouter();
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(
          routerConfig: router,
        ),
      ),
    );
    await tester.pumpAndSettle();

    router.go('/import');
    await tester.pumpAndSettle();
    expect(find.byType(CourseImportPage), findsOneWidget);
    expect(container.read(courseFlowProvider).courseId, isNull);

    router.go('/import?courseId=101');
    await tester.pumpAndSettle();
    expect(find.byType(CourseImportPage), findsOneWidget);
    expect(find.textContaining('101'), findsOneWidget);
    expect(container.read(courseFlowProvider).courseId, '101');

    router.go('/courses/205/progress');
    await tester.pumpAndSettle();
    expect(find.byType(ParseProgressPage), findsOneWidget);
    expect(container.read(courseFlowProvider).courseId, '205');

    router.go('/courses/306/qa/9876');
    await tester.pumpAndSettle();
    expect(find.byType(QaPage), findsOneWidget);
    expect(container.read(courseFlowProvider).courseId, '306');
  });

  testWidgets('home bottom nav does not invent course or quiz ids', (
    tester,
  ) async {
    _useTestSurface(tester, const Size(1448, 1086));
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(_RouterFakeApiClient()),
      ],
    );
    final router = AppRouter.createRouter();
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(
          routerConfig: router,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byType(HomePage), findsOneWidget);
    expect(container.read(courseFlowProvider).courseId, isNull);

    await tester.tap(find.text('讲义').last);
    await tester.pumpAndSettle();

    expect(find.byType(HomePage), findsOneWidget);
    expect(find.byType(HandoutPage), findsNothing);
    expect(container.read(courseFlowProvider).courseId, isNull);

    await tester.tap(find.text('测验').last);
    await tester.pumpAndSettle();

    expect(find.byType(HomePage), findsOneWidget);
    expect(find.byType(QuizPage), findsNothing);
    expect(container.read(courseFlowProvider).courseId, isNull);
  });

  testWidgets('home primary actions work on narrow screens', (
    tester,
  ) async {
    _useTestSurface(tester, const Size(390, 900));
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(_RouterFakeApiClient()),
      ],
    );
    final router = AppRouter.createRouter();
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(
          routerConfig: router,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
    await tester.tap(find.text('自主导入'));
    await tester.pumpAndSettle();

    expect(find.byType(CourseImportPage), findsOneWidget);

    router.go('/');
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('智能课程推荐'));
    await tester.tap(find.text('智能课程推荐'));
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
    expect(find.byType(CourseRecommendPage), findsOneWidget);
  });
}

void _useTestSurface(WidgetTester tester, Size size) {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

class _RouterFakeApiClient extends ApiClient {
  final exportPlaceholderCourseIds = <String>[];

  @override
  Future<CourseSummaryModel> fetchCourse(String courseId) async {
    return _course(int.parse(courseId));
  }

  @override
  Future<CourseSummaryModel> fetchCurrentCourse() async {
    return _course(202);
  }

  @override
  Future<BilibiliAuthSessionModel> fetchBilibiliAuthSession() async {
    return const BilibiliAuthSessionModel(
      loginStatus: 'none',
      userNickname: null,
      expiresAt: null,
    );
  }

  @override
  Future<BilibiliImportRunListModel> fetchBilibiliImportRuns(
    String courseId,
  ) async {
    return const BilibiliImportRunListModel(items: []);
  }

  @override
  Future<List<CourseResourceModel>> fetchCourseResources(
      String courseId) async {
    return const [];
  }

  @override
  Future<List<CourseLibraryItemModel>> fetchCourseLibrary({
    String? query,
    String? learningStatus,
    String? source,
    String archived = 'exclude',
    String sort = 'recent_activity_desc',
  }) async {
    return [_libraryItem('101')];
  }

  @override
  Future<CourseWorkbenchModel> fetchCourseWorkbench(String courseId) async {
    return CourseWorkbenchModel.fromJson({
      'course': _libraryItem(courseId).toJson(),
      'progress': {
        'progressPct': 40,
        'completedLessonCount': 1,
        'totalLessonCount': 2,
      },
      'currentLesson': _lesson(courseId, 'l-2'),
      'lessons': [_lesson(courseId, 'l-2')],
      'courseResources': [],
      'quickEntries': [],
      'nextActions': [],
      'placeholderStates': {},
    });
  }

  @override
  Future<LessonDetailModel> fetchLessonDetail({
    required String courseId,
    required String lessonId,
  }) async {
    return LessonDetailModel.fromJson({
      'lesson': _lesson(courseId, lessonId),
      'primaryVideo': null,
      'lessonResources': [],
      'artifactSummaries': [],
      'progress': {'positionSec': 0},
      'citations': [],
      'sourceOverview': {},
      'knowledgePointPlaceholders': [],
      'weaknessPlaceholders': [],
      'nextAction': null,
    });
  }

  @override
  Future<PlaceholderEntryModel> fetchCourseQaPlaceholder(
      String courseId) async {
    return const PlaceholderEntryModel(
      key: 'course_qa',
      title: '全课程 QA',
      status: 'placeholder',
      message: '暂无会话',
    );
  }

  @override
  Future<PlaceholderEntryModel> fetchLessonQaPlaceholder({
    required String courseId,
    required String lessonId,
  }) async {
    return const PlaceholderEntryModel(
      key: 'lesson_qa',
      title: '本节 QA',
      status: 'placeholder',
      message: '暂无会话',
    );
  }

  @override
  Future<PlaceholderEntryModel> fetchCourseExportPlaceholder(
      String courseId) async {
    exportPlaceholderCourseIds.add(courseId);
    return PlaceholderEntryModel(
      key: 'export',
      title: '课程导出',
      status: 'placeholder',
      message: '导出占位 $courseId',
    );
  }

  CourseLibraryItemModel _libraryItem(String courseId) {
    return CourseLibraryItemModel.fromJson({
      'courseId': courseId,
      'title': '路由工作台 $courseId',
      'isCurrent': true,
      'entryType': 'bilibili',
      'learningStatus': 'learning_ready',
      'lastActivityAt': '2026-06-01T09:30:00+08:00',
      'lessonCount': 2,
      'courseResourceCount': 0,
      'currentLessonId': 'l-2',
      'currentLessonTitle': '路由节课',
      'overallMasteryScore': 0.5,
      'pendingReviewCount': 0,
      'pipelineStage': 'handout',
      'pipelineStatus': 'succeeded',
      'lifecycleStatus': 'learning_ready',
      'archivedAt': null,
    });
  }

  Map<String, dynamic> _lesson(String courseId, String lessonId) {
    return {
      'lessonId': lessonId,
      'courseId': courseId,
      'title': '路由节课',
      'orderIndex': 1,
      'lessonStatus': 'learning_ready',
      'primaryVideoResourceId': null,
      'primaryVideoStartSec': null,
      'primaryVideoEndSec': null,
      'handoutStatus': 'not_generated',
      'quizStatus': 'not_generated',
      'reviewStatus': 'not_due',
      'masteryScore': null,
      'lastPositionSec': 0,
      'lastActivityAt': null,
      'nextAction': null,
    };
  }

  @override
  Future<PipelineStatusModel> fetchPipelineStatus(String courseId) async {
    return PipelineStatusModel.fromJson({
      'courseStatus': {
        'lifecycleStatus': 'resource_ready',
        'pipelineStage': 'parse',
        'pipelineStatus': 'queued',
      },
      'progressPct': 0,
      'steps': [],
      'activeParseRunId': null,
      'activeHandoutVersionId': null,
      'nextAction': 'poll',
    });
  }

  @override
  Future<InquiryQuestionsModel> fetchInquiryQuestions(String courseId) async {
    return InquiryQuestionsModel.fromJson({
      'version': 1,
      'questions': [],
    });
  }

  @override
  Future<QuizModel> fetchQuiz(int quizId) async {
    return QuizModel.fromJson({
      'quizId': quizId,
      'courseId': 101,
      'status': 'ready',
      'questionCount': 1,
      'questions': [
        {
          'questionId': 8101,
          'stemMd': '极限定义关注什么？',
          'options': ['A', 'B', 'C', 'D'],
        },
      ],
    });
  }

  @override
  Future<ReviewTasksModel> fetchReviewTasks(String courseId) async {
    return const ReviewTasksModel(items: []);
  }

  @override
  Future<HomeDashboardModel> fetchHomeDashboard() async {
    return HomeDashboardModel.fromJson({
      'recentCourses': [],
      'topReviewTasks': [],
      'recommendationEntryEnabled': true,
      'dailyRecommendedKnowledgePoints': [],
      'learningStats': {},
    });
  }

  @override
  Future<CourseProgressModel> fetchCourseProgress(String courseId) async {
    return CourseProgressModel.fromJson({
      'courseId': int.parse(courseId),
      'lastActivityAt': '2026-05-11T10:00:00+00:00',
    });
  }

  CourseSummaryModel _course(int courseId) {
    return CourseSummaryModel.fromJson({
      'courseId': courseId,
      'title': '路由课程 $courseId',
      'entryType': 'recommendation',
      'catalogId': 'math-final-01',
      'lifecycleStatus': 'learning_ready',
      'pipelineStage': 'handout',
      'pipelineStatus': 'succeeded',
      'updatedAt': '2026-05-25T10:00:00+08:00',
    });
  }
}
