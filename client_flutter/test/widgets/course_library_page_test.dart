import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/core/network/api_client.dart';
import 'package:knowlink_client/features/course_library/course_library_page.dart';
import 'package:knowlink_client/shared/models/course_lesson_models.dart';
import 'package:knowlink_client/shared/providers/course_recommend_provider.dart';

void main() {
  testWidgets('course library displays V2 course metadata', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(_CourseLibraryFakeApiClient()),
        ],
        child: const MaterialApp(home: CourseLibraryPage()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('课程库'), findsOneWidget);
    expect(find.text('数据库系统'), findsOneWidget);
    expect(find.text('当前课程'), findsOneWidget);
    expect(find.textContaining('学习状态：learning_ready'), findsOneWidget);
    expect(find.textContaining('最近活动：2026-06-01'), findsOneWidget);
    expect(find.textContaining('节课 6'), findsOneWidget);
    expect(find.textContaining('课程资料 3'), findsOneWidget);
    expect(find.textContaining('当前节课：关系模型'), findsOneWidget);
    expect(find.textContaining('掌握度 72%'), findsOneWidget);
    expect(find.textContaining('待复习 4'), findsOneWidget);
    expect(find.textContaining('handout / running'), findsOneWidget);
  });
}

class _CourseLibraryFakeApiClient extends ApiClient {
  @override
  Future<List<CourseLibraryItemModel>> fetchCourseLibrary({
    String? query,
    String? learningStatus,
    String? source,
    String archived = 'exclude',
    String sort = 'recent_activity_desc',
  }) async {
    return [
      CourseLibraryItemModel.fromJson({
        'courseId': 101,
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
      }),
    ];
  }
}
