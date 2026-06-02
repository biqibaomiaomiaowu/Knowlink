import 'package:flutter/material.dart';

import '../../app/theme/app_theme.dart';
import '../../core/widgets/app_scaffold.dart';
import '../../core/widgets/knowlink_widgets.dart';

class CourseReviewPage extends StatelessWidget {
  const CourseReviewPage({
    required this.courseId,
    this.lessonId,
    this.kind = CourseReviewPageKind.courseReview,
    super.key,
  });

  final String courseId;
  final String? lessonId;
  final CourseReviewPageKind kind;

  @override
  Widget build(BuildContext context) {
    final title = switch (kind) {
      CourseReviewPageKind.lessonHandout => '本节讲义',
      CourseReviewPageKind.lessonReview => '本节复习',
      CourseReviewPageKind.comprehensiveQuiz => '综合测验',
      CourseReviewPageKind.subjectiveGrading => '主观题判卷',
      CourseReviewPageKind.report => '学习报告',
      CourseReviewPageKind.courseReview => '课程总复习',
    };
    final status = switch (kind) {
      CourseReviewPageKind.lessonHandout => 'not_generated',
      CourseReviewPageKind.comprehensiveQuiz => 'not_generated',
      CourseReviewPageKind.subjectiveGrading => 'not_supported',
      CourseReviewPageKind.report => 'placeholder',
      _ => 'generating',
    };
    final message = switch (kind) {
      CourseReviewPageKind.lessonHandout => '本节讲义入口已预留，生成状态以后端返回为准。',
      CourseReviewPageKind.lessonReview => '本节复习计划生成中或等待触发。',
      CourseReviewPageKind.comprehensiveQuiz => '综合测验入口已预留，题目生成状态以后端返回为准。',
      CourseReviewPageKind.subjectiveGrading => '主观题自动判卷本轮仅保留入口。',
      CourseReviewPageKind.report => '学习报告 read model 本轮仅保留占位状态。',
      CourseReviewPageKind.courseReview => '课程总复习入口已接入，等待后端复习任务状态。',
    };
    return AppScaffold(
      title: title,
      activeTab: KnowLinkTab.review,
      courseId: courseId,
      body: ListView(
        children: [
          PageTitle(
            title: title,
            subtitle:
                lessonId == null ? 'course:$courseId' : 'lesson:$lessonId',
            icon: Icons.refresh,
          ),
          SectionCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                StatusPill(label: status),
                const SizedBox(height: 14),
                Text(
                  message,
                  style: const TextStyle(
                    color: AppTheme.muted,
                    fontWeight: FontWeight.w700,
                    height: 1.45,
                  ),
                ),
                const SizedBox(height: 16),
                const Text('不会调用未支持的 AI 生成或判卷后端。'),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

enum CourseReviewPageKind {
  courseReview,
  lessonHandout,
  lessonReview,
  comprehensiveQuiz,
  subjectiveGrading,
  report,
}

CourseReviewPageKind courseReviewPageKindFromQuery(String? value) {
  return switch (value) {
    'comprehensive_quiz' => CourseReviewPageKind.comprehensiveQuiz,
    'subjective_grading' => CourseReviewPageKind.subjectiveGrading,
    'report' => CourseReviewPageKind.report,
    _ => CourseReviewPageKind.courseReview,
  };
}
