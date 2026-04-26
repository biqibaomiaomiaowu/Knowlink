import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/app/router/app_router.dart';
import 'package:knowlink_client/core/network/api_client.dart';
import 'package:knowlink_client/features/course_import/course_import_page.dart';
import 'package:knowlink_client/features/course_recommend/course_recommend_page.dart';
import 'package:knowlink_client/shared/models/confirm_recommendation_request.dart';
import 'package:knowlink_client/shared/models/confirm_recommendation_result.dart';
import 'package:knowlink_client/shared/models/course_summary.dart';
import 'package:knowlink_client/shared/models/recommendation_card.dart';
import 'package:knowlink_client/shared/models/recommendation_enums.dart';
import 'package:knowlink_client/shared/models/recommendation_request.dart';
import 'package:knowlink_client/shared/models/resource_manifest_item.dart';
import 'package:knowlink_client/shared/providers/course_flow_providers.dart';
import 'package:knowlink_client/shared/providers/course_recommend_provider.dart';

void main() {
  testWidgets(
    'recommend page fetches, confirms, syncs course flow, and navigates to import',
    (tester) async {
      tester.view.physicalSize = const Size(1200, 2200);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      final fakeApiClient = _FakeApiClient();
      final container = ProviderContainer(
        overrides: [
          apiClientProvider.overrideWithValue(fakeApiClient),
        ],
      );
      final router = AppRouter.createRouter();
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp.router(routerConfig: router),
        ),
      );

      router.go('/recommend');
      await tester.pumpAndSettle();

      expect(find.byType(CourseRecommendPage), findsOneWidget);

      await tester.tap(find.byType(FilledButton));
      await tester.pumpAndSettle();

      expect(find.text(_FakeApiClient.recommendationTitle), findsOneWidget);
      expect(find.textContaining('MP4'), findsAtLeastNWidgets(1));
      expect(fakeApiClient.recommendationRequests, hasLength(1));

      await tester.tap(find.byType(FilledButton).last);
      await tester.pumpAndSettle();

      expect(fakeApiClient.confirmationRequests, hasLength(1));
      expect(
        find.textContaining(
          _FakeApiClient.createdCourseTitle,
          skipOffstage: false,
        ),
        findsOneWidget,
      );
      expect(
        find.textContaining('courseId', skipOffstage: false),
        findsOneWidget,
      );

      final flowState = container.read(courseFlowProvider);
      expect(flowState.courseId, '101');
      expect(flowState.lifecycleStatus, 'draft');
      expect(flowState.pipelineStage, 'idle');
      expect(flowState.pipelineStatus, 'idle');

      final importButton = find.byType(OutlinedButton, skipOffstage: false);
      await tester.ensureVisible(importButton);
      await tester.tap(importButton);
      await tester.pumpAndSettle();

      expect(find.byType(CourseImportPage), findsOneWidget);
      expect(find.text('当前课程：101'), findsOneWidget);
      expect(container.read(courseFlowProvider).courseId, '101');

      await tester.pump(const Duration(seconds: 4));
      await tester.pumpAndSettle();
    },
  );

  testWidgets('invalid examAt shows error and blocks submit', (tester) async {
    tester.view.physicalSize = const Size(1200, 2200);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final fakeApiClient = _FakeApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(
          home: CourseRecommendPage(),
        ),
      ),
    );

    final examAtField = find.byType(TextField).last;
    await tester.enterText(examAtField, 'invalid-date');
    await tester.pump();

    final fetchButton = tester.widget<FilledButton>(find.byType(FilledButton));
    final examAtWidget = tester.widget<TextField>(examAtField);
    expect(find.textContaining('ISO'), findsOneWidget);
    expect(examAtWidget.decoration?.errorText, isNotNull);
    expect(fetchButton.onPressed, isNull);
    expect(fakeApiClient.recommendationRequests, isEmpty);
    expect(container.read(courseRecommendProvider).requestDraft.examAt, isNull);
  });

  testWidgets('time budget below API minimum shows error and blocks submit', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1200, 2200);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final fakeApiClient = _FakeApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(
          home: CourseRecommendPage(),
        ),
      ),
    );

    final timeBudgetField = find.byType(TextField).at(1);
    await tester.enterText(timeBudgetField, '15');
    await tester.pump();

    final fetchButton = tester.widget<FilledButton>(find.byType(FilledButton));
    final timeBudgetWidget = tester.widget<TextField>(timeBudgetField);
    expect(timeBudgetWidget.decoration?.errorText, isNotNull);
    expect(timeBudgetWidget.decoration?.errorText, contains('30'));
    expect(fetchButton.onPressed, isNull);
    expect(fakeApiClient.recommendationRequests, isEmpty);
    expect(
      container.read(courseRecommendProvider).requestDraft.timeBudgetMinutes,
      240,
    );
  });

  testWidgets('draft form locks during fetch and confirm', (tester) async {
    tester.view.physicalSize = const Size(1200, 2200);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final fetchCompleter = Completer<List<RecommendationCardModel>>();
    final confirmCompleter = Completer<ConfirmRecommendationResultModel>();
    final fakeApiClient = _FakeApiClient(
      fetchCompleter: fetchCompleter,
      confirmCompleter: confirmCompleter,
    );
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(
          home: CourseRecommendPage(),
        ),
      ),
    );

    await tester.tap(find.byType(FilledButton));
    await tester.pump();

    _expectDraftInputsLocked(tester);

    fetchCompleter.complete([
      const RecommendationCardModel(
        catalogId: 'math-final-01',
        title: _FakeApiClient.recommendationTitle,
        provider: 'KnowLink Seed',
        level: 'intermediate',
        estimatedHours: 4,
        fitScore: 96,
        reasons: ['Difficulty matches the current level'],
        defaultResourceManifest: [],
      ),
    ]);
    await tester.pumpAndSettle();

    await tester.tap(find.byType(FilledButton).last);
    await tester.pump();

    _expectDraftInputsLocked(tester);

    confirmCompleter.complete(
      ConfirmRecommendationResultModel(
        course: CourseSummaryModel(
          courseId: 101,
          title: _FakeApiClient.createdCourseTitle,
          entryType: 'recommendation',
          catalogId: 'math-final-01',
          lifecycleStatus: 'draft',
          pipelineStage: 'idle',
          pipelineStatus: 'idle',
          updatedAt: DateTime.parse('2026-04-18T15:00:00+00:00'),
        ),
        createdFromCatalogId: 'math-final-01',
      ),
    );
    await tester.pumpAndSettle();
  });
}

