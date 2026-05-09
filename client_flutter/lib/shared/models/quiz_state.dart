import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'quiz_models.dart';

class QuizState {
  const QuizState({
    required this.quiz,
    required this.generation,
    required this.status,
    required this.submission,
    required this.selectedAnswers,
    this.isPolling = false,
  });

  factory QuizState.initial() {
    return const QuizState(
      quiz: AsyncData<QuizModel?>(null),
      generation: AsyncData<QuizGenerateResultModel?>(null),
      status: AsyncData<QuizStatusModel?>(null),
      submission: AsyncData<SubmitQuizResultModel?>(null),
      selectedAnswers: <int, String>{},
    );
  }

  final AsyncValue<QuizModel?> quiz;
  final AsyncValue<QuizGenerateResultModel?> generation;
  final AsyncValue<QuizStatusModel?> status;
  final AsyncValue<SubmitQuizResultModel?> submission;
  final Map<int, String> selectedAnswers;
  final bool isPolling;

  QuizModel? get quizValue => quiz.valueOrNull;
  SubmitQuizResultModel? get submissionValue => submission.valueOrNull;
  bool get isGenerating => generation.isLoading || isPolling;
  bool get isSubmitting => submission.isLoading;
  bool get hasResult => submissionValue != null;

  bool get canSubmit {
    final currentQuiz = quizValue;
    if (currentQuiz == null || currentQuiz.questions.isEmpty || hasResult) {
      return false;
    }
    return currentQuiz.questions.every(
      (question) => selectedAnswers[question.questionId]?.isNotEmpty ?? false,
    );
  }

  QuizState copyWith({
    AsyncValue<QuizModel?>? quiz,
    AsyncValue<QuizGenerateResultModel?>? generation,
    AsyncValue<QuizStatusModel?>? status,
    AsyncValue<SubmitQuizResultModel?>? submission,
    Map<int, String>? selectedAnswers,
    bool? isPolling,
  }) {
    return QuizState(
      quiz: quiz ?? this.quiz,
      generation: generation ?? this.generation,
      status: status ?? this.status,
      submission: submission ?? this.submission,
      selectedAnswers: selectedAnswers ?? this.selectedAnswers,
      isPolling: isPolling ?? this.isPolling,
    );
  }
}
