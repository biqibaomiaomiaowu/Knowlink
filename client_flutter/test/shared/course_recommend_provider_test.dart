import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:knowlink_client/core/network/api_client.dart';
import 'package:knowlink_client/shared/models/confirm_recommendation_request.dart';
import 'package:knowlink_client/shared/models/confirm_recommendation_result.dart';
import 'package:knowlink_client/shared/models/course_summary.dart';
import 'package:knowlink_client/shared/models/recommendation_card.dart';
import 'package:knowlink_client/shared/models/recommendation_enums.dart';
import 'package:knowlink_client/shared/models/recommendation_request.dart';
import 'package:knowlink_client/shared/models/resource_manifest_item.dart';
import 'package:knowlink_client/shared/providers/course_recommend_provider.dart';

void main() {
  test('course recommend provider starts with week 1 defaults', () {
    final container = ProviderContainer();
    addTearDown(container.dispose);

    final state = container.read(courseRecommendProvider);

    expect(state.requestDraft.goalText, '高等数学期末复习');
    expect(state.requestDraft.selfLevel, SelfLevel.intermediate);
    expect(state.requestDraft.timeBudgetMinutes, 240);
    expect(state.requestDraft.preferredStyle, PreferredStyle.exam);
    expect(state.recommendations.valueOrNull, isEmpty);
    expect(state.confirmation.valueOrNull, isNull);
    expect(state.lastConfirmIdempotencyKey, isNull);
  });

  test('fetchRecommendations uses updated draft and stores results', () async {
    final fakeApiClient = FakeApiClient(
      recommendations: [
        const RecommendationCardModel(
          catalogId: 'math-final-01',
          title: '高等数学期末冲刺',
          provider: 'KnowLink Seed',
          level: 'intermediate',
          estimatedHours: 4,
          fitScore: 96,
          reasons: ['难度与当前基础匹配'],
          defaultResourceManifest: [
            ResourceManifestItemModel(
              resourceType: ResourceType.mp4,
              isRequired: true,
              description: '主课程视频',
            ),
          ],
        ),
      ],
      confirmResult: null,
    );
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);

    final notifier = container.read(courseRecommendProvider.notifier);
    final examAt = DateTime.utc(2026, 6, 15, 1);
    notifier.updateDraft(
      goalText: '线性代数期末复习',
      timeBudgetMinutes: 180,
      examAt: examAt,
      selfLevel: SelfLevel.advanced,
      preferredStyle: PreferredStyle.quick,
    );

    await notifier.fetchRecommendations();

    expect(fakeApiClient.recommendationRequests, hasLength(1));
    expect(fakeApiClient.recommendationRequests.single.goalText, '线性代数期末复习');
    expect(fakeApiClient.recommendationRequests.single.timeBudgetMinutes, 180);
    expect(fakeApiClient.recommendationRequests.single.examAt, examAt);
    expect(fakeApiClient.recommendationRequests.single.selfLevel,
        SelfLevel.advanced);
    expect(fakeApiClient.recommendationRequests.single.preferredStyle,
        PreferredStyle.quick);

    final state = container.read(courseRecommendProvider);
    expect(state.recommendations.valueOrNull, hasLength(1));
    expect(
        state.recommendations.valueOrNull!.single.catalogId, 'math-final-01');
    expect(state.confirmation.valueOrNull, isNull);
  });

  test('updating draft clears stale recommendations and confirm metadata',
      () async {
    final fakeApiClient = FakeApiClient(
      recommendations: [
        const RecommendationCardModel(
          catalogId: 'math-final-01',
          title: '高等数学期末冲刺',
          provider: 'KnowLink Seed',
          level: 'intermediate',
          estimatedHours: 4,
          fitScore: 96,
          reasons: ['难度与当前基础匹配'],
          defaultResourceManifest: [
            ResourceManifestItemModel(
              resourceType: ResourceType.mp4,
              isRequired: true,
              description: '主课程视频',
            ),
          ],
        ),
      ],
      confirmResult: ConfirmRecommendationResultModel(
        course: CourseSummaryModel(
          courseId: 101,
          title: '高数期末冲刺课',
          entryType: 'recommendation',
          catalogId: 'math-final-01',
          lifecycleStatus: 'draft',
          pipelineStage: 'idle',
          pipelineStatus: 'idle',
          updatedAt: DateTime.utc(2026, 4, 18, 15),
        ),
        createdFromCatalogId: 'math-final-01',
      ),
    );
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);

    final notifier = container.read(courseRecommendProvider.notifier);

    await notifier.fetchRecommendations();
    await notifier.confirmRecommendation('math-final-01');

    notifier.updateDraft(goalText: '改了条件');

    final state = container.read(courseRecommendProvider);
    expect(state.recommendations.valueOrNull, isEmpty);
    expect(state.confirmation.valueOrNull, isNull);
    expect(state.lastConfirmCatalogId, isNull);
    expect(state.lastConfirmFingerprint, isNull);
    expect(state.lastConfirmIdempotencyKey, isNull);
  });

  test('stale fetch results are ignored after the draft changes', () async {
    final fetchCompleter = Completer<List<RecommendationCardModel>>();
    final fakeApiClient = FakeApiClient(
      recommendations: const [],
      confirmResult: null,
      onFetch: (_) => fetchCompleter.future,
    );
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);

    final notifier = container.read(courseRecommendProvider.notifier);

    final fetchFuture = notifier.fetchRecommendations();
    notifier.updateDraft(goalText: '新的推荐条件');

    fetchCompleter.complete([
      const RecommendationCardModel(
        catalogId: 'math-final-01',
        title: '旧推荐结果',
        provider: 'KnowLink Seed',
        level: 'intermediate',
        estimatedHours: 4,
        fitScore: 96,
        reasons: ['旧请求返回'],
        defaultResourceManifest: [],
      ),
    ]);
    await fetchFuture;

    final state = container.read(courseRecommendProvider);
    expect(state.requestDraft.goalText, '新的推荐条件');
    expect(state.recommendations.valueOrNull, isEmpty);
    expect(state.confirmation.valueOrNull, isNull);
  });

  test('confirmRecommendation reuses idempotency key for identical retry',
      () async {
    final fakeApiClient = FakeApiClient(
      recommendations: const [],
      confirmResult: ConfirmRecommendationResultModel(
        course: CourseSummaryModel(
          courseId: 101,
          title: '高数期末冲刺课',
          entryType: 'recommendation',
          catalogId: 'math-final-01',
          lifecycleStatus: 'draft',
          pipelineStage: 'idle',
          pipelineStatus: 'idle',
          updatedAt: DateTime.utc(2026, 4, 18, 15),
        ),
        createdFromCatalogId: 'math-final-01',
      ),
      failFirstConfirm: true,
    );
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);

    final notifier = container.read(courseRecommendProvider.notifier);

    await notifier.confirmRecommendation('math-final-01');
    var state = container.read(courseRecommendProvider);
    expect(state.confirmation.hasError, isTrue);
    expect(state.lastConfirmCatalogId, 'math-final-01');
    expect(state.lastConfirmIdempotencyKey, isNotNull);

    final firstKey = state.lastConfirmIdempotencyKey;

    await notifier.confirmRecommendation('math-final-01');
    state = container.read(courseRecommendProvider);

    expect(fakeApiClient.confirmCalls, hasLength(2));
    expect(fakeApiClient.confirmCalls.first.idempotencyKey, firstKey);
    expect(fakeApiClient.confirmCalls.last.idempotencyKey, firstKey);
    expect(
        state.confirmation.valueOrNull?.createdFromCatalogId, 'math-final-01');
    expect(state.confirmation.valueOrNull?.course.courseId, 101);
    expect(state.lastConfirmIdempotencyKey, firstKey);
    expect(state.activeConfirmCatalogId, isNull);
  });

  test('confirmRecommendation reuses session key after provider disposal',
      () async {
    final fakeApiClient = FakeApiClient(
      recommendations: const [],
      confirmResult: ConfirmRecommendationResultModel(
        course: CourseSummaryModel(
          courseId: 101,
          title: '高数期末冲刺课',
          entryType: 'recommendation',
          catalogId: 'math-final-01',
          lifecycleStatus: 'draft',
          pipelineStage: 'idle',
          pipelineStatus: 'idle',
          updatedAt: DateTime.utc(2026, 4, 18, 15),
        ),
        createdFromCatalogId: 'math-final-01',
      ),
    );
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);

    final subscription = container.listen(
      courseRecommendProvider,
      (_, __) {},
      fireImmediately: true,
    );

    await container
        .read(courseRecommendProvider.notifier)
        .confirmRecommendation('math-final-01');
    final firstKey = fakeApiClient.confirmCalls.single.idempotencyKey;

    subscription.close();
    await container.pump();

    await container
        .read(courseRecommendProvider.notifier)
        .confirmRecommendation('math-final-01');

    expect(fakeApiClient.confirmCalls, hasLength(2));
    expect(fakeApiClient.confirmCalls.first.idempotencyKey, firstKey);
    expect(fakeApiClient.confirmCalls.last.idempotencyKey, firstKey);
  });

  test('fetchRecommendations keeps session idempotency key for same confirm',
      () async {
    final fakeApiClient = FakeApiClient(
      recommendations: const [],
      confirmResult: ConfirmRecommendationResultModel(
        course: CourseSummaryModel(
          courseId: 101,
          title: '高数期末冲刺课',
          entryType: 'recommendation',
          catalogId: 'math-final-01',
          lifecycleStatus: 'draft',
          pipelineStage: 'idle',
          pipelineStatus: 'idle',
          updatedAt: DateTime.utc(2026, 4, 18, 15),
        ),
        createdFromCatalogId: 'math-final-01',
      ),
    );
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);

    final notifier = container.read(courseRecommendProvider.notifier);

    await notifier.confirmRecommendation('math-final-01');
    final firstKey = fakeApiClient.confirmCalls.single.idempotencyKey;

    await notifier.fetchRecommendations();
    await notifier.confirmRecommendation('math-final-01');

    expect(fakeApiClient.confirmCalls, hasLength(2));
    expect(fakeApiClient.confirmCalls.first.idempotencyKey, firstKey);
    expect(fakeApiClient.confirmCalls.last.idempotencyKey, firstKey);
  });

  test('stale confirm results are ignored after the draft changes', () async {
    final confirmCompleter = Completer<ConfirmRecommendationResultModel>();
    final fakeApiClient = FakeApiClient(
      recommendations: const [],
      confirmResult: ConfirmRecommendationResultModel(
        course: CourseSummaryModel(
          courseId: 101,
          title: '高数期末冲刺课',
          entryType: 'recommendation',
          catalogId: 'math-final-01',
          lifecycleStatus: 'draft',
          pipelineStage: 'idle',
          pipelineStatus: 'idle',
          updatedAt: DateTime.utc(2026, 4, 18, 15),
        ),
        createdFromCatalogId: 'math-final-01',
      ),
      onConfirm: ({
        required String catalogId,
        required ConfirmRecommendationRequestModel request,
        required String idempotencyKey,
      }) =>
          confirmCompleter.future,
    );
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);

    final notifier = container.read(courseRecommendProvider.notifier);

    final confirmFuture = notifier.confirmRecommendation('math-final-01');
    notifier.updateDraft(goalText: '新的确认条件');

    confirmCompleter.complete(
      ConfirmRecommendationResultModel(
        course: CourseSummaryModel(
          courseId: 101,
          title: '高数期末冲刺课',
          entryType: 'recommendation',
          catalogId: 'math-final-01',
          lifecycleStatus: 'draft',
          pipelineStage: 'idle',
          pipelineStatus: 'idle',
          updatedAt: DateTime.utc(2026, 4, 18, 15),
        ),
        createdFromCatalogId: 'math-final-01',
      ),
    );
    await confirmFuture;

    final state = container.read(courseRecommendProvider);
    expect(state.requestDraft.goalText, '新的确认条件');
    expect(state.confirmation.valueOrNull, isNull);
    expect(state.lastConfirmCatalogId, isNull);
    expect(state.lastConfirmFingerprint, isNull);
    expect(state.lastConfirmIdempotencyKey, isNull);
    expect(state.activeConfirmCatalogId, isNull);
  });
}

