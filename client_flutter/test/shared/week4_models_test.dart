import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/shared/models/course_progress_models.dart';
import 'package:knowlink_client/shared/models/home_dashboard_models.dart';
import 'package:knowlink_client/shared/models/quiz_models.dart';
import 'package:knowlink_client/shared/models/review_models.dart';

void main() {
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
          'correctAnswer': 'B',
          'isCorrect': false,
          'explanationMd': '需要同时关注自变量趋近和函数值趋近。',
        },
      ],
    });

    expect(result.score, 80);
    expect(result.masteryDelta.single.delta, -0.1);
    expect(result.items.single.isCorrect, isFalse);
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
