import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'inquiry_models.dart';

class InquiryState {
  const InquiryState({
    this.questions = const AsyncData<InquiryQuestionsModel?>(null),
    this.submitResult = const AsyncData<SaveInquiryAnswersResultModel?>(null),
    this.answers = const {},
    this.validationErrors = const {},
  });

  final AsyncValue<InquiryQuestionsModel?> questions;
  final AsyncValue<SaveInquiryAnswersResultModel?> submitResult;
  final Map<String, Object> answers;
  final Map<String, String> validationErrors;

  bool get isLoadingQuestions => questions.isLoading;
  bool get isSubmitting => submitResult.isLoading;

  InquiryState copyWith({
    AsyncValue<InquiryQuestionsModel?>? questions,
    AsyncValue<SaveInquiryAnswersResultModel?>? submitResult,
    Map<String, Object>? answers,
    Map<String, String>? validationErrors,
  }) {
    return InquiryState(
      questions: questions ?? this.questions,
      submitResult: submitResult ?? this.submitResult,
      answers: answers ?? this.answers,
      validationErrors: validationErrors ?? this.validationErrors,
    );
  }
}
