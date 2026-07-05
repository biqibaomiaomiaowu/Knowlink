import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:knowlink_client/core/network/api_client.dart';
import 'package:knowlink_client/features/quiz/quiz_history_page.dart';
import 'package:knowlink_client/features/quiz/quiz_page.dart';
import 'package:knowlink_client/shared/models/quiz_models.dart';
import 'package:knowlink_client/shared/providers/course_recommend_provider.dart';

void main() {
  testWidgets('quiz page loads, submits answers, and renders result', (
    tester,
  ) async {
    _useTestSurface(tester);
    final fakeApiClient = _QuizPageFakeApiClient();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(fakeApiClient),
        ],
        child: const MaterialApp(home: QuizPage(quizId: '8001')),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('测验编号：8001'), findsOneWidget);
    expect(find.text('极限定义关注什么？'), findsOneWidget);
    expect(find.text('导数的几何意义是？'), findsOneWidget);
    expect(find.text('提交答案'), findsOneWidget);

    await tester.tap(find.text('自变量趋近与函数值趋近'));
    await tester.tap(find.text('切线斜率'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('提交答案'));
    await tester.pumpAndSettle();

    expect(fakeApiClient.submittedAnswers.single.toJson(), {
      'answers': [
        {'questionId': 8101, 'selectedOption': 'A'},
        {'questionId': 8102, 'selectedOption': 'A'},
      ],
    });
    expect(find.text('自变量趋近与函数值趋近'), findsOneWidget);
    expect(find.text('切线斜率'), findsOneWidget);
    expect(find.text('80/100'), findsOneWidget);
    expect(find.text('80%'), findsOneWidget);
    expect(find.text('极限定义'), findsOneWidget);
    expect(find.text('查看复习任务'), findsOneWidget);
    expect(find.text('待巩固'), findsOneWidget);
    expect(find.text('Review block 4001'), findsOneWidget);
    expect(find.text('Practice similar questions'), findsOneWidget);
  });

  testWidgets('quiz center shows supported objective test scopes', (
    tester,
  ) async {
    _useTestSurface(tester);
    final fakeApiClient = _QuizPageFakeApiClient();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(fakeApiClient),
        ],
        child: const MaterialApp(home: QuizPage(courseId: '101')),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('测试中心'), findsWidgets);
    expect(find.text('课程测试'), findsOneWidget);
    expect(find.text('课时测试'), findsNothing);
    expect(find.text('阶段测试'), findsNothing);
    expect(find.text('综合测试'), findsNothing);
    expect(find.text('主观题' '判卷'), findsNothing);
  });

  testWidgets('lesson quiz route preselects lesson test scope', (
    tester,
  ) async {
    _useTestSurface(tester);
    final fakeApiClient = _QuizPageFakeApiClient();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(fakeApiClient),
        ],
        child: const MaterialApp(
          home: QuizPage(courseId: '101', lessonId: '42'),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(fakeApiClient.currentLessonQuizRequests, ['101/42']);
    expect(find.text('当前入口：课时测试'), findsOneWidget);
    expect(find.text('课时编号：42'), findsOneWidget);

    await tester.tap(find.text('生成课时测试'));
    await tester.pumpAndSettle();

    expect(fakeApiClient.generatedLessonQuizRequests, ['101/42']);
    expect(fakeApiClient.generatedCourseIds, isEmpty);
  });

  testWidgets('course quiz page can generate a quiz', (tester) async {
    _useTestSurface(tester);
    final fakeApiClient = _QuizPageFakeApiClient();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(fakeApiClient),
        ],
        child: const MaterialApp(home: QuizPage(courseId: '101')),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('还没有测验'), findsOneWidget);
    expect(find.text('适中 3-5题'), findsOneWidget);

    await tester.tap(find.text('生成课程测试'));
    await tester.pumpAndSettle();

    expect(fakeApiClient.generatedCourseIds, ['101']);
    expect(fakeApiClient.generatedLevels, [QuizQuestionCountLevel.medium]);
    expect(fakeApiClient.fetchedQuizIds, [8001]);
    expect(find.text('极限定义关注什么？'), findsOneWidget);
  });

  testWidgets('course quiz page auto regenerates once for regenerate route', (
    tester,
  ) async {
    _useTestSurface(tester);
    final fakeApiClient = _QuizPageFakeApiClient();

    Widget buildPage() {
      return ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(fakeApiClient),
        ],
        child: const MaterialApp(
          home: QuizPage(courseId: '101', autoRegenerate: true),
        ),
      );
    }

    await tester.pumpWidget(buildPage());
    await tester.pumpAndSettle();
    await tester.pumpWidget(buildPage());
    await tester.pumpAndSettle();

    expect(fakeApiClient.generatedCourseIds, ['101']);
    expect(fakeApiClient.fetchedQuizIds, [8001]);
  });

  testWidgets('quiz history page opens selected quiz detail route', (
    tester,
  ) async {
    _useTestSurface(tester);
    final fakeApiClient = _QuizPageFakeApiClient();
    final router = GoRouter(
      initialLocation: '/courses/101/quizzes',
      routes: [
        GoRoute(
          path: '/courses/:courseId/quizzes',
          builder: (context, state) => CourseQuizHistoryPage(
            courseId: state.pathParameters['courseId']!,
          ),
        ),
        GoRoute(
          path: '/quizzes/:quizId',
          builder: (context, state) => Text(
            'quiz-detail ${state.pathParameters['quizId']}',
          ),
        ),
      ],
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(fakeApiClient),
        ],
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();

    expect(fakeApiClient.historyCourseIds, ['101']);
    expect(find.textContaining('8001'), findsWidgets);

    await tester.tap(find.textContaining('8001').first);
    await tester.pumpAndSettle();

    expect(find.text('quiz-detail 8001'), findsOneWidget);
  });

  testWidgets('course quiz page keeps generate disabled while polling', (
    tester,
  ) async {
    _useTestSurface(tester);
    final fakeApiClient = _PollingQuizPageFakeApiClient();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(fakeApiClient),
        ],
        child: const MaterialApp(home: QuizPage(courseId: '101')),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('生成课程测试'));
    await tester.pump();

    expect(fakeApiClient.generatedCourseIds, ['101']);
    expect(fakeApiClient.fetchedQuizIds, [8001]);
    var button = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, '生成中'),
    );
    expect(button.onPressed, isNull);

    await tester.pump(const Duration(milliseconds: 700));

    button = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, '生成中'),
    );
    expect(button.onPressed, isNull);
    expect(fakeApiClient.generatedCourseIds, ['101']);

    fakeApiClient.markReady();
    await tester.pump(const Duration(seconds: 2));
    await tester.pumpAndSettle();

    expect(find.text('极限定义关注什么？'), findsOneWidget);
  });

  testWidgets('course quiz page sends selected question count level', (
    tester,
  ) async {
    _useTestSurface(tester);
    final fakeApiClient = _QuizPageFakeApiClient();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(fakeApiClient),
        ],
        child: const MaterialApp(home: QuizPage(courseId: '101')),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('多练 5-10题'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('生成课程测试'));
    await tester.pumpAndSettle();

    expect(fakeApiClient.generatedCourseIds, ['101']);
    expect(fakeApiClient.generatedLevels, [QuizQuestionCountLevel.large]);
  });
}

