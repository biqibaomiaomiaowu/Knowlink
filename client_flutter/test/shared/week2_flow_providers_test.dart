import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/core/network/api_client.dart';
import 'package:knowlink_client/shared/models/course_create_request.dart';
import 'package:knowlink_client/shared/models/course_import_state.dart';
import 'package:knowlink_client/shared/models/course_summary.dart';
import 'package:knowlink_client/shared/models/inquiry_models.dart';
import 'package:knowlink_client/shared/models/pipeline_status.dart';
import 'package:knowlink_client/shared/models/recommendation_enums.dart';
import 'package:knowlink_client/shared/models/resource_upload_models.dart';
import 'package:knowlink_client/shared/providers/course_flow_providers.dart';
import 'package:knowlink_client/shared/providers/course_import_provider.dart';
import 'package:knowlink_client/shared/providers/course_recommend_provider.dart';
import 'package:knowlink_client/shared/providers/inquiry_provider.dart';
import 'package:knowlink_client/shared/providers/parse_progress_provider.dart';

void main() {
  test('course import provider creates course and uploads queued file',
      () async {
    final fakeApiClient = _Week2FakeApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);

    final notifier = container.read(courseImportProvider.notifier);

    await notifier.createCourse();

    expect(fakeApiClient.createCourseRequests.single.title, 'KnowLink 固定联调课');
    expect(container.read(courseFlowProvider).courseId, '101');
    expect(container.read(courseImportProvider).createdCourse.valueOrNull,
        isNotNull);

    notifier.addFilesForUpload([
      UploadQueueItemModel(
        id: 'file-1',
        name: 'chapter-1.pdf',
        resourceType: ResourceType.pdf,
        mimeType: 'application/pdf',
        sizeBytes: 3,
        checksum: 'sha256:demo',
        bytes: Uint8List.fromList([1, 2, 3]),
      ),
    ]);

    await notifier.uploadPendingFiles('101');

    final state = container.read(courseImportProvider);
    expect(fakeApiClient.uploadedObjectUrls.single,
        'https://minio.test/upload/chapter-1.pdf');
    expect(fakeApiClient.completedUploads.single.originalName, 'chapter-1.pdf');
    expect(state.uploadQueue.single.isReady, isTrue);
    expect(state.resources.valueOrNull, hasLength(1));
  });

  test('parse progress provider polls until partial success and syncs flow',
      () async {
    final fakeApiClient = _Week2FakeApiClient(
      pipelineStatuses: [
        _pipelineStatusJson('running', nextAction: 'poll', progressPct: 40),
        _pipelineStatusJson(
          'partial_success',
          nextAction: 'enter_handout_outline',
          progressPct: 80,
        ),
      ],
    );
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    final subscription = container.listen(
      parseProgressProvider,
      (_, __) {},
      fireImmediately: true,
    );
    addTearDown(container.dispose);
    addTearDown(subscription.close);

    await container.read(parseProgressProvider.notifier).startAndPoll(
          '101',
          interval: Duration.zero,
        );

    final state = container.read(parseProgressProvider);
    final flow = container.read(courseFlowProvider);
    expect(fakeApiClient.startParseCourseIds.single, '101');
    expect(state.currentStatus?.courseStatus.pipelineStatus, 'partial_success');
    expect(flow.activeParseRunId, 9001);
    expect(flow.nextAction, 'enter_handout_outline');
  });

  test('inquiry provider defaults selects and submits answers', () async {
    final fakeApiClient = _Week2FakeApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);

    final notifier = container.read(inquiryProvider.notifier);

    await notifier.fetchQuestions('101');
    notifier.updateAnswer('time_budget_minutes', '90');
    await notifier.submitAnswers('101');

    final state = container.read(inquiryProvider);
    expect(state.questions.valueOrNull?.questions, hasLength(2));
    expect(fakeApiClient.savedInquiryAnswers.single.answers, hasLength(2));
    expect(state.submitResult.valueOrNull?.saved, isTrue);
  });

  test('inquiry provider validates time budget contract range', () async {
    final fakeApiClient = _Week2FakeApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);

    final notifier = container.read(inquiryProvider.notifier);
    await notifier.fetchQuestions('101');

    for (final invalidValue in ['1', '99999', '12.5', 'abc']) {
      notifier.updateAnswer('time_budget_minutes', invalidValue);
      await notifier.submitAnswers('101');
      expect(
        container.read(inquiryProvider).validationErrors['time_budget_minutes'],
        isNotNull,
        reason: '$invalidValue should not pass time_budget_minutes validation',
      );
    }

    notifier.updateAnswer('time_budget_minutes', '10');
    await notifier.submitAnswers('101');

    expect(fakeApiClient.savedInquiryAnswers, hasLength(1));
    expect(
      fakeApiClient.savedInquiryAnswers.single.answers
          .singleWhere((answer) => answer.key == 'time_budget_minutes')
          .value,
      '10',
    );
  });
}

