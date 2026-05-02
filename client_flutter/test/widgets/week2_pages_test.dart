import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/core/network/api_client.dart';
import 'package:knowlink_client/features/course_import/course_import_page.dart';
import 'package:knowlink_client/features/inquiry/inquiry_page.dart';
import 'package:knowlink_client/features/parse_progress/parse_progress_page.dart';
import 'package:knowlink_client/shared/models/course_create_request.dart';
import 'package:knowlink_client/shared/models/course_summary.dart';
import 'package:knowlink_client/shared/models/inquiry_models.dart';
import 'package:knowlink_client/shared/models/pipeline_status.dart';
import 'package:knowlink_client/shared/models/resource_upload_models.dart';
import 'package:knowlink_client/shared/providers/course_flow_providers.dart';
import 'package:knowlink_client/shared/providers/course_recommend_provider.dart';
import 'package:knowlink_client/shared/providers/inquiry_provider.dart';

void main() {
  testWidgets('course import page creates a manual course', (tester) async {
    _useLargeTestSurface(tester);
    final fakeApiClient = _Week2PageFakeApiClient();
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(fakeApiClient),
        ],
        child: const MaterialApp(home: CourseImportPage()),
      ),
    );

    await tester.tap(find.widgetWithText(FilledButton, '创建课程'));
    await tester.pumpAndSettle();

    expect(fakeApiClient.createCourseCalls, 1);
    expect(find.text('当前课程：101'), findsOneWidget);
    expect(
      find.widgetWithText(
        FilledButton,
        '进入解析进度',
        skipOffstage: false,
      ),
      findsOneWidget,
    );
  });

  testWidgets('bare course import page ignores stale active course', (
    tester,
  ) async {
    _useLargeTestSurface(tester);
    final fakeApiClient = _Week2PageFakeApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);
    container.read(courseFlowProvider.notifier).startCourse('999');

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: CourseImportPage()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('请先创建课程或从推荐页进入。'), findsOneWidget);
    expect(find.text('当前课程：999'), findsNothing);
    expect(fakeApiClient.fetchedResourceCourseIds, isEmpty);
  });

  testWidgets('parse progress page renders pipeline status', (tester) async {
    _useLargeTestSurface(tester);
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(_Week2PageFakeApiClient()),
        ],
        child: const MaterialApp(home: ParseProgressPage(courseId: '101')),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.textContaining('partial_success'), findsOneWidget);
    expect(find.text('资源校验'), findsOneWidget);
    expect(find.text('资源 501 校验失败'), findsOneWidget);
    expect(find.text('失败资源：501'), findsOneWidget);
    expect(find.text('failed · 80%'), findsOneWidget);
    expect(
      find.widgetWithText(FilledButton, '进入问询', skipOffstage: false),
      findsOneWidget,
    );
  });

  testWidgets('inquiry page validates required number and saves answers', (
    tester,
  ) async {
    _useLargeTestSurface(tester);
    final fakeApiClient = _Week2PageFakeApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: InquiryPage(courseId: '101')),
      ),
    );
    await tester.pumpAndSettle();

    final saveButton = find.widgetWithText(FilledButton, '保存问询答案');
    await tester.ensureVisible(saveButton);
    await tester.tap(saveButton);
    await tester.pump();
    expect(
      container.read(inquiryProvider).validationErrors['time_budget_minutes'],
      '请完成该项',
    );

    await tester.enterText(find.byType(TextField), '120');
    await tester.ensureVisible(saveButton);
    await tester.tap(saveButton);
    await tester.pumpAndSettle();

    expect(fakeApiClient.saveInquiryCalls, 1);
    expect(find.text('问询答案已保存。'), findsOneWidget);
  });
}

void _useLargeTestSurface(WidgetTester tester) {
  tester.view.physicalSize = const Size(1200, 1800);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

class _Week2PageFakeApiClient extends ApiClient {
  int createCourseCalls = 0;
  int saveInquiryCalls = 0;
  final List<String> fetchedResourceCourseIds = [];

  @override
  Future<CourseSummaryModel> createCourse({
    required CourseCreateRequestModel request,
    required String idempotencyKey,
  }) async {
    createCourseCalls++;
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
  Future<List<CourseResourceModel>> fetchCourseResources(
      String courseId) async {
    fetchedResourceCourseIds.add(courseId);
    return const [];
  }

  @override
  Future<PipelineStatusModel> fetchPipelineStatus(String courseId) async {
    return PipelineStatusModel.fromJson({
      'courseStatus': {
        'lifecycleStatus': 'inquiry_ready',
        'pipelineStage': 'parse',
        'pipelineStatus': 'partial_success',
      },
      'progressPct': 80,
      'steps': [
        {
          'code': 'resource_validate',
          'label': '资源校验',
          'status': 'failed',
          'progressPct': 80,
          'message': '资源 501 校验失败',
          'failedResourceIds': [501],
        },
      ],
      'activeParseRunId': 9001,
      'activeHandoutVersionId': null,
      'nextAction': 'enter_inquiry',
    });
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
    saveInquiryCalls++;
    return SaveInquiryAnswersResultModel(
      saved: true,
      answerCount: request.answers.length,
    );
  }
}
