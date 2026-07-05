import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/core/network/api_client.dart';
import 'package:knowlink_client/shared/models/quiz_models.dart';
import 'package:knowlink_client/shared/providers/course_flow_providers.dart';
import 'package:knowlink_client/shared/providers/course_recommend_provider.dart';
import 'package:knowlink_client/shared/providers/quiz_provider.dart';

void main() {
  test('loadQuiz fetches quiz and syncs course flow', () async {
    final fakeApiClient = _FakeQuizApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    final subscription = container.listen(quizProvider, (_, __) {});
    addTearDown(subscription.close);
    addTearDown(container.dispose);

    await container.read(quizProvider.notifier).loadQuiz(8001);

    final state = container.read(quizProvider);
    expect(state.quizValue?.quizId, 8001);
    expect(container.read(courseFlowProvider).courseId, '101');
    expect(container.read(courseFlowProvider).quizId, 8001);
  });

  test('generateAndPoll creates quiz and loads ready quiz', () async {
    final fakeApiClient = _FakeQuizApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    final subscription = container.listen(quizProvider, (_, __) {});
    addTearDown(subscription.close);
    addTearDown(container.dispose);

    await container.read(quizProvider.notifier).generateAndPoll(
          '101',
          interval: Duration.zero,
          maxAttempts: 1,
        );

    final state = container.read(quizProvider);
    expect(fakeApiClient.generatedCourseIds, ['101']);
    expect(fakeApiClient.generatedLevels, [QuizQuestionCountLevel.medium]);
    expect(fakeApiClient.fetchedQuizIds, [8001]);
    expect(state.quizValue?.questions, hasLength(2));
    expect(container.read(courseFlowProvider).quizId, 8001);
  });

  test('generateAndPoll sends selected question count level', () async {
    final fakeApiClient = _FakeQuizApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    final subscription = container.listen(quizProvider, (_, __) {});
    addTearDown(subscription.close);
    addTearDown(container.dispose);

    container
        .read(quizProvider.notifier)
        .setQuestionCountLevel(QuizQuestionCountLevel.large);
    await container.read(quizProvider.notifier).generateAndPoll(
          '101',
          interval: Duration.zero,
          maxAttempts: 1,
        );

    expect(container.read(quizProvider).questionCountLevel,
        QuizQuestionCountLevel.large);
    expect(fakeApiClient.generatedLevels, [QuizQuestionCountLevel.large]);
  });

  test('prepareCourse clears stale quiz when route course changes', () async {
    final fakeApiClient = _FakeQuizApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    final subscription = container.listen(quizProvider, (_, __) {});
    addTearDown(subscription.close);
    addTearDown(container.dispose);

    await container.read(quizProvider.notifier).loadQuiz(8001);
    container.read(quizProvider.notifier).selectAnswer(
          questionId: 8101,
          selectedOption: 'A',
        );

    container.read(quizProvider.notifier).prepareCourse('102');

    final state = container.read(quizProvider);
    expect(state.quizValue, isNull);
    expect(state.selectedAnswers, isEmpty);
    expect(container.read(courseFlowProvider).courseId, '102');
    expect(container.read(courseFlowProvider).quizId, isNull);
  });

  test('prepareLesson fetches current lesson quiz and syncs active lesson',
      () async {
    final fakeApiClient = _FakeQuizApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    final subscription = container.listen(quizProvider, (_, __) {});
    addTearDown(subscription.close);
    addTearDown(container.dispose);

    await container.read(quizProvider.notifier).prepareLesson(
          courseId: '101',
          lessonId: '42',
        );

    final state = container.read(quizProvider);
    expect(fakeApiClient.currentLessonQuizRequests, ['101/42']);
    expect(state.quizValue?.scopeType, 'lesson');
    expect(state.quizValue?.lessonId, 42);
    expect(container.read(courseFlowProvider).courseId, '101');
    expect(container.read(activeLessonProvider)?.lessonId, '42');
    expect(container.read(courseFlowProvider).quizId, 8401);
  });

  test('prepareLesson treats missing current lesson quiz as empty state',
      () async {
    final fakeApiClient = _FakeQuizApiClient()
      ..missingCurrentLessonQuiz = true;
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    final subscription = container.listen(quizProvider, (_, __) {});
    addTearDown(subscription.close);
    addTearDown(container.dispose);

    await container.read(quizProvider.notifier).prepareLesson(
          courseId: '101',
          lessonId: '42',
        );

    final state = container.read(quizProvider);
    expect(fakeApiClient.currentLessonQuizRequests, ['101/42']);
    expect(state.quizValue, isNull);
    expect(state.quiz.hasError, isFalse);
    expect(container.read(courseFlowProvider).quizId, isNull);
    expect(container.read(activeLessonProvider)?.lessonId, '42');
  });

  test('generateLessonAndPoll uses lesson scoped quiz endpoint', () async {
    final fakeApiClient = _FakeQuizApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    final subscription = container.listen(quizProvider, (_, __) {});
    addTearDown(subscription.close);
    addTearDown(container.dispose);

    container
        .read(quizProvider.notifier)
        .setQuestionCountLevel(QuizQuestionCountLevel.small);
    await container.read(quizProvider.notifier).generateLessonAndPoll(
          courseId: '101',
          lessonId: '42',
        );

    final state = container.read(quizProvider);
    expect(fakeApiClient.generatedLessonQuizRequests, ['101/42']);
    expect(fakeApiClient.generatedLevels, [QuizQuestionCountLevel.small]);
    expect(fakeApiClient.generatedCourseIds, isEmpty);
    expect(state.quizValue?.quizId, 8402);
    expect(state.quizValue?.scopeType, 'lesson');
    expect(container.read(courseFlowProvider).quizId, 8402);
  });

  test('generateAndPoll clears old quiz while new generation is pending',
      () async {
    final fakeApiClient = _SlowGenerateQuizApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    final subscription = container.listen(quizProvider, (_, __) {});
    addTearDown(subscription.close);
    addTearDown(container.dispose);

    await container.read(quizProvider.notifier).loadQuiz(8001);
    expect(container.read(quizProvider).quizValue?.quizId, 8001);

    final pending = container.read(quizProvider.notifier).generateAndPoll(
          '101',
          interval: Duration.zero,
          maxAttempts: 1,
        );
    await Future<void>.delayed(Duration.zero);

    expect(container.read(quizProvider).quizValue, isNull);
    expect(container.read(quizProvider).isGenerating, isTrue);

    fakeApiClient.completeGeneration();
    await pending;

    expect(container.read(quizProvider).quizValue?.quizId, 8001);
  });

  test('submit sends selected answers and syncs attempt and review run',
      () async {
    final fakeApiClient = _FakeQuizApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);

    await container.read(quizProvider.notifier).loadQuiz(8001);
    container.read(quizProvider.notifier)
      ..selectAnswer(questionId: 8101, selectedOption: 'A')
      ..selectAnswer(questionId: 8102, selectedOption: 'B');
    await container.read(quizProvider.notifier).submit(8001);

    final state = container.read(quizProvider);
    expect(fakeApiClient.submittedAnswers.single.toJson(), {
      'answers': [
        {'questionId': 8101, 'selectedOption': 'A'},
        {'questionId': 8102, 'selectedOption': 'B'},
      ],
    });
    expect(state.submissionValue?.score, 80);
    expect(container.read(courseFlowProvider).quizAttemptId, 8201);
    expect(container.read(courseFlowProvider).reviewTaskRunId, 8301);
  });

  test('submit keeps result when review run is absent', () async {
    final fakeApiClient = _FakeQuizApiClient()..reviewTaskRunId = null;
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);

    await container.read(quizProvider.notifier).loadQuiz(8001);
    container.read(quizProvider.notifier)
      ..selectAnswer(questionId: 8101, selectedOption: 'A')
      ..selectAnswer(questionId: 8102, selectedOption: 'B');
    await container.read(quizProvider.notifier).submit(8001);

    final state = container.read(quizProvider);
    expect(state.submissionValue?.attemptId, 8201);
    expect(state.submissionValue?.reviewTaskRunId, isNull);
    expect(container.read(courseFlowProvider).quizAttemptId, 8201);
    expect(container.read(courseFlowProvider).reviewTaskRunId, isNull);
  });
}