class _FakeApiClient extends ApiClient {
  static const recommendationTitle = 'Calculus Final Sprint';
  static const createdCourseTitle = 'Calculus Final Sprint Course';

  _FakeApiClient({
    this.fetchCompleter,
    this.confirmCompleter,
  });

  final Completer<List<RecommendationCardModel>>? fetchCompleter;
  final Completer<ConfirmRecommendationResultModel>? confirmCompleter;

  final List<RecommendationRequestModel> recommendationRequests = [];
  final List<ConfirmRecommendationRequestModel> confirmationRequests = [];

  @override
  Future<List<RecommendationCardModel>> fetchRecommendations(
    RecommendationRequestModel request,
  ) async {
    recommendationRequests.add(request);
    return fetchCompleter?.future ??
        const [
          RecommendationCardModel(
            catalogId: 'math-final-01',
            title: recommendationTitle,
            provider: 'KnowLink Seed',
            level: 'intermediate',
            estimatedHours: 4,
            fitScore: 96,
            reasons: [
              'Difficulty matches the current level',
              'Duration fits the current budget',
            ],
            defaultResourceManifest: [
              ResourceManifestItemModel(
                resourceType: ResourceType.mp4,
                isRequired: true,
                description: 'Main lesson video',
              ),
              ResourceManifestItemModel(
                resourceType: ResourceType.pdf,
                isRequired: true,
                description: 'Companion lecture notes',
              ),
            ],
          ),
        ];
  }

  @override
  Future<ConfirmRecommendationResultModel> confirmRecommendation({
    required String catalogId,
    required ConfirmRecommendationRequestModel request,
    required String idempotencyKey,
  }) async {
    confirmationRequests.add(request);
    return confirmCompleter?.future ??
        ConfirmRecommendationResultModel(
          course: CourseSummaryModel(
            courseId: 101,
            title: createdCourseTitle,
            entryType: 'recommendation',
            catalogId: catalogId,
            lifecycleStatus: 'draft',
            pipelineStage: 'idle',
            pipelineStatus: 'idle',
            updatedAt: DateTime.parse('2026-04-18T15:00:00+00:00'),
          ),
          createdFromCatalogId: catalogId,
        );
  }
}

void _expectDraftInputsLocked(WidgetTester tester) {
  for (var index = 0; index < 3; index++) {
    final field = tester.widget<TextField>(find.byType(TextField).at(index));
    expect(field.enabled, isFalse);
  }

  final selfLevelDropdown = tester.widget<DropdownButtonFormField<SelfLevel>>(
    find.byType(DropdownButtonFormField<SelfLevel>),
  );
  final preferredStyleDropdown =
      tester.widget<DropdownButtonFormField<PreferredStyle>>(
    find.byType(DropdownButtonFormField<PreferredStyle>),
  );
  final fetchButton =
      tester.widget<FilledButton>(find.byType(FilledButton).first);

  expect(selfLevelDropdown.onChanged, isNull);
  expect(preferredStyleDropdown.onChanged, isNull);
  expect(fetchButton.onPressed, isNull);
}