void _useTestSurface(WidgetTester tester) {
  tester.view.physicalSize = const Size(1200, 1200);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

class _QuizPageFakeApiClient extends ApiClient {
  final generatedCourseIds = <String>[];
  final generatedLessonQuizRequests = <String>[];
  final currentLessonQuizRequests = <String>[];
  final generatedLevels = <QuizQuestionCountLevel>[];
  final fetchedQuizIds = <int>[];
  final submittedAnswers = <SubmitQuizRequestModel>[];
  final historyCourseIds = <String>[];

  @override
  Future<QuizGenerateResultModel> generateQuiz({
    required String courseId,
    required String idempotencyKey,
    required QuizQuestionCountLevel questionCountLevel,
  }) async {
    generatedCourseIds.add(courseId);
    generatedLevels.add(questionCountLevel);
    return QuizGenerateResultModel.fromJson({
      'taskId': 9001,
      'status': 'queued',
      'nextAction': 'poll',
      'entity': {'type': 'quiz', 'id': 8001},
    });
  }

  @override
  Future<QuizModel> fetchQuiz(int quizId) async {
    fetchedQuizIds.add(quizId);
    if (quizId >= 8400) {
      return _lessonQuiz(quizId, '101', '42');
    }
    return _readyQuiz(quizId);
  }

  QuizModel _readyQuiz(int quizId) {
    return QuizModel.fromJson({
      'quizId': quizId,
      'courseId': 101,
      'status': 'ready',
      'questionCount': 2,
      'questions': [
        {
          'questionId': 8101,
          'stemMd': '极限定义关注什么？',
          'options': ['自变量趋近与函数值趋近', '只关注图像'],
        },
        {
          'questionId': 8102,
          'stemMd': '导数的几何意义是？',
          'options': ['切线斜率', '曲线面积'],
        },
      ],
    });
  }

  @override
  Future<List<CourseQuizHistoryItemModel>> fetchCourseQuizHistory(
    String courseId,
  ) async {
    historyCourseIds.add(courseId);
    return [
      CourseQuizHistoryItemModel.fromJson({
        'quizId': 8001,
        'courseId': int.parse(courseId),
        'scopeType': 'course',
        'lessonId': null,
        'status': 'ready',
        'quizMode': 'objective',
        'questionCount': 2,
        'createdAt': '2026-07-01T10:00:00Z',
        'updatedAt': '2026-07-01T10:02:00Z',
        'latestAttempt': {
          'attemptId': 8201,
          'score': 80,
          'totalScore': 100,
          'accuracy': 0.8,
          'createdAt': '2026-07-01T10:05:00Z',
        },
      }),
      CourseQuizHistoryItemModel.fromJson({
        'quizId': 8002,
        'courseId': int.parse(courseId),
        'scopeType': 'lesson',
        'lessonId': 42,
        'status': 'ready',
        'quizMode': 'objective',
        'questionCount': 1,
        'createdAt': '2026-07-01T11:00:00Z',
        'updatedAt': '2026-07-01T11:02:00Z',
        'latestAttempt': null,
      }),
    ];
  }

  @override
  Future<QuizModel> fetchCurrentLessonQuiz({
    required String courseId,
    required String lessonId,
  }) async {
    currentLessonQuizRequests.add('$courseId/$lessonId');
    return _lessonQuiz(8401, courseId, lessonId);
  }

  @override
  Future<QuizGenerateResultModel> generateLessonQuiz({
    required String courseId,
    required String lessonId,
    required String idempotencyKey,
    required QuizQuestionCountLevel questionCountLevel,
  }) async {
    expect(idempotencyKey,
        startsWith('quiz-generate-lesson-$courseId-$lessonId-'));
    generatedLessonQuizRequests.add('$courseId/$lessonId');
    generatedLevels.add(questionCountLevel);
    return QuizGenerateResultModel.fromJson({
      'taskId': 9402,
      'status': 'queued',
      'nextAction': 'poll',
      'entity': {'type': 'quiz', 'id': 8402},
    });
  }

  QuizModel _lessonQuiz(int quizId, String courseId, String lessonId) {
    return QuizModel.fromJson({
      'quizId': quizId,
      'courseId': int.parse(courseId),
      'scopeType': 'lesson',
      'lessonId': int.parse(lessonId),
      'status': 'ready',
      'questionCount': 1,
      'questions': [
        {
          'questionId': 84010,
          'stemMd': '课时测试题',
          'options': ['A', 'B'],
        },
      ],
    });
  }

  @override
  Future<SubmitQuizResultModel> submitQuiz({
    required int quizId,
    required SubmitQuizRequestModel request,
  }) async {
    submittedAnswers.add(request);
    return SubmitQuizResultModel.fromJson({
      'attemptId': 8201,
      'score': 80,
      'totalScore': 100,
      'accuracy': 0.8,
      'reviewTaskRunId': 8301,
      'masteryDelta': [
        {'knowledgePoint': '极限定义', 'delta': -0.1, 'status': 'weakened'},
      ],
      'items': [
        {
          'questionId': 8101,
          'selectedOption': 'A',
          'isCorrect': false,
          'explanationMd': '需要同时关注自变量趋近和函数值趋近。',
        },
      ],
      'recommendedReviewActions': [
        {
          'type': 'revisit_block',
          'targetBlockId': 4001,
          'reason': 'Review block 4001',
        },
        {
          'type': 'practice_questions',
          'targetId': 5001,
          'reason': 'Practice similar questions',
        },
      ],
    });
  }
}

class _PollingQuizPageFakeApiClient extends _QuizPageFakeApiClient {
  var _ready = false;

  void markReady() {
    _ready = true;
  }

  @override
  Future<QuizModel> fetchQuiz(int quizId) async {
    fetchedQuizIds.add(quizId);
    if (_ready) {
      return _readyQuiz(quizId);
    }
    return QuizModel.fromJson({
      'quizId': quizId,
      'courseId': 101,
      'status': 'generating',
      'questionCount': 0,
      'questions': [],
    });
  }
}
