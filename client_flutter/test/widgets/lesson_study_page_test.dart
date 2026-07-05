import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:knowlink_client/core/network/api_client.dart';
import 'package:knowlink_client/features/lesson_study/lesson_study_page.dart';
import 'package:knowlink_client/shared/models/course_lesson_models.dart';
import 'package:knowlink_client/shared/models/handout_models.dart' as handouts;
import 'package:knowlink_client/shared/models/resource_upload_models.dart'
    as resources;
import 'package:knowlink_client/shared/providers/course_recommend_provider.dart';

void main() {
  testWidgets('lesson study page matches prototype structure', (tester) async {
    _useTestSurface(tester);
    await _pumpLessonStudy(tester);

    expect(find.text('本节资料'), findsOneWidget);
    expect(find.text('进入测试'), findsOneWidget);
    expect(find.text('加入复习'), findsNothing);
    expect(find.text('生成讲义'), findsWidgets);
    expect(find.text('根据资料生成讲义'), findsNothing);
    expect(find.byKey(const Key('lesson_study_video_panel')), findsOneWidget);
    expect(find.byKey(const Key('lesson_study_ai_panel')), findsOneWidget);
    expect(find.byKey(const Key('lesson_study_block_panel')), findsOneWidget);
  });

  testWidgets('lesson outline drawer opens from left trigger', (tester) async {
    _useTestSurface(tester);
    await _pumpLessonStudy(tester);

    expect(find.byKey(const Key('lesson_outline_drawer')), findsNothing);

    await tester.tap(find.byTooltip('讲义目录'));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('lesson_outline_drawer')), findsOneWidget);
    expect(find.text('第一章'), findsOneWidget);
    expect(
      find.descendant(
        of: find.byKey(const Key('lesson_outline_drawer')),
        matching: find.text('1.1 极限定义'),
      ),
      findsOneWidget,
    );
  });

  testWidgets('lesson materials open in blurred dialog', (tester) async {
    _useTestSurface(tester);
    await _pumpLessonStudy(tester);

    await tester.tap(find.text('本节资料'));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('lesson_materials_dialog')), findsOneWidget);
    expect(find.byType(BackdropFilter), findsWidgets);
    expect(find.text('本节资料'), findsWidgets);
    expect(
      find.descendant(
        of: find.byKey(const Key('lesson_materials_dialog')),
        matching: find.text('01-栈与队列.mp4'),
      ),
      findsOneWidget,
    );
  });

  testWidgets('enter test action routes to lesson quiz context', (tester) async {
    _useTestSurface(tester);
    await _pumpLessonStudy(tester);

    await tester.tap(find.text('进入测试'));
    await tester.pumpAndSettle();

    expect(find.text('lesson quiz 101/42'), findsOneWidget);
  });
}

Future<void> _pumpLessonStudy(WidgetTester tester) async {
  final router = GoRouter(
    initialLocation: '/',
    routes: [
      GoRoute(
        path: '/',
        builder: (context, state) => const LessonStudyPage(
          courseId: '101',
          lessonId: '42',
        ),
      ),
      GoRoute(
        path: '/courses/:courseId/lessons/:lessonId/quiz',
        builder: (context, state) => Text(
          'lesson quiz ${state.pathParameters['courseId']}/'
          '${state.pathParameters['lessonId']}',
        ),
      ),
    ],
  );

  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        apiClientProvider.overrideWithValue(_LessonStudyPageFakeApiClient()),
      ],
      child: MaterialApp.router(routerConfig: router),
    ),
  );
  await tester.pumpAndSettle();
}

