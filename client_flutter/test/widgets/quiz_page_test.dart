import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/core/network/api_client.dart';
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
        {'questionId': 8101, 'selectedOption': '自变量趋近与函数值趋近'},
        {'questionId': 8102, 'selectedOption': '切线斜率'},
      ],
    });
    expect(find.text('80/100'), findsOneWidget);
    expect(find.text('80%'), findsOneWidget);
    expect(find.text('极限定义'), findsOneWidget);
    expect(find.text('查看复习任务'), findsOneWidget);
    expect(find.text('待巩固'), findsOneWidget);
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

    await tester.tap(find.text('生成测验'));
    await tester.pumpAndSettle();

    expect(fakeApiClient.generatedCourseIds, ['101']);
    expect(fakeApiClient.generatedLevels, [QuizQuestionCountLevel.medium]);
    expect(fakeApiClient.fetchedQuizIds, [8001]);
    expect(find.text('极限定义关注什么？'), findsOneWidget);
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

    await tester.tap(find.text('生成测验'));
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
    await tester.tap(find.text('生成测验'));
    await tester.pumpAndSettle();

    expect(fakeApiClient.generatedCourseIds, ['101']);
    expect(fakeApiClient.generatedLevels, [QuizQuestionCountLevel.large]);
  });
}

void _useTestSurface(WidgetTester tester) {
  tester.view.physicalSize = const Size(1200, 900);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

class _QuizPageFakeApiClient extends ApiClient {
  final generatedCourseIds = <String>[];
  final generatedLevels = <QuizQuestionCountLevel>[];
  final fetchedQuizIds = <int>[];
  final submittedAnswers = <SubmitQuizRequestModel>[];

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
  Future<SubmitQuizResultModel> submitQuizAttempt({
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
          'selectedOption': '自变量趋近与函数值趋近',
          'correctAnswer': '只关注图像',
          'isCorrect': false,
          'explanationMd': '需要同时关注自变量趋近和函数值趋近。',
        },
      ],
      'recommendedReviewAction': {
        'type': 'revisit_block',
        'targetBlockId': 4001,
        'reason': '建议先回看易错知识块。',
      },
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