class FakeApiClient extends ApiClient {
  FakeApiClient({
    required this.recommendations,
    required this.confirmResult,
    this.failFirstConfirm = false,
    this.onFetch,
    this.onConfirm,
  });

  final List<RecommendationCardModel> recommendations;
  final ConfirmRecommendationResultModel? confirmResult;
  final bool failFirstConfirm;
  final Future<List<RecommendationCardModel>> Function(
    RecommendationRequestModel request,
  )? onFetch;
  final Future<ConfirmRecommendationResultModel> Function({
    required String catalogId,
    required ConfirmRecommendationRequestModel request,
    required String idempotencyKey,
  })? onConfirm;

  final List<RecommendationRequestModel> recommendationRequests = [];
  final List<ConfirmCallRecord> confirmCalls = [];

  @override
  Future<List<RecommendationCardModel>> fetchRecommendations(
    RecommendationRequestModel request,
  ) async {
    recommendationRequests.add(request);
    if (onFetch != null) {
      return onFetch!(request);
    }
    return recommendations;
  }

  @override
  Future<ConfirmRecommendationResultModel> confirmRecommendation({
    required String catalogId,
    required ConfirmRecommendationRequestModel request,
    required String idempotencyKey,
  }) async {
    confirmCalls.add(
      ConfirmCallRecord(
        catalogId: catalogId,
        request: request,
        idempotencyKey: idempotencyKey,
      ),
    );

    if (onConfirm != null) {
      return onConfirm!(
        catalogId: catalogId,
        request: request,
        idempotencyKey: idempotencyKey,
      );
    }

    if (failFirstConfirm && confirmCalls.length == 1) {
      throw StateError('temporary confirm failure');
    }

    return confirmResult!;
  }
}

class ConfirmCallRecord {
  const ConfirmCallRecord({
    required this.catalogId,
    required this.request,
    required this.idempotencyKey,
  });

  final String catalogId;
  final ConfirmRecommendationRequestModel request;
  final String idempotencyKey;
}
