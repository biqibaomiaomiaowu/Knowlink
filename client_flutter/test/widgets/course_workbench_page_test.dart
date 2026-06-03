import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/core/network/api_client.dart';
import 'package:knowlink_client/features/course_workbench/course_workbench_page.dart';
import 'package:knowlink_client/shared/models/course_lesson_models.dart';
import 'package:knowlink_client/shared/providers/course_recommend_provider.dart';

void main() {
  testWidgets('course workbench shows aggregate read model entries',
      (tester) async {
    _useTestSurface(tester, const Size(1200, 1600));
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(_CourseWorkbenchFakeApiClient()),
        ],
        child: const MaterialApp(
          home: CourseWorkbenchPage(courseId: '101'),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('数据库系统'), findsOneWidget);
    expect(find.textContaining('进度 33%'), findsOneWidget);
    expect(find.text('第 2 课'), findsOneWidget);
    expect(find.text('关系模型'), findsOneWidget);
    expect(find.text('数据库教材.pdf'), findsOneWidget);
    expect(find.text('全课程 QA'), findsOneWidget);
    expect(find.text('课程图谱'), findsOneWidget);
    expect(find.text('综合测验'), findsOneWidget);
    expect(find.text('课程总复习'), findsOneWidget);
    expect(find.text('学习报告'), findsOneWidget);
    expect(find.text('课程导出'), findsOneWidget);
    expect(find.text('课程设置'), findsOneWidget);
    expect(find.text('继续学习关系模型'), findsOneWidget);
  });
}

void _useTestSurface(WidgetTester tester, Size size) {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

class _CourseWorkbenchFakeApiClient extends ApiClient {
  @override
  Future<CourseWorkbenchModel> fetchCourseWorkbench(String courseId) async {
    return CourseWorkbenchModel.fromJson({
      'course': {
        'courseId': courseId,
        'title': '数据库系统',
        'isCurrent': true,
        'entryType': 'bilibili',
        'learningStatus': 'learning_ready',
        'lastActivityAt': '2026-06-01T09:30:00+08:00',
        'lessonCount': 6,
        'courseResourceCount': 3,
        'currentLessonId': 'l-2',
        'currentLessonTitle': '关系模型',
        'overallMasteryScore': 0.72,
        'pendingReviewCount': 4,
        'pipelineStage': 'handout',
        'pipelineStatus': 'running',
        'lifecycleStatus': 'learning_ready',
        'archivedAt': null,
      },
      'progress': {
        'completedLessonCount': 2,
        'totalLessonCount': 6,
        'progressPct': 33,
        'lastPositionSec': 125,
      },
      'currentLesson': _lesson(),
      'lessons': [_lesson()],
      'courseResources': [
        {
          'resourceId': 501,
          'courseId': courseId,
          'resourceType': 'pdf',
          'originalName': '数据库教材.pdf',
          'scopeType': 'course',
          'lessonId': null,
          'usageRole': 'course_material',
          'visibleToCourseQa': true,
          'durationSec': null,
          'sortOrder': 1,
        },
      ],
      'quickEntries': [
        {
          'key': 'course_qa',
          'title': '全课程 QA',
          'status': 'ready',
          'message': '基于全部节课提问',
        },
        {
          'key': 'course_graph',
          'title': '课程图谱',
          'status': 'placeholder',
          'message': '图谱生成暂未启用',
        },
        {
          'key': 'comprehensive_quiz',
          'title': '综合测验',
          'status': 'placeholder',
          'message': '综合测验等待生成',
        },
        {
          'key': 'course_review',
          'title': '课程总复习',
          'status': 'generating',
          'message': '复习计划生成中',
        },
        {
          'key': 'report',
          'title': '学习报告',
          'status': 'placeholder',
          'message': '报告暂未启用',
        },
        {
          'key': 'export',
          'title': '课程导出',
          'status': 'placeholder',
          'message': '导出暂未启用',
        },
        {
          'key': 'settings',
          'title': '课程设置',
          'status': 'ready',
          'message': '调整课程信息',
        },
      ],
      'nextActions': [
        {
          'type': 'continue_lesson',
          'lessonId': 'l-2',
          'title': '关系模型',
        },
      ],
      'placeholderStates': {},
    });
  }

  Map<String, dynamic> _lesson() {
    return {
      'lessonId': 'l-2',
      'courseId': 101,
      'title': '关系模型',
      'orderIndex': 2,
      'lessonStatus': 'learning_ready',
      'primaryVideoResourceId': 601,
      'primaryVideoStartSec': 0,
      'primaryVideoEndSec': 1800,
      'handoutStatus': 'ready',
      'quizStatus': 'not_generated',
      'reviewStatus': 'due',
      'masteryScore': 0.64,
      'lastPositionSec': 125,
      'lastActivityAt': '2026-06-01T09:30:00+08:00',
      'nextAction': {
        'type': 'resume_video',
        'label': '继续看视频',
        'route': '/courses/101/lessons/l-2',
        'reason': '上次看到 02:05',
      },
    };
  }
}