void _useTestSurface(WidgetTester tester) {
  tester.view.physicalSize = const Size(1448, 1086);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

class _LessonStudyPageFakeApiClient extends ApiClient {
  @override
  Future<LessonDetailModel> fetchLessonDetail({
    required String courseId,
    required String lessonId,
  }) async {
    return LessonDetailModel.fromJson({
      'lesson': {
        'lessonId': lessonId,
        'courseId': courseId,
        'title': '第 1 课：栈与队列',
        'orderIndex': 1,
        'lessonStatus': 'learning_ready',
        'primaryVideoResourceId': 501,
        'primaryVideoStartSec': 0,
        'primaryVideoEndSec': 2700,
        'handoutStatus': 'ready',
        'quizStatus': 'not_generated',
        'reviewStatus': 'not_due',
        'masteryScore': 0.52,
        'lastPositionSec': 128,
      },
      'primaryVideo': {
        'resourceId': 501,
        'resourceName': '01-栈与队列.mp4',
        'resourceType': 'mp4',
        'durationSec': 2700,
        'startSec': 0,
        'endSec': 2700,
      },
      'lessonResources': [
        {
          'resourceId': 501,
          'courseId': courseId,
          'resourceType': 'mp4',
          'originalName': '01-栈与队列.mp4',
          'scopeType': 'lesson',
          'lessonId': lessonId,
          'usageRole': 'primary_video',
          'visibleToCourseQa': true,
          'durationSec': 2700,
          'sortOrder': 1,
        },
        {
          'resourceId': 502,
          'courseId': courseId,
          'resourceType': 'pdf',
          'originalName': '栈与队列讲义.pdf',
          'scopeType': 'lesson',
          'lessonId': lessonId,
          'usageRole': 'lesson_material',
          'visibleToCourseQa': true,
          'durationSec': null,
          'sortOrder': 2,
        },
      ],
      'artifactSummaries': [],
      'progress': {'lastPositionSec': 128, 'masteryScore': 0.52},
      'citations': [],
      'sourceOverview': {},
      'knowledgePointPlaceholders': [],
      'weaknessPlaceholders': [],
    });
  }

  @override
  Future<handouts.HandoutLatestModel> fetchLessonHandout({
    required String courseId,
    required String lessonId,
  }) async {
    return handouts.HandoutLatestModel.fromJson({
      'handoutVersionId': 4200,
      'title': '栈与队列讲义',
      'summary': '围绕栈、队列和循环队列的核心操作生成。',
      'totalBlocks': 2,
      'status': 'ready',
    });
  }

  @override
  Future<handouts.HandoutOutlineModel> fetchLessonHandoutOutline({
    required String courseId,
    required String lessonId,
  }) async {
    return handouts.HandoutOutlineModel.fromJson({
      'handoutVersionId': 4200,
      'title': '栈与队列讲义',
      'summary': '两级讲义目录',
      'items': [
        {
          'outlineKey': 'chapter-1',
          'title': '第一章',
          'summary': '',
          'startSec': 0,
          'endSec': 180,
          'sortNo': 1,
          'children': [
            _outlineChild(
              blockId: 4201,
              outlineKey: 'section-1-1',
              title: '1.1 极限定义',
              startSec: 0,
              endSec: 90,
            ),
            _outlineChild(
              blockId: 4202,
              outlineKey: 'section-1-2',
              title: '1.2 栈的操作端',
              startSec: 90,
              endSec: 180,
            ),
          ],
        },
      ],
      'outlineUsedFallback': false,
      'outlineIssues': [],
    });
  }

  @override
  Future<handouts.HandoutBlocksModel> fetchLessonHandoutBlocks({
    required String courseId,
    required String lessonId,
  }) async {
    return handouts.HandoutBlocksModel.fromJson({
      'items': [
        _block(
          blockId: 4201,
          outlineKey: 'section-1-1',
          title: '1.1 极限定义',
          contentMd: '栈只允许在一端插入和删除，队列从队尾入队、队头出队。',
        ),
        _block(
          blockId: 4202,
          outlineKey: 'section-1-2',
          title: '1.2 栈的操作端',
          contentMd: '操作端决定了数据结构的访问顺序。',
        ),
      ],
    });
  }

  @override
  Future<handouts.CurrentHandoutBlockModel> fetchLessonCurrentHandoutBlock({
    required String courseId,
    required String lessonId,
    required int currentSec,
  }) async {
    return handouts.CurrentHandoutBlockModel.fromJson({
      'blockId': 4201,
      'outlineKey': 'section-1-1',
      'startSec': 0,
      'endSec': 90,
      'generationStatus': 'ready',
    });
  }

  @override
  Future<resources.CourseResourcePlaybackModel> fetchCourseResourcePlayback(
    int resourceId,
  ) async {
    return resources.CourseResourcePlaybackModel.fromJson({
      'resourceId': resourceId,
      'resourceType': 'mp4',
      'playbackUrl': 'https://cdn.test/$resourceId.mp4',
      'mimeType': 'video/mp4',
      'expiresAt': '2026-07-05T12:00:00Z',
      'durationSec': 2700,
    });
  }
}

Map<String, dynamic> _outlineChild({
  required int blockId,
  required String outlineKey,
  required String title,
  required int startSec,
  required int endSec,
}) {
  return {
    'outlineKey': outlineKey,
    'blockId': blockId,
    'title': title,
    'summary': '',
    'startSec': startSec,
    'endSec': endSec,
    'sortNo': blockId,
    'generationStatus': 'ready',
    'sourceSegmentKeys': ['segment-$blockId'],
    'topicTags': ['topic-$blockId'],
  };
}

Map<String, dynamic> _block({
  required int blockId,
  required String outlineKey,
  required String title,
  required String contentMd,
}) {
  return {
    'blockId': blockId,
    'outlineKey': outlineKey,
    'title': title,
    'summary': '',
    'status': 'ready',
    'contentMd': contentMd,
    'startSec': 0,
    'endSec': 90,
    'citations': [
      {
        'resourceId': 501,
        'refLabel': '第 1 讲视频',
        'startSec': 18,
        'endSec': 42,
      },
    ],
  };
}
