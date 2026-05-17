import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/inquiry_models.dart';
import '../models/inquiry_state.dart';
import 'course_recommend_provider.dart';

class InquiryController extends AutoDisposeNotifier<InquiryState> {
  @override
  InquiryState build() => const InquiryState();

  Future<void> fetchQuestions(String courseId) async {
    state = state.copyWith(questions: const AsyncLoading());

    try {
      final questions = await ref.read(apiClientProvider).fetchInquiryQuestions(
            courseId,
          );
      state = state.copyWith(
        questions: AsyncData(questions),
        answers: _defaultAnswersFor(questions),
        validationErrors: const {},
      );
    } catch (error, stackTrace) {
      state = state.copyWith(questions: AsyncError(error, stackTrace));
    }
  }

  void updateAnswer(String key, Object value) {
    final nextAnswers = Map<String, Object>.from(state.answers);
    nextAnswers[key] = value;
    final nextErrors = Map<String, String>.from(state.validationErrors);
    nextErrors.remove(key);
    state = state.copyWith(
      answers: nextAnswers,
      validationErrors: nextErrors,
      submitResult: const AsyncData(null),
    );
  }

  Future<void> submitAnswers(String courseId) async {
    final questions = state.questions.valueOrNull;
    if (questions == null || state.isSubmitting) {
      return;
    }

    final validationErrors = _validate(questions);
    if (validationErrors.isNotEmpty) {
      state = state.copyWith(validationErrors: validationErrors);
      return;
    }

    final answers = questions.questions
        .where((question) => state.answers.containsKey(question.key))
        .map(
          (question) => InquiryAnswerModel(
            key: question.key,
            value: state.answers[question.key]!,
          ),
        )
        .toList();

    state = state.copyWith(submitResult: const AsyncLoading());

    try {
      final result = await ref.read(apiClientProvider).saveInquiryAnswers(
            courseId: courseId,
            request: SaveInquiryAnswersRequestModel(answers: answers),
          );
      state = state.copyWith(submitResult: AsyncData(result));
    } catch (error, stackTrace) {
      state = state.copyWith(submitResult: AsyncError(error, stackTrace));
    }
  }

  Map<String, String> _validate(InquiryQuestionsModel questions) {
    final errors = <String, String>{};
    for (final question in questions.questions) {
      final value = state.answers[question.key];
      if (question.isRequired && _isBlank(value)) {
        errors[question.key] = '请完成该项';
        continue;
      }
      if (question.type == 'number' && value != null) {
        final text = value.toString().trim();
        final number = int.tryParse(text);
        if (number == null || !RegExp(r'^\d+$').hasMatch(text)) {
          errors[question.key] = '请输入整数';
        } else if (question.key == 'time_budget_minutes' &&
            (number < 10 || number > 1440)) {
          errors[question.key] = '请输入 10 到 1440 之间的整数分钟数';
        } else if (number <= 0) {
          errors[question.key] = '请输入大于 0 的整数';
        }
      }
    }
    return errors;
  }
}

final inquiryProvider =
    AutoDisposeNotifierProvider<InquiryController, InquiryState>(
  InquiryController.new,
);

Map<String, Object> _defaultAnswersFor(InquiryQuestionsModel questions) {
  final answers = <String, Object>{};
  for (final question in questions.questions) {
    if (question.type == 'single_select' && question.options.isNotEmpty) {
      answers[question.key] = question.options.first.value;
    }
  }
  return answers;
}

bool _isBlank(Object? value) {
  if (value == null) {
    return true;
  }
  if (value is String) {
    return value.trim().isEmpty;
  }
  return false;
}
