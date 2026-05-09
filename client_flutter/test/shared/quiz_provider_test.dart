import 'dart:async';

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
    expect(fakeApiClient.fetchedQuizIds, [8001]);
    expect(state.quizValue?.questions, hasLength(2));
    expect(container.read(courseFlowProvider).quizId, 8001);
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
}

class _FakeQuizApiClient extends ApiClient {
  final generatedCourseIds = <String>[];
  final fetchedQuizIds = <int>[];
  final submittedAnswers = <SubmitQuizRequestModel>[];

  @override
  Future<QuizGenerateResultModel> generateQuiz({
    required String courseId,
    required String idempotencyKey,
  }) async {
    generatedCourseIds.add(courseId);
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
  }) async {
    generatedCourseIds.add(courseId);
    return _completer.future;
  }
}
