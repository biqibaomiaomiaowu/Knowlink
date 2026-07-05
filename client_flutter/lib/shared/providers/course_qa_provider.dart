import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/handout_models.dart';
import 'course_recommend_provider.dart';

class QaScopeArgs {
  const QaScopeArgs({
    required this.courseId,
    required this.scopeType,
    this.lessonId,
  });

  final String courseId;
  final String scopeType;
  final String? lessonId;

  bool get isLesson => scopeType == 'lesson';

  @override
  bool operator ==(Object other) {
    return other is QaScopeArgs &&
        other.courseId == courseId &&
        other.scopeType == scopeType &&
        other.lessonId == lessonId;
  }

  @override
  int get hashCode => Object.hash(courseId, scopeType, lessonId);
}

class CourseQaEntry {
  const CourseQaEntry({
    required this.question,
    this.answer,
    this.errorText,
  });

  final String question;
  final QaMessageModel? answer;
  final String? errorText;

  CourseQaEntry copyWith({
    QaMessageModel? answer,
    String? errorText,
  }) {
    return CourseQaEntry(
      question: question,
      answer: answer ?? this.answer,
      errorText: errorText ?? this.errorText,
    );
  }
}

class CourseQaState {
  const CourseQaState({
    required this.sessions,
    required this.history,
    required this.entries,
    required this.submit,
    this.activeSessionId,
  });

  factory CourseQaState.initial() {
    return const CourseQaState(
      sessions: AsyncData(<QaSessionModel>[]),
      history: AsyncData(<QaMessageModel>[]),
      entries: <CourseQaEntry>[],
      submit: AsyncData(null),
    );
  }

  final AsyncValue<List<QaSessionModel>> sessions;
  final AsyncValue<List<QaMessageModel>> history;
  final List<CourseQaEntry> entries;
  final AsyncValue<QaMessageModel?> submit;
  final int? activeSessionId;

  CourseQaState copyWith({
    AsyncValue<List<QaSessionModel>>? sessions,
    AsyncValue<List<QaMessageModel>>? history,
    List<CourseQaEntry>? entries,
    AsyncValue<QaMessageModel?>? submit,
    int? activeSessionId,
    bool clearActiveSessionId = false,
  }) {
    return CourseQaState(
      sessions: sessions ?? this.sessions,
      history: history ?? this.history,
      entries: entries ?? this.entries,
      submit: submit ?? this.submit,
      activeSessionId:
          clearActiveSessionId ? null : activeSessionId ?? this.activeSessionId,
    );
  }
}

final courseQaProvider = AutoDisposeNotifierProviderFamily<CourseQaController,
    CourseQaState, QaScopeArgs>(
  CourseQaController.new,
);

class CourseQaController
    extends AutoDisposeFamilyNotifier<CourseQaState, QaScopeArgs> {
  var _sessionsRequestId = 0;
  var _historyRequestId = 0;
  var _submitRequestId = 0;

  @override
  CourseQaState build(QaScopeArgs arg) {
    return CourseQaState.initial();
  }

  Future<void> loadSessions() async {
    final requestId = ++_sessionsRequestId;
    state = state.copyWith(sessions: const AsyncLoading());
    try {
      final result = arg.isLesson
          ? await ref.read(apiClientProvider).fetchLessonQaSessions(
                courseId: arg.courseId,
                lessonId: arg.lessonId!,
              )
          : await ref.read(apiClientProvider).fetchCourseQaSessions(
                arg.courseId,
              );
      if (requestId != _sessionsRequestId) {
        return;
      }
      state = state.copyWith(sessions: AsyncData(result.items));
    } catch (error, stackTrace) {
      if (requestId != _sessionsRequestId) {
        return;
      }
      state = state.copyWith(
        sessions: AsyncError(error, stackTrace),
      );
    }
  }

  Future<void> selectSession(int sessionId) async {
    final requestId = ++_historyRequestId;
    state = state.copyWith(
      activeSessionId: sessionId,
      history: const AsyncLoading(),
      entries: const <CourseQaEntry>[],
      submit: const AsyncData(null),
    );
    try {
      final result = await ref.read(apiClientProvider).fetchQaSessionMessages(
            sessionId,
          );
      if (requestId != _historyRequestId) {
        return;
      }
      state = state.copyWith(
        history: AsyncData(result.items),
        entries: _entriesFromHistory(result.items),
      );
    } catch (error, stackTrace) {
      if (requestId != _historyRequestId) {
        return;
      }
      state = state.copyWith(
        history: AsyncError(error, stackTrace),
      );
    }
  }

  void startNewSession() {
    _historyRequestId++;
    state = state.copyWith(
      clearActiveSessionId: true,
      history: const AsyncData(<QaMessageModel>[]),
      entries: const <CourseQaEntry>[],
      submit: const AsyncData(null),
    );
  }

  Future<void> submitQuestion(String question) async {
    if (state.submit.isLoading || question.trim().isEmpty) {
      return;
    }
    final trimmedQuestion = question.trim();
    final requestId = ++_submitRequestId;
    final localEntry = CourseQaEntry(question: trimmedQuestion);
    state = state.copyWith(
      submit: const AsyncLoading(),
      entries: [...state.entries, localEntry],
    );

    try {
      final request = ScopedQaMessageRequestModel(
        question: trimmedQuestion,
        sessionId: state.activeSessionId,
        scopeType: arg.scopeType,
        courseId: arg.courseId,
        lessonId: arg.isLesson ? arg.lessonId : null,
      );
      final answer = arg.isLesson
          ? await ref.read(apiClientProvider).createLessonQaMessage(
                courseId: arg.courseId,
                lessonId: arg.lessonId!,
                request: request,
              )
          : await ref.read(apiClientProvider).createCourseQaMessage(
                courseId: arg.courseId,
                request: request,
              );
      if (requestId != _submitRequestId) {
        return;
      }
      state = state.copyWith(
        activeSessionId: answer.sessionId,
        submit: AsyncData(answer),
        entries: [
          for (final entry in state.entries)
            if (identical(entry, localEntry))
              entry.copyWith(answer: answer)
            else
              entry,
        ],
      );
      await loadSessions();
    } catch (error, stackTrace) {
      if (requestId != _submitRequestId) {
        return;
      }
      state = state.copyWith(
        submit: AsyncError(error, stackTrace),
        entries: [
          for (final entry in state.entries)
            if (identical(entry, localEntry))
              entry.copyWith(errorText: '提交失败，请稍后重试。')
            else
              entry,
        ],
      );
    }
  }

  List<CourseQaEntry> _entriesFromHistory(List<QaMessageModel> messages) {
    final entries = <CourseQaEntry>[];
    for (final message in messages) {
      final role = message.role;
      if (role == 'user') {
        final question = message.question ??
            message.contentMd ??
            (message.answerMd.isEmpty ? null : message.answerMd);
        if (question != null && question.isNotEmpty) {
          entries.add(CourseQaEntry(question: question));
        }
        continue;
      }

      final question = message.question ??
          (entries.isNotEmpty ? entries.last.question : null) ??
          message.contentMd ??
          '';
      if (question.isEmpty) {
        continue;
      }
      if (entries.isNotEmpty &&
          entries.last.answer == null &&
          entries.last.question == question) {
        entries[entries.length - 1] = entries.last.copyWith(answer: message);
      } else {
        entries.add(CourseQaEntry(question: question, answer: message));
      }
    }
    return entries;
  }
}
