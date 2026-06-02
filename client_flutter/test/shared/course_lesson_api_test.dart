import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/core/network/api_client.dart';
import 'package:knowlink_client/shared/models/course_lesson_models.dart';
import 'package:knowlink_client/shared/services/course_lesson_api.dart';

void main() {
  test('course lesson models parse frozen V2 DTO fields', () {
    final libraryItem = CourseLibraryItemModel.fromJson({
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
    });

    expect(libraryItem.courseId, '101');
    expect(libraryItem.isCurrent, isTrue);
    expect(libraryItem.currentLessonTitle, '关系模型');
    expect(libraryItem.overallMasteryScore, 0.72);

    final detail = LessonDetailModel.fromJson(_lessonDetailData());
    expect(detail.lesson.lessonId, 'l-2');
    expect(detail.primaryVideo?.usageRole, 'primary_video');
    expect(detail.lessonResources.single.scopeType, 'lesson');
    expect(detail.artifactSummaries, hasLength(2));
    expect(detail.artifactSummaryByKey['handout_version']?.status, 'ready');
    expect(detail.citations.single.lessonTitle, '关系模型');
    expect(detail.nextAction?.type, 'continue_video');
    expect(detail.nextAction?.label, '继续看视频');
    expect(detail.nextAction?.route, '/courses/101/lessons/l-2');
  });

  test('ApiClient and CourseLessonApi use aggregate course/lesson paths',
      () async {
    final adapter = _RecordingHttpClientAdapter(
      onFetch: (options, _) async {
        final data = switch ('${options.method} ${options.path}') {
          'GET /api/v1/courses' => {
              'items': [_courseLibraryItem()],
            },
          'GET /api/v1/courses/101/workbench' => _workbenchData(),
          'GET /api/v1/courses/101/lessons' => {
              'items': [_lessonSummary()],
            },
          'POST /api/v1/courses/101/lessons' => {
              'lesson': _lessonSummary(),
            },
          'PATCH /api/v1/courses/101/lessons/l-2' => {
              'lesson': _lessonSummary(),
            },
          'DELETE /api/v1/courses/101/lessons/l-2' => {},
          'POST /api/v1/courses/101/lessons/reorder' => {
              'items': [_lessonSummary()],
            },
          'POST /api/v1/courses/101/lessons/l-2/primary-video' => {
              'lesson': _lessonSummary(),
            },
          'POST /api/v1/courses/101/lessons/merge' => {
              'lesson': _lessonSummary(),
              'staleArtifactIds': ['quiz:702'],
              'staleArtifacts': [],
            },
          'POST /api/v1/courses/101/lessons/l-2/split' => {
              'firstLesson': _lessonSummary(),
              'secondLesson': {..._lessonSummary(), 'lessonId': 'l-3'},
              'staleArtifactIds': ['handout_version:701'],
              'staleArtifacts': [],
            },
          'GET /api/v1/courses/101/lessons/l-2' => _lessonDetailData(),
          'GET /api/v1/courses/101/lessons/l-2/progress' =>
            _lessonProgressData(),
          'PUT /api/v1/courses/101/lessons/l-2/progress' =>
            _lessonProgressData(lastPositionSec: 180),
          'GET /api/v1/courses/101/qa/sessions' => {
              'items': [],
              'placeholder': {
                'key': 'course_qa',
                'title': '全课程 QA',
                'status': 'placeholder',
                'message': '等待生成会话',
              },
            },
          'GET /api/v1/courses/101/graph' => {
              'status': 'placeholder',
              'message': '图谱生成暂未启用',
              'nodes': [],
              'edges': [],
            },
          'GET /api/v1/courses/101/exports' => {
              'availableExportTypes': ['course_summary'],
              'status': 'placeholder',
              'message': '导出任务暂未启用',
              'downloadUrl': null,
            },
          _ => throw StateError('Unexpected ${options.method} ${options.path}'),
        };
        return ResponseBody.fromString(
          jsonEncode({'data': data}),
          200,
          headers: {
            Headers.contentTypeHeader: ['application/json'],
          },
        );
      },
    );
    final client = ApiClient(
      httpClientAdapter: adapter,
      baseUrl: 'https://example.test',
      demoToken: 'v2-task7-token',
    );
    final api = CourseLessonApi(client);

    final courses = await api.fetchCourseLibrary();
    final workbench = await api.fetchCourseWorkbench('101');
    final lessons = await api.fetchLessons('101');
    final created = await api.createLesson(
      courseId: '101',
      request: {'title': '新增节课'},
      idempotencyKey: 'create-l-2',
    );
    final updated = await api.updateLesson(
      courseId: '101',
      lessonId: 'l-2',
      request: {'title': '关系模型'},
    );
    await api.deleteLesson(courseId: '101', lessonId: 'l-2');
    final reordered = await api.reorderLessons(
      courseId: '101',
      lessonIds: ['l-2'],
    );
    final primaryVideo = await api.setLessonPrimaryVideo(
      courseId: '101',
      lessonId: 'l-2',
      resourceId: '601',
      startSec: 0,
      endSec: 1800,
    );
    final merged = await api.mergeLessons(
      courseId: '101',
      lessonIds: ['l-1', 'l-2'],
      targetTitle: '合并节课',
    );
    final split = await api.splitLesson(
      courseId: '101',
      lessonId: 'l-2',
      splitAtSec: 900,
      firstTitle: '前半节',
      secondTitle: '后半节',
    );
    final detail = await api.fetchLessonDetail(
      courseId: '101',
      lessonId: 'l-2',
    );
    final progress = await api.fetchLessonProgress(
      courseId: '101',
      lessonId: 'l-2',
    );
    final updatedProgress = await api.updateLessonProgress(
      courseId: '101',
      lessonId: 'l-2',
      request: {'lastPositionSec': 180},
    );
    final qaPlaceholder = await api.fetchCourseQaPlaceholder('101');
    final graphPlaceholder = await api.fetchCourseGraphPlaceholder('101');
    final exportPlaceholder = await api.fetchCourseExportPlaceholder('101');

    expect(courses.single.title, '数据库系统');
    expect(workbench.lessons.single.title, '关系模型');
    expect(workbench.nextActions.single.label, '继续学习关系模型');
    expect(workbench.nextActions.single.route, '/courses/101/lessons/l-2');
    expect(lessons.single.lessonId, 'l-2');
    expect(created.lessonId, 'l-2');
    expect(updated.lessonId, 'l-2');
    expect(reordered.single.lessonId, 'l-2');
    expect(primaryVideo.primaryVideoResourceId, '601');
    expect(merged['staleArtifactIds'], ['quiz:702']);
    expect(split['staleArtifactIds'], ['handout_version:701']);
    expect(detail.lesson.title, '关系模型');
    expect(progress.lastPositionSec, 125);
    expect(updatedProgress.lastPositionSec, 180);
    expect(qaPlaceholder.key, 'course_qa');
    expect(graphPlaceholder.status, 'placeholder');
    expect(exportPlaceholder.title, '课程导出');
    expect(
        adapter.requests.map((request) => '${request.method} ${request.path}'),
        [
          'GET /api/v1/courses',
          'GET /api/v1/courses/101/workbench',
          'GET /api/v1/courses/101/lessons',
          'POST /api/v1/courses/101/lessons',
          'PATCH /api/v1/courses/101/lessons/l-2',
          'DELETE /api/v1/courses/101/lessons/l-2',
          'POST /api/v1/courses/101/lessons/reorder',
          'POST /api/v1/courses/101/lessons/l-2/primary-video',
          'POST /api/v1/courses/101/lessons/merge',
          'POST /api/v1/courses/101/lessons/l-2/split',
          'GET /api/v1/courses/101/lessons/l-2',
          'GET /api/v1/courses/101/lessons/l-2/progress',
          'PUT /api/v1/courses/101/lessons/l-2/progress',
          'GET /api/v1/courses/101/qa/sessions',
          'GET /api/v1/courses/101/graph',
          'GET /api/v1/courses/101/exports',
        ]);
  });
}

