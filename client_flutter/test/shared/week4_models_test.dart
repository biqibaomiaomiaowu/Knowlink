import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/shared/models/course_progress_models.dart';
import 'package:knowlink_client/shared/models/home_dashboard_models.dart';
import 'package:knowlink_client/shared/models/quiz_models.dart';
import 'package:knowlink_client/shared/models/review_models.dart';

void main() {
  test('quiz detail parses V2 public scope and question metadata', () {
    final quiz = QuizModel.fromJson({
      'quizId': 8001,
      'courseId': 101,
      'status': 'ready',
      'questionCount': 1,
      'scopeType': 'lesson',
      'lessonId': 201,
      'startLessonId': 201,
      'endLessonId': 203,
      'quizMode': 'objective',
      'questions': [
        {
          'questionId': 8101,
          'stemMd': 'What does a derivative represent?',
          'options': ['Slope', 'Area', 'Length', 'Volume'],
          'questionType': 'single_choice',
          'knowledgePointKey': 'kp-derivative',
          'knowledgePointName': 'Derivative meaning',
          'sourceBlockKey': 'block-derivative-intro',
          'sourceSegmentKeys': ['seg-1', 'seg-2'],
        },
      ],
    });

    expect(quiz.scopeType, 'lesson');
    expect(quiz.lessonId, 201);
    expect(quiz.startLessonId, 201);
    expect(quiz.endLessonId, 203);
    expect(quiz.quizMode, 'objective');
    expect(quiz.questions.single.questionType, 'single_choice');
    expect(quiz.questions.single.knowledgePointKey, 'kp-derivative');
    expect(quiz.questions.single.knowledgePointName, 'Derivative meaning');
    expect(quiz.questions.single.sourceBlockKey, 'block-derivative-intro');
    expect(quiz.questions.single.sourceSegmentKeys, ['seg-1', 'seg-2']);
  });

  test('quiz models parse optional result details defensively', () {
    final result = SubmitQuizResultModel.fromJson({
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
    });

    expect(result.score, 80);
    expect(result.reviewTaskRunId, 8301);
    expect(result.masteryDelta.single.delta, -0.1);
    expect(result.items.single.isCorrect, isFalse);
    expect(result.items.single.selectedOption, 'A');
  });

  test('quiz submit result tolerates missing review task run', () {
    final result = SubmitQuizResultModel.fromJson({
      'attemptId': 8201,
      'score': 80,
      'totalScore': 100,
      'accuracy': 0.8,
      'reviewTaskRunId': null,
      'masteryDelta': [],
      'items': [],
    });

    expect(result.reviewTaskRunId, isNull);
    expect(result.score, 80);
  });

  test('quiz submit result parses recommended review action list', () {
    final result = SubmitQuizResultModel.fromJson({
      'attemptId': 8201,
      'score': 80,
      'totalScore': 100,
      'accuracy': 0.8,
      'reviewTaskRunId': 8301,
      'masteryDelta': [],
      'items': [],
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

    expect(result.recommendedReviewActions, hasLength(2));
    expect(result.recommendedReviewActions.first.reason, 'Review block 4001');
    expect(result.recommendedReviewAction?.reason, 'Review block 4001');
  });

  test('quiz submit result falls back to legacy singular review action', () {
    final result = SubmitQuizResultModel.fromJson({
      'attemptId': 8201,
      'score': 80,
      'totalScore': 100,
      'accuracy': 0.8,
      'reviewTaskRunId': 8301,
      'masteryDelta': [],
      'items': [],
      'recommendedReviewAction': {
        'type': 'revisit_block',
        'targetBlockId': 4001,
        'reason': 'Legacy review block',
      },
    });

    expect(result.recommendedReviewActions, hasLength(1));
    expect(result.recommendedReviewAction?.reason, 'Legacy review block');
  });

  test('review models expose top three and segment display text', () {
    final tasks = ReviewTasksModel.fromJson({
      'items': List.generate(
        4,
        (index) => {
          'reviewTaskId': 8401 + index,
          'taskType': 'revisit_block',
          'priorityScore': 95 - index,
          'reasonText': '建议优先复习',
          'recommendedMinutes': 20,
          'recommendedSegment': {
            'blockId': 4001 + index,
            'startSec': 120,
            'endSec': 240,
            'label': '建议优先回看片段',
          },
          'reviewOrder': index + 1,
          'intensity': 'high',
        },
      ),
    });

    expect(tasks.topThree, hasLength(3));
    expect(tasks.items.first.recommendedSegment?.displayText,
        '建议优先回看片段 · 2:00-4:00 · 讲义块 4001');
  });

  test('dashboard and progress models tolerate empty optional sections', () {
    final dashboard = HomeDashboardModel.fromJson({
      'recentCourses': [],
      'topReviewTasks': [],
    });
    final progress = CourseProgressModel.fromJson({
      'courseId': 101,
      'lastActivityAt': '2026-05-11T10:00:00+00:00',
    });
    const update = CourseProgressUpdateModel(
      lastHandoutBlockId: 4001,
      lastPositionSec: 180,
    );

    expect(dashboard.recommendationEntryEnabled, isTrue);
    expect(dashboard.learningStats.totalLearningMinutes, 0);
    expect(progress.hasResumeTarget, isFalse);
    expect(update.toJson(), {
      'lastHandoutBlockId': 4001,
      'lastPositionSec': 180,
    });
  });
}