class _FakeQuizApiClient extends ApiClient {
  final generatedCourseIds = <String>[];
  final generatedLessonQuizRequests = <String>[];
  final currentLessonQuizRequests = <String>[];
  final generatedLevels = <QuizQuestionCountLevel>[];
  final fetchedQuizIds = <int>[];
  final submittedAnswers = <SubmitQuizRequestModel>[];
  int? reviewTaskRunId = 8301;
  bool missingCurrentLessonQuiz = false;

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
  Future<QuizModel> fetchCurrentLessonQuiz({
    required String courseId,
    required String lessonId,
  }) async {
    currentLessonQuizRequests.add('$courseId/$lessonId');
    if (missingCurrentLessonQuiz) {
      throw DioException(
        requestOptions: RequestOptions(path: '/lesson-quiz-current'),
        response: Response<Map<String, dynamic>>(
          requestOptions: RequestOptions(path: '/lesson-quiz-current'),
          statusCode: 404,
          data: {'errorCode': 'quiz.not_found'},
        ),
      );
    }
    return _lessonQuiz(8401, courseId, lessonId);
  }

  @override
  Future<QuizModel> generateLessonQuiz({
    required String courseId,
    required String lessonId,
    required QuizQuestionCountLevel questionCountLevel,
  }) async {
    generatedLessonQuizRequests.add('$courseId/$lessonId');
    generatedLevels.add(questionCountLevel);
    return _lessonQuiz(8402, courseId, lessonId);
  }

  @override
  Future<QuizModel> fetchQuiz(int quizId) async {
    fetchedQuizIds.add(quizId);
    return QuizModel.fromJson({
      'quizId': quizId,
      'courseId': 101,
      'status': 'ready',
      'questionCount': 2,
      'questions': [
        {
          'questionId': 8101,
          'stemMd': '极限定义关注什么？',
          'options': ['A', 'B'],
        },
        {
          'questionId': 8102,
          'stemMd': '导数的几何意义是？',
          'options': ['A', 'B'],
        },
      ],
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
          'stemMd': '课时测验题',
          'options': ['A', 'B'],
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
      'reviewTaskRunId': reviewTaskRunId,
      'masteryDelta': [
        {'knowledgePoint': '极限定义', 'delta': 0.1, 'status': 'improved'},
      ],
    });
  }
}

class _SlowGenerateQuizApiClient extends _FakeQuizApiClient {
  final _completer = Completer<QuizGenerateResultModel>();

  void completeGeneration() {
    _completer.complete(
      QuizGenerateResultModel.fromJson({
        'taskId': 9001,
        'status': 'queued',
        'nextAction': 'poll',
        'entity': {'type': 'quiz', 'id': 8001},
      }),
    );
  }

  @override
  Future<QuizGenerateResultModel> generateQuiz({
    required String courseId,
    required String idempotencyKey,
    required QuizQuestionCountLevel questionCountLevel,
  }) async {
    generatedCourseIds.add(courseId);
    generatedLevels.add(questionCountLevel);
    return _completer.future;
  }
}