class _Week2FakeApiClient extends ApiClient {
  _Week2FakeApiClient({
    List<Map<String, dynamic>>? pipelineStatuses,
  }) : _pipelineStatuses = pipelineStatuses ?? [_pipelineStatusJson('queued')];

  final List<Map<String, dynamic>> _pipelineStatuses;

  final List<CourseCreateRequestModel> createCourseRequests = [];
  final List<String> uploadedObjectUrls = [];
  final List<ResourceUploadCompleteRequestModel> completedUploads = [];
  final List<String> startParseCourseIds = [];
  final List<SaveInquiryAnswersRequestModel> savedInquiryAnswers = [];

  var _pipelineIndex = 0;

  @override
  Future<CourseSummaryModel> createCourse({
    required CourseCreateRequestModel request,
    required String idempotencyKey,
  }) async {
    createCourseRequests.add(request);
    return CourseSummaryModel(
      courseId: 101,
      title: request.title,
      entryType: 'manual_import',
      lifecycleStatus: 'draft',
      pipelineStage: 'idle',
      pipelineStatus: 'idle',
      updatedAt: DateTime.parse('2026-04-18T15:00:00+00:00'),
    );
  }

  @override
  Future<ResourceUploadInitResultModel> initResourceUpload({
    required String courseId,
    required ResourceUploadInitRequestModel request,
  }) async {
    return ResourceUploadInitResultModel(
      uploadUrl: 'https://minio.test/upload/${request.filename}',
      objectKey: 'raw/1/$courseId/temp/${request.filename}',
      headers: const {'x-amz-meta-course-id': '101'},
      expiresAt: DateTime.parse('2026-04-18T15:15:00+00:00'),
    );
  }

  @override
  Future<void> uploadObject({
    required String uploadUrl,
    required Uint8List bytes,
    required Map<String, String> headers,
    required String mimeType,
  }) async {
    uploadedObjectUrls.add(uploadUrl);
  }

  @override
  Future<CourseResourceModel> completeResourceUpload({
    required String courseId,
    required ResourceUploadCompleteRequestModel request,
    required String idempotencyKey,
  }) async {
    completedUploads.add(request);
    return CourseResourceModel.fromJson({
      'resourceId': 501,
      'resourceType': request.resourceType.name,
      'originalName': request.originalName,
      'objectKey': request.objectKey,
      'ingestStatus': 'ready',
      'validationStatus': 'passed',
      'processingStatus': 'pending',
    });
  }

  @override
  Future<List<CourseResourceModel>> fetchCourseResources(
      String courseId) async {
    if (completedUploads.isEmpty) {
      return const [];
    }
    final upload = completedUploads.last;
    return [
      CourseResourceModel.fromJson({
        'resourceId': 501,
        'resourceType': upload.resourceType.name,
        'originalName': upload.originalName,
        'objectKey': upload.objectKey,
        'ingestStatus': 'ready',
        'validationStatus': 'passed',
        'processingStatus': 'pending',
      }),
    ];
  }

  @override
  Future<ParseStartResultModel> startParse({
    required String courseId,
    required String idempotencyKey,
  }) async {
    startParseCourseIds.add(courseId);
    return ParseStartResultModel.fromJson({
      'taskId': 7001,
      'status': 'queued',
      'nextAction': 'poll',
      'entity': {'type': 'parse_run', 'id': 9001},
    });
  }

  @override
  Future<PipelineStatusModel> fetchPipelineStatus(String courseId) async {
    final json = _pipelineStatuses[
        _pipelineIndex.clamp(0, _pipelineStatuses.length - 1)];
    _pipelineIndex++;
    return PipelineStatusModel.fromJson(json);
  }

  @override
  Future<InquiryQuestionsModel> fetchInquiryQuestions(String courseId) async {
    return InquiryQuestionsModel.fromJson({
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
        {
          'key': 'time_budget_minutes',
          'label': '本轮学习时间预算',
          'type': 'number',
          'required': true,
          'options': [],
        },
      ],
    });
  }

  @override
  Future<SaveInquiryAnswersResultModel> saveInquiryAnswers({
    required String courseId,
    required SaveInquiryAnswersRequestModel request,
  }) async {
    savedInquiryAnswers.add(request);
    return SaveInquiryAnswersResultModel(
      saved: true,
      answerCount: request.answers.length,
    );
  }
}

Map<String, dynamic> _pipelineStatusJson(
  String pipelineStatus, {
  String nextAction = 'poll',
  int progressPct = 0,
}) {
  return {
    'courseStatus': {
      'lifecycleStatus': pipelineStatus == 'partial_success'
          ? 'inquiry_ready'
          : 'resource_ready',
      'pipelineStage': 'parse',
      'pipelineStatus': pipelineStatus,
    },
    'progressPct': progressPct,
    'steps': [
      {
        'code': 'resource_validate',
        'label': '资源校验',
        'status': pipelineStatus == 'running' ? 'running' : 'succeeded',
      },
    ],
    'activeParseRunId': 9001,
    'activeHandoutVersionId': null,
    'nextAction': nextAction,
  };
}
