import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/core/network/api_client.dart';
import 'package:knowlink_client/shared/models/confirm_recommendation_request.dart';
import 'package:knowlink_client/shared/models/course_create_request.dart';
import 'package:knowlink_client/shared/models/inquiry_models.dart';
import 'package:knowlink_client/shared/models/recommendation_enums.dart';
import 'package:knowlink_client/shared/models/recommendation_request.dart';
import 'package:knowlink_client/shared/models/resource_upload_models.dart';

void main() {
  test('fetchRecommendations sends expected path, auth header, and parses data',
      () async {
    final adapter = _RecordingHttpClientAdapter(
      onFetch: (options, _) async {
        return ResponseBody.fromString(
          jsonEncode({
            'data': {
              'recommendations': [
                {
                  'catalogId': 'math-final-01',
                  'title': '高等数学期末冲刺',
                  'provider': 'KnowLink Seed',
                  'level': 'intermediate',
                  'estimatedHours': 4,
                  'fitScore': 96,
                  'reasons': ['难度与当前基础匹配'],
                  'defaultResourceManifest': [
                    {
                      'resourceType': 'mp4',
                      'required': true,
                      'description': '主课程视频',
                    },
                  ],
                },
              ],
            },
          }),
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
      demoToken: 'week-one-token',
    );

    final request = RecommendationRequestModel(
      goalText: '高等数学期末复习',
      selfLevel: SelfLevel.intermediate,
      timeBudgetMinutes: 240,
      examAt: DateTime.utc(2026, 6, 15, 1),
      preferredStyle: PreferredStyle.exam,
    );

    final recommendations = await client.fetchRecommendations(request);

    expect(recommendations, hasLength(1));
    expect(recommendations.single.catalogId, 'math-final-01');
    expect(adapter.requests, hasLength(1));

    final captured = adapter.requests.single;
    expect(captured.method, 'POST');
    expect(captured.path, '/api/v1/recommendations/courses');
    expect(_headerValue(captured.headers, 'authorization'),
        'Bearer week-one-token');
    expect(captured.data, request.toJson());
  });

  test('confirmRecommendation sends idempotency key and parses created course',
      () async {
    final adapter = _RecordingHttpClientAdapter(
      onFetch: (options, _) async {
        return ResponseBody.fromString(
          jsonEncode({
            'data': {
              'course': {
                'courseId': 101,
                'title': '高数期末冲刺课',
                'entryType': 'recommendation',
                'catalogId': 'math-final-01',
                'lifecycleStatus': 'draft',
                'pipelineStage': 'idle',
                'pipelineStatus': 'idle',
                'updatedAt': '2026-04-18T15:00:00+00:00',
              },
              'createdFromCatalogId': 'math-final-01',
            },
          }),
          201,
          headers: {
            Headers.contentTypeHeader: ['application/json'],
          },
        );
      },
    );
    final client = ApiClient(
      httpClientAdapter: adapter,
      baseUrl: 'https://example.test',
      demoToken: 'week-one-token',
    );
    const request = ConfirmRecommendationRequestModel(
      goalText: '高等数学期末复习',
      preferredStyle: PreferredStyle.exam,
      titleOverride: '高数期末冲刺课',
    );

    final result = await client.confirmRecommendation(
      catalogId: 'math-final-01',
      request: request,
      idempotencyKey: 'rec-confirm-1',
    );

    expect(result.createdFromCatalogId, 'math-final-01');
    expect(result.course.courseId, 101);
    expect(adapter.requests, hasLength(1));

    final captured = adapter.requests.single;
    expect(captured.method, 'POST');
    expect(
      captured.path,
      '/api/v1/recommendations/math-final-01/confirm',
    );
    expect(_headerValue(captured.headers, 'authorization'),
        'Bearer week-one-token');
    expect(
      _headerValue(captured.headers, 'idempotency-key'),
      'rec-confirm-1',
    );
    expect(captured.data, request.toJson());
  });

  test('createCourse sends idempotency key and parses course', () async {
    final adapter = _RecordingHttpClientAdapter(
      onFetch: (options, _) async {
        return ResponseBody.fromString(
          jsonEncode({
            'data': {
              'course': {
                'courseId': 202,
                'title': 'KnowLink 固定联调课',
                'entryType': 'manual_import',
                'catalogId': null,
                'lifecycleStatus': 'draft',
                'pipelineStage': 'idle',
                'pipelineStatus': 'idle',
                'updatedAt': '2026-04-18T15:00:00+00:00',
              },
            },
          }),
          201,
          headers: {
            Headers.contentTypeHeader: ['application/json'],
          },
        );
      },
    );
    final client = ApiClient(
      httpClientAdapter: adapter,
      baseUrl: 'https://example.test',
      demoToken: 'week-two-token',
    );
    const request = CourseCreateRequestModel(
      title: 'KnowLink 固定联调课',
      goalText: '期末复习',
      preferredStyle: PreferredStyle.balanced,
    );

    final course = await client.createCourse(
      request: request,
      idempotencyKey: 'course-create-1',
    );

    expect(course.courseId, 202);
    expect(course.entryType, 'manual_import');
    final captured = adapter.requests.single;
    expect(captured.method, 'POST');
    expect(captured.path, '/api/v1/courses');
    expect(
        _headerValue(captured.headers, 'idempotency-key'), 'course-create-1');
    expect(captured.data, request.toJson());
  });

  test('resource upload methods use frozen Week 2 paths', () async {
    final adapter = _RecordingHttpClientAdapter(
      onFetch: (options, _) async {
        if (options.path.endsWith('/upload-init')) {
          return ResponseBody.fromString(
            jsonEncode({
              'data': {
                'uploadUrl': 'https://minio.test/upload/demo',
                'objectKey': 'raw/1/101/temp/chapter-1.pdf',
                'headers': {'x-amz-meta-course-id': '101'},
                'expiresAt': '2026-04-18T15:15:00+00:00',
              },
            }),
            200,
            headers: {
              Headers.contentTypeHeader: ['application/json'],
            },
          );
        }
        if (options.path.endsWith('/upload-complete')) {
          return ResponseBody.fromString(
            jsonEncode({
              'data': {
                'resourceId': 501,
                'resourceType': 'pdf',
                'originalName': 'chapter-1.pdf',
                'objectKey': 'raw/1/101/temp/chapter-1.pdf',
                'ingestStatus': 'ready',
                'validationStatus': 'passed',
                'processingStatus': 'pending',
              },
            }),
            200,
            headers: {
              Headers.contentTypeHeader: ['application/json'],
            },
          );
        }
        return ResponseBody.fromString(
          jsonEncode({
            'data': {
              'items': [
                {
                  'resourceId': 501,
                  'resourceType': 'pdf',
                  'originalName': 'chapter-1.pdf',
                  'objectKey': 'raw/1/101/temp/chapter-1.pdf',
                  'ingestStatus': 'ready',
                  'validationStatus': 'passed',
                  'processingStatus': 'pending',
                },
              ],
            },
          }),
          200,
          headers: {
            Headers.contentTypeHeader: ['application/json'],
          },
        );
      },
    );
    final objectAdapter = _RecordingHttpClientAdapter(
      onFetch: (options, _) async => ResponseBody.fromString('', 200),
    );
    final client = ApiClient(
      httpClientAdapter: adapter,
      objectStorageHttpClientAdapter: objectAdapter,
      baseUrl: 'https://example.test',
      demoToken: 'week-two-token',
    );

    final uploadInit = await client.initResourceUpload(
      courseId: '101',
      request: const ResourceUploadInitRequestModel(
        resourceType: ResourceType.pdf,
        filename: 'chapter-1.pdf',
        mimeType: 'application/pdf',
        sizeBytes: 32768,
        checksum: 'sha256:demo',
      ),
    );
    await client.uploadObject(
      uploadUrl: uploadInit.uploadUrl,
      bytes: Uint8List.fromList([1, 2, 3]),
      headers: uploadInit.headers,
      mimeType: 'application/pdf',
    );
    final resource = await client.completeResourceUpload(
      courseId: '101',
      request: ResourceUploadCompleteRequestModel(
        resourceType: ResourceType.pdf,
        objectKey: uploadInit.objectKey,
        originalName: 'chapter-1.pdf',
        mimeType: 'application/pdf',
        sizeBytes: 32768,
        checksum: 'sha256:demo',
      ),
      idempotencyKey: 'upload-complete-1',
    );
    final resources = await client.fetchCourseResources('101');

    expect(resource.resourceId, 501);
    expect(resources.single.originalName, 'chapter-1.pdf');
    expect(adapter.requests.map((request) => request.path), [
      '/api/v1/courses/101/resources/upload-init',
      '/api/v1/courses/101/resources/upload-complete',
      '/api/v1/courses/101/resources',
    ]);
    expect(
      _headerValue(adapter.requests[1].headers, 'idempotency-key'),
      'upload-complete-1',
    );
    expect(objectAdapter.requests.single.uri.toString(),
        'https://minio.test/upload/demo');
    expect(
      _headerValue(objectAdapter.requests.single.headers, 'authorization'),
      isNull,
    );
  });

  test('parse and inquiry methods parse Week 2 response models', () async {
    final adapter = _RecordingHttpClientAdapter(
      onFetch: (options, _) async {
        if (options.path.endsWith('/parse/start')) {
          return ResponseBody.fromString(
            jsonEncode({
              'data': {
                'taskId': 7001,
                'status': 'queued',
                'nextAction': 'poll',
                'entity': {'type': 'parse_run', 'id': 9001},
              },
            }),
            200,
            headers: {
              Headers.contentTypeHeader: ['application/json'],
            },
          );
        }
        if (options.path.endsWith('/pipeline-status')) {
          return ResponseBody.fromString(
            jsonEncode({
              'data': {
                'courseStatus': {
                  'lifecycleStatus': 'inquiry_ready',
                  'pipelineStage': 'parse',
                  'pipelineStatus': 'partial_success',
                },
                'progressPct': 80,
                'steps': [
                  {
                    'code': 'knowledge_extract',
                    'label': '目录抽取 / 知识点懒生成',
                    'status': 'partial_success',
                    'progressPct': 75,
                    'message': '2 个资源解析失败',
                    'failedResourceIds': [501, 502],
                  },
                ],
                'activeParseRunId': 9001,
                'activeHandoutVersionId': null,
                'nextAction': 'enter_handout_outline',
                'sourceOverview': {
                  'videoReady': true,
                  'outlineReady': true,
                  'outlineItemCount': 3,
                  'docTypes': ['pdf'],
                  'organizedSourceCount': 1,
                },
                'knowledgeMap': {
                  'status': 'deferred',
                  'knowledgePointCount': 0,
                  'segmentCount': 12,
                },
                'handoutOutline': {
                  'status': 'ready',
                  'outlineItemCount': 3,
                  'generatedBlockCount': 0,
                },
                'highlightSummary': {
                  'status': 'ready',
                  'items': ['视频目录已生成'],
                },
              },
            }),
            200,
            headers: {
              Headers.contentTypeHeader: ['application/json'],
            },
          );
        }
        if (options.path.endsWith('/inquiry/questions')) {
          return ResponseBody.fromString(
            jsonEncode({
              'data': {
                'version': 1,
                'questions': [
                  {
                    'key': 'goal_type',
                    'label': '当前学习目标',
                    'type': 'single_select',
                    'required': true,
                    'options': [
                      {'label': '期末复习', 'value': 'final_review'},
                    ],
                  },
                ],
              },
            }),
            200,
            headers: {
              Headers.contentTypeHeader: ['application/json'],
            },
          );
        }
        return ResponseBody.fromString(
          jsonEncode({
            'data': {
              'saved': true,
              'answerCount': 1,
            },
          }),
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
      demoToken: 'week-two-token',
    );

    final parse = await client.startParse(
      courseId: '101',
      idempotencyKey: 'parse-start-1',
    );
    final status = await client.fetchPipelineStatus('101');
    final questions = await client.fetchInquiryQuestions('101');
    final saved = await client.saveInquiryAnswers(
      courseId: '101',
      request: const SaveInquiryAnswersRequestModel(
        answers: [
          InquiryAnswerModel(key: 'goal_type', value: 'final_review'),
        ],
      ),
    );

    expect(parse.entity.id, 9001);
    expect(status.courseStatus.pipelineStatus, 'partial_success');
    expect(status.steps.single.progressPct, 75);
    expect(status.steps.single.message, '2 个资源解析失败');
    expect(status.steps.single.failedResourceIds, [501, 502]);
    expect(status.canEnterHandoutOutline, isTrue);
    expect(questions.questions.single.key, 'goal_type');
    expect(saved.answerCount, 1);
    expect(adapter.requests.map((request) => request.path), [
      '/api/v1/courses/101/parse/start',
      '/api/v1/courses/101/pipeline-status',
      '/api/v1/courses/101/inquiry/questions',
      '/api/v1/courses/101/inquiry/answers',
    ]);
    expect(
      _headerValue(adapter.requests.first.headers, 'idempotency-key'),
      'parse-start-1',
    );
  });
}

String? _headerValue(Map<String, dynamic> headers, String key) {
  for (final entry in headers.entries) {
    if (entry.key.toLowerCase() == key.toLowerCase()) {
      return entry.value?.toString();
    }
  }
  return null;
}

class _RecordingHttpClientAdapter implements HttpClientAdapter {
  _RecordingHttpClientAdapter({
    required this.onFetch,
  });

  final Future<ResponseBody> Function(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
  ) onFetch;

  final List<RequestOptions> requests = <RequestOptions>[];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    requests.add(options);
    return onFetch(options, requestStream);
  }

  @override
  void close({
    bool force = false,
  }) {}
}