Map<String, dynamic> _courseLibraryItem() {
  return {
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
  };
}

Map<String, dynamic> _workbenchData() {
  return {
    'course': _courseLibraryItem(),
    'progress': {
      'completedLessonCount': 2,
      'totalLessonCount': 6,
      'progressPct': 33,
      'lastPositionSec': 125,
    },
    'currentLesson': _lessonSummary(),
    'lessons': [_lessonSummary()],
    'courseResources': [
      {
        'resourceId': 501,
        'courseId': 101,
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
    ],
    'nextActions': [
      {
        'type': 'continue_lesson',
        'lessonId': 'l-2',
        'title': '关系模型',
      },
    ],
    'placeholderStates': {
      'course_graph': {
        'key': 'course_graph',
        'title': '课程图谱',
        'status': 'placeholder',
        'message': '图谱生成暂未启用',
      },
    },
  };
}

Map<String, dynamic> _lessonSummary() {
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

Map<String, dynamic> _lessonProgressData({int lastPositionSec = 125}) {
  return {
    'courseId': 101,
    'lessonId': 'l-2',
    'lastPositionSec': lastPositionSec,
    'lastHandoutBlockId': null,
    'handoutReadPercent': 42,
    'quizStatus': 'not_generated',
    'reviewStatus': 'due',
    'lastActivityAt': '2026-06-01T09:30:00+08:00',
  };
}

Map<String, dynamic> _lessonDetailData() {
  return {
    'lesson': _lessonSummary(),
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
        'courseId': 101,
        'resourceType': 'pdf',
        'originalName': '关系模型讲义.pdf',
        'scopeType': 'lesson',
        'lessonId': 'l-2',
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
        'lessonId': 'l-2',
        'status': 'ready',
      },
      {
        'artifactId': 702,
        'artifactType': 'quiz',
        'scopeType': 'lesson',
        'lessonId': 'l-2',
        'status': 'not_generated',
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
        'lessonId': 'l-2',
        'lessonTitle': '关系模型',
        'resourceId': 602,
        'resourceName': '关系模型讲义.pdf',
        'refLabel': 'PDF 第 12 页',
        'pageNo': 12,
      },
    ],
    'sourceOverview': {
      'scopeType': 'lesson',
      'lessonId': 'l-2',
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
  };
}

class _RecordingHttpClientAdapter implements HttpClientAdapter {
  _RecordingHttpClientAdapter({required this.onFetch});

  final Future<ResponseBody> Function(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
  ) onFetch;
  final List<RequestOptions> requests = <RequestOptions>[];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<List<int>>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    requests.add(options);
    return onFetch(options, requestStream?.cast<Uint8List>());
  }

  @override
  void close({bool force = false}) {}
}
