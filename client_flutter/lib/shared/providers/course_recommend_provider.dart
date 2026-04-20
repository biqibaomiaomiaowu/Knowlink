import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/network/api_client.dart';
import '../models/confirm_recommendation_request.dart';
import '../models/course_recommend_state.dart';
import '../models/recommendation_enums.dart';
import '../models/recommendation_card.dart';

final apiClientProvider = Provider<ApiClient>((ref) => ApiClient());

class CourseRecommendController
    extends AutoDisposeNotifier<CourseRecommendState> {
  var _draftVersion = 0;
  var _latestFetchRequestId = 0;
  var _latestConfirmRequestId = 0;
  var _isDisposed = false;

  @override
  CourseRecommendState build() {
    _isDisposed = false;
    ref.onDispose(() {
      _isDisposed = true;
    });
    return CourseRecommendState.initial();
  }

  void updateDraft({
    String? goalText,
    int? timeBudgetMinutes,
    DateTime? examAt,
    bool clearExamAt = false,
    SelfLevel? selfLevel,
    PreferredStyle? preferredStyle,
  }) {
    _draftVersion++;
    state = state.copyWith(
      requestDraft: state.requestDraft.copyWith(
        goalText: goalText,
        timeBudgetMinutes: timeBudgetMinutes,
        examAt: examAt,
        clearExamAt: clearExamAt,
        selfLevel: selfLevel,
        preferredStyle: preferredStyle,
      ),
      recommendations: const AsyncData(<RecommendationCardModel>[]),
      confirmation: const AsyncData(null),
      clearActiveConfirmCatalogId: true,
      clearLastConfirmCatalogId: true,
      clearLastConfirmFingerprint: true,
      clearLastConfirmIdempotencyKey: true,
    );
  }

  Future<void> fetchRecommendations() async {
    final request = state.requestDraft;
    final draftVersion = _draftVersion;
    final requestId = ++_latestFetchRequestId;
    state = state.copyWith(
      recommendations: const AsyncLoading(),
      confirmation: const AsyncData(null),
      clearActiveConfirmCatalogId: true,
      clearLastConfirmCatalogId: true,
      clearLastConfirmFingerprint: true,
      clearLastConfirmIdempotencyKey: true,
    );

    final apiClient = ref.read(apiClientProvider);

    try {
      final recommendations = await apiClient.fetchRecommendations(request);
      if (!_shouldApplyFetchResult(
        requestId: requestId,
        draftVersion: draftVersion,
      )) {
        return;
      }
      state = state.copyWith(recommendations: AsyncData(recommendations));
    } catch (error, stackTrace) {
      if (!_shouldApplyFetchResult(
        requestId: requestId,
        draftVersion: draftVersion,
      )) {
        return;
      }
      state = state.copyWith(
        recommendations: AsyncError(error, stackTrace),
      );
    }
  }

  Future<void> confirmRecommendation(
    String catalogId, {
    String? titleOverride,
  }) async {
    if (state.isConfirming) {
      return;
    }

    final apiClient = ref.read(apiClientProvider);
    final draftVersion = _draftVersion;
    final request = ConfirmRecommendationRequestModel.fromRecommendationRequest(
      state.requestDraft,
      titleOverride: titleOverride,
    );
    final fingerprint = _buildConfirmFingerprint(
      catalogId: catalogId,
      request: request,
    );
    final idempotencyKey = _resolveIdempotencyKey(
      fingerprint: fingerprint,
      catalogId: catalogId,
    );
    final requestId = ++_latestConfirmRequestId;

    state = state.copyWith(
      confirmation: const AsyncLoading(),
      activeConfirmCatalogId: catalogId,
      lastConfirmCatalogId: catalogId,
      lastConfirmFingerprint: fingerprint,
      lastConfirmIdempotencyKey: idempotencyKey,
    );

    try {
      final result = await apiClient.confirmRecommendation(
        catalogId: catalogId,
        request: request,
        idempotencyKey: idempotencyKey,
      );
      if (!_shouldApplyConfirmResult(
        requestId: requestId,
        draftVersion: draftVersion,
      )) {
        return;
      }
      state = state.copyWith(
        confirmation: AsyncData(result),
        clearActiveConfirmCatalogId: true,
        lastConfirmCatalogId: catalogId,
        lastConfirmFingerprint: fingerprint,
        lastConfirmIdempotencyKey: idempotencyKey,
      );
    } catch (error, stackTrace) {
      if (!_shouldApplyConfirmResult(
        requestId: requestId,
        draftVersion: draftVersion,
      )) {
        return;
      }
      state = state.copyWith(
        confirmation: AsyncError(error, stackTrace),
        clearActiveConfirmCatalogId: true,
        lastConfirmCatalogId: catalogId,
        lastConfirmFingerprint: fingerprint,
        lastConfirmIdempotencyKey: idempotencyKey,
      );
    }
  }

  bool _shouldApplyFetchResult({
    required int requestId,
    required int draftVersion,
  }) {
    return !_isDisposed &&
        requestId == _latestFetchRequestId &&
        draftVersion == _draftVersion;
  }

  bool _shouldApplyConfirmResult({
    required int requestId,
    required int draftVersion,
  }) {
    return !_isDisposed &&
        requestId == _latestConfirmRequestId &&
        draftVersion == _draftVersion;
  }

  String _buildConfirmFingerprint({
    required String catalogId,
    required ConfirmRecommendationRequestModel request,
  }) {
    return [
      catalogId,
      request.goalText,
      request.preferredStyle.name,
      request.examAt?.toIso8601String() ?? '',
      request.titleOverride ?? '',
    ].join('|');
  }

  String _resolveIdempotencyKey({
    required String fingerprint,
    required String catalogId,
  }) {
    if (state.lastConfirmFingerprint == fingerprint &&
        state.lastConfirmIdempotencyKey != null) {
      return state.lastConfirmIdempotencyKey!;
    }

    return 'recommend-confirm-$catalogId-${DateTime.now().microsecondsSinceEpoch}';
  }
}

final courseRecommendProvider = AutoDisposeNotifierProvider<
    CourseRecommendController, CourseRecommendState>(
  CourseRecommendController.new,
);
