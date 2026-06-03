import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/core/network/api_client.dart';
import 'package:knowlink_client/features/lesson_detail/lesson_detail_page.dart';
import 'package:knowlink_client/shared/models/course_lesson_models.dart';
import 'package:knowlink_client/shared/providers/course_recommend_provider.dart';

void main() {
  testWidgets('lesson detail shows scoped lesson learning sections',
      (tester) async {
    _useTestSurface(tester, const Size(1200, 1700));
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(_LessonDetailFakeApiClient()),
        ],
        child: const MaterialApp(
          home: LessonDetailPage(courseId: '101', lessonId: 'l-2'),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('关系模型'), findsOneWidget);
    expect(find.text('02-关系模型.mp4'), findsOneWidget);
    expect(find.text('关系模型讲义.pdf'), findsOneWidget);
    expect(find.text('本节讲义'), findsOneWidget);
    expect(find.text('本节 QA'), findsOneWidget);
    expect(find.text('本节测验'), findsOneWidget);
    expect(find.text('本节复习'), findsAtLeastNWidgets(1));
    expect(find.text('本节图谱'), findsAtLeastNWidgets(1));
    expect(find.textContaining('进度 02:05'), findsOneWidget);
    expect(find.text('PDF 第 12 页'), findsOneWidget);
    expect(find.text('知识与薄弱点'), findsOneWidget);
    expect(find.text('继续看视频'), findsOneWidget);
  });
}

void _useTestSurface(WidgetTester tester, Size size) {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

class _LessonDetailFakeApiClient extends ApiClient {
  @override
  Future<LessonDetailModel> fetchLessonDetail({
    required String courseId,
    required String lessonId,
  }) async {
    return LessonDetailModel.fromJson({
      'lesson': {
        'lessonId': lessonId,
        'courseId': courseId,
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
      },
      'primaryVideo': {
        'resourceId': 601,
        'resourceName': '02-关系模型.mp4',
        'resourceType': 'mp4',
        'durationSec': 1800,
        'startSec': 0,
        'endSec': 1800,
      },
      'lessonResources': [
        {
          'resourceId': 602,
          'courseId': courseId,
          'resourceType': 'pdf',
          'originalName': '关系模型讲义.pdf',
          'scopeType': 'lesson',
          'lessonId': lessonId,
          'usageRole': 'lesson_material',
          'visibleToCourseQa': true,
          'durationSec': null,
          'sortOrder': 2,
        },
      ],
      'artifactSummaries': [
        {
          'artifactId': 701,
          'artifactType': 'handout_version',
          'scopeType': 'lesson',
          'lessonId': lessonId,
          'status': 'ready',
        },
        {
          'artifactId': 702,
          'artifactType': 'quiz',
          'scopeType': 'lesson',
          'lessonId': lessonId,
          'status': 'not_generated',
        },
        {
          'artifactId': 703,
          'artifactType': 'review_task_run',
          'scopeType': 'lesson',
          'lessonId': lessonId,
          'status': 'generating',
        },
        {
          'artifactId': 704,
          'artifactType': 'graph_snapshot',
          'scopeType': 'lesson',
          'lessonId': lessonId,
          'status': 'placeholder',
        },
      ],
      'progress': {
        'lastPositionSec': 125,
        'handoutReadPercent': 42,
        'quizStatus': 'not_generated',
        'reviewStatus': 'due',
      },
      'citations': [
        {
          'scopeType': 'lesson',
          'lessonId': lessonId,
          'lessonTitle': '关系模型',
          'resourceId': 602,
          'resourceName': '关系模型讲义.pdf',
          'refLabel': 'PDF 第 12 页',
          'pageNo': 12,
        },
      ],
      'sourceOverview': {
        'scopeType': 'lesson',
        'lessonId': lessonId,
        'resourceCount': 2,
        'primaryVideoResourceId': 601,
      },
      'knowledgePointPlaceholders': [
        {
          'type': 'lesson_graph',
          'status': 'placeholder',
          'items': [],
        },
      ],
      'weaknessPlaceholders': [
        {
          'type': 'lesson_review',
          'status': 'placeholder',
          'items': [],
        },
      ],
      'nextAction': {
        'type': 'continue_video',
        'label': '继续看视频',
        'route': '/courses/101/lessons/l-2',
      },
    });
  }
}
