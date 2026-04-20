import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:knowlink_client/shared/models/course_flow_state.dart';
import 'package:knowlink_client/shared/providers/course_flow_providers.dart';

void main() {
  test('course flow defaults align with idle entry state', () {
    const state = CourseFlowState();

    expect(state.courseId, isNull);
    expect(state.lifecycleStatus, 'draft');
    expect(state.pipelineStage, 'idle');
    expect(state.pipelineStatus, 'idle');
    expect(state.progressPct, 0);
    expect(state.activeParseRunId, isNull);
    expect(state.activeHandoutVersionId, isNull);
    expect(state.nextAction, 'none');
    expect(state.sessionId, isNull);
    expect(state.quizId, isNull);
    expect(state.quizAttemptId, isNull);
    expect(state.reviewTaskRunId, isNull);
  });

  test('copyWith can explicitly clear nullable flow ids', () {
    const state = CourseFlowState(
      courseId: '101',
      activeParseRunId: 9001,
      activeHandoutVersionId: 3001,
      sessionId: 6001,
      quizId: 8001,
      quizAttemptId: 8201,
      reviewTaskRunId: 8301,
    );

    final updated = state.copyWith(
      clearActiveParseRunId: true,
      clearActiveHandoutVersionId: true,
      clearSessionId: true,
      clearQuizId: true,
      clearQuizAttemptId: true,
      clearReviewTaskRunId: true,
    );

    expect(updated.activeParseRunId, isNull);
    expect(updated.activeHandoutVersionId, isNull);
    expect(updated.sessionId, isNull);
    expect(updated.quizId, isNull);
    expect(updated.quizAttemptId, isNull);
    expect(updated.reviewTaskRunId, isNull);
  });

  test('switching to a different course keeps current flow snapshot until sync',
      () {
    final container = ProviderContainer();
    addTearDown(container.dispose);

    final notifier = container.read(courseFlowProvider.notifier);

    notifier.startCourse('101');
    notifier.setLifecycleStatus('inquiry_ready');
    notifier.setPipelineStage('handout');
    notifier.setPipelineStatus('running');
    notifier.setProgressPct(65);
    notifier.setActiveParseRun(9001);
    notifier.setActiveHandoutVersion(3001);
    notifier.setNextAction('poll');
    notifier.setSession(6001);
    notifier.setQuiz(8001);
    notifier.setQuizAttempt(8201);
    notifier.setReviewTaskRun(8301);

    notifier.startCourse('102');

    final state = container.read(courseFlowProvider);
    expect(state.courseId, '102');
    expect(state.lifecycleStatus, 'inquiry_ready');
    expect(state.pipelineStage, 'handout');
    expect(state.pipelineStatus, 'running');
    expect(state.progressPct, 65);
    expect(state.activeParseRunId, 9001);
    expect(state.activeHandoutVersionId, 3001);
    expect(state.nextAction, 'poll');
    expect(state.sessionId, 6001);
    expect(state.quizId, 8001);
    expect(state.quizAttemptId, 8201);
    expect(state.reviewTaskRunId, 8301);
  });

  test('starting the same course preserves existing flow state', () {
    final container = ProviderContainer();
    addTearDown(container.dispose);

    final notifier = container.read(courseFlowProvider.notifier);

    notifier.startCourse('101');
    notifier.setPipelineStatus('running');
    notifier.setProgressPct(40);
    notifier.setSession(6001);

    notifier.startCourse('101');

    final state = container.read(courseFlowProvider);
    expect(state.courseId, '101');
    expect(state.pipelineStatus, 'running');
    expect(state.progressPct, 40);
    expect(state.sessionId, 6001);
  });

  test('syncCreatedCourse hydrates course summary and clears downstream ids',
      () {
    final container = ProviderContainer();
    addTearDown(container.dispose);

    final notifier = container.read(courseFlowProvider.notifier);

    notifier.startCourse('101');
    notifier.setProgressPct(65);
    notifier.setActiveParseRun(9001);
    notifier.setActiveHandoutVersion(3001);
    notifier.setNextAction('poll');
    notifier.setSession(6001);
    notifier.setQuiz(8001);
    notifier.setQuizAttempt(8201);
    notifier.setReviewTaskRun(8301);

    notifier.syncCreatedCourse(
      courseId: 205,
      lifecycleStatus: 'draft',
      pipelineStage: 'idle',
      pipelineStatus: 'idle',
    );

    final state = container.read(courseFlowProvider);
    expect(state.courseId, '205');
    expect(state.lifecycleStatus, 'draft');
    expect(state.pipelineStage, 'idle');
    expect(state.pipelineStatus, 'idle');
    expect(state.progressPct, 0);
    expect(state.activeParseRunId, isNull);
    expect(state.activeHandoutVersionId, isNull);
    expect(state.nextAction, 'none');
    expect(state.sessionId, isNull);
    expect(state.quizId, isNull);
    expect(state.quizAttemptId, isNull);
    expect(state.reviewTaskRunId, isNull);
  });
}
