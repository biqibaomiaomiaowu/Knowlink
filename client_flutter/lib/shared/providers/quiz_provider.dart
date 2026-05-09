import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/quiz_models.dart';
import '../models/quiz_state.dart';
import 'course_flow_providers.dart';
import 'course_recommend_provider.dart';

class QuizController extends AutoDisposeNotifier<QuizState> {
  var _isDisposed = false;
  var _latestRequestId = 0;
  String? _activeCourseId;

  @override
  QuizState build() {
    _isDisposed = false;
    ref.onDispose(() {
      _isDisposed = true;
    });
    return QuizState.initial();
  }

  void prepareCourse(String courseId) {
    if (_activeCourseId == courseId &&
        state.quizValue == null &&
        !state.isGenerating) {
      return;
    }
    _activeCourseId = courseId;
    _latestRequestId++;
    ref.read(courseFlowProvider.notifier).startCourse(courseId);
    state = QuizState.initial();
  }

  Future<void> loadQuiz(int quizId) async {
    final requestId = ++_latestRequestId;
    state = state.copyWith(
      quiz: const AsyncLoading(),
      submission: const AsyncData<SubmitQuizResultModel?>(null),
      selectedAnswers: const <int, String>{},
      isPolling: false,
    );

    try {
      final quiz = await ref.read(apiClientProvider).fetchQuiz(quizId);
      if (!_shouldApply(requestId)) {
        return;
      }
      _activeCourseId = quiz.courseId.toString();
      ref.read(courseFlowProvider.notifier)
        ..startCourse(quiz.courseId.toString())
        ..setQuiz(quiz.quizId);
      state = state.copyWith(quiz: AsyncData(quiz));
    } catch (error, stackTrace) {
      if (!_shouldApply(requestId)) {
        return;
      }
      state = state.copyWith(quiz: AsyncError(error, stackTrace));
    }
  }

  Future<void> generateAndPoll(
    String courseId, {
    Duration interval = const Duration(seconds: 2),
    int maxAttempts = 30,
  }) async {
    if (state.isGenerating) {
      return;
    }
    final requestId = ++_latestRequestId;
    _activeCourseId = courseId;
    state = state.copyWith(
      quiz: const AsyncData<QuizModel?>(null),
      generation: const AsyncLoading(),
      status: const AsyncData<QuizStatusModel?>(null),
      submission: const AsyncData<SubmitQuizResultModel?>(null),
      selectedAnswers: const <int, String>{},
      isPolling: true,
    );

    try {
      final result = await ref.read(apiClientProvider).generateQuiz(
            courseId: courseId,
            idempotencyKey:
                'quiz-generate-$courseId-${DateTime.now().microsecondsSinceEpoch}',
          );
      if (!_shouldApply(requestId, courseId: courseId)) {
        return;
      }
      ref.read(courseFlowProvider.notifier).setQuiz(
            result.entity.type == 'quiz' ? result.entity.id : null,
          );
      state = state.copyWith(generation: AsyncData(result));

      if (result.entity.type != 'quiz') {
        return;
      }

      final quizId = result.entity.id;
      QuizModel? latestQuiz;
      for (var attempt = 0; attempt < maxAttempts; attempt++) {
        if (!_shouldApply(requestId, courseId: courseId)) {
          return;
        }
        latestQuiz = await ref.read(apiClientProvider).fetchQuiz(quizId);
        if (!_shouldApply(requestId, courseId: courseId)) {
          return;
        }
        state = state.copyWith(
          status: AsyncData(QuizStatusModel.fromQuiz(latestQuiz)),
        );
        if (latestQuiz.isReady || latestQuiz.status == 'failed') {
          break;
        }
        await Future<void>.delayed(interval);
      }

      if (latestQuiz?.isReady ?? false) {
        state = state.copyWith(quiz: AsyncData(latestQuiz));
      }
    } catch (error, stackTrace) {
      if (!_shouldApply(requestId, courseId: courseId)) {
        return;
      }
      state = state.copyWith(
        generation: AsyncError(error, stackTrace),
      );
    } finally {
      if (_shouldApply(requestId, courseId: courseId)) {
        state = state.copyWith(isPolling: false);
      }
    }
  }

  void selectAnswer({
    required int questionId,
    required String selectedOption,
  }) {
    if (state.hasResult) {
      return;
    }
    state = state.copyWith(
      selectedAnswers: {
        ...state.selectedAnswers,
        questionId: selectedOption,
      },
    );
  }

  Future<void> submit(int quizId) async {
    if (!state.canSubmit || state.isSubmitting) {
      return;
    }
    final requestId = ++_latestRequestId;
    state = state.copyWith(submission: const AsyncLoading());

    final request = SubmitQuizRequestModel(
      answers: [
        for (final entry in state.selectedAnswers.entries)
          QuizAnswerModel(
            questionId: entry.key,
            selectedOption: entry.value,
          ),
      ],
    );

    try {
      final result = await ref.read(apiClientProvider).submitQuizAttempt(
            quizId: quizId,
            request: request,
          );
      if (!_shouldApply(requestId)) {
        return;
      }
      ref.read(courseFlowProvider.notifier)
        ..setQuizAttempt(result.attemptId)
        ..setReviewTaskRun(result.reviewTaskRunId);
      state = state.copyWith(submission: AsyncData(result));
    } catch (error, stackTrace) {
      if (!_shouldApply(requestId)) {
        return;
      }
      state = state.copyWith(submission: AsyncError(error, stackTrace));
    }
  }

  bool _shouldApply(int requestId, {String? courseId}) {
    return !_isDisposed &&
        requestId == _latestRequestId &&
        (courseId == null || _activeCourseId == courseId);
  }
}

final quizProvider =
    AutoDisposeNotifierProvider<QuizController, QuizState>(QuizController.new);
