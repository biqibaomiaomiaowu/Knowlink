import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'confirm_recommendation_result.dart';
import 'recommendation_card.dart';
import 'recommendation_request.dart';

class CourseRecommendState {
  const CourseRecommendState({
    required this.requestDraft,
    required this.recommendations,
    required this.confirmation,
    this.activeConfirmCatalogId,
    this.lastConfirmCatalogId,
    this.lastConfirmFingerprint,
    this.lastConfirmIdempotencyKey,
  });

  factory CourseRecommendState.initial() {
    return const CourseRecommendState(
      requestDraft: RecommendationRequestModel.weekOneDefaults,
      recommendations: AsyncData(<RecommendationCardModel>[]),
      confirmation: AsyncData<ConfirmRecommendationResultModel?>(null),
    );
  }

  final RecommendationRequestModel requestDraft;
  final AsyncValue<List<RecommendationCardModel>> recommendations;
  final AsyncValue<ConfirmRecommendationResultModel?> confirmation;
  final String? activeConfirmCatalogId;
  final String? lastConfirmCatalogId;
  final String? lastConfirmFingerprint;
  final String? lastConfirmIdempotencyKey;

  bool get isFetchingRecommendations => recommendations.isLoading;
  bool get isConfirming => confirmation.isLoading;

  CourseRecommendState copyWith({
    RecommendationRequestModel? requestDraft,
    AsyncValue<List<RecommendationCardModel>>? recommendations,
    AsyncValue<ConfirmRecommendationResultModel?>? confirmation,
    String? activeConfirmCatalogId,
    bool clearActiveConfirmCatalogId = false,
    String? lastConfirmCatalogId,
    bool clearLastConfirmCatalogId = false,
    String? lastConfirmFingerprint,
    bool clearLastConfirmFingerprint = false,
    String? lastConfirmIdempotencyKey,
    bool clearLastConfirmIdempotencyKey = false,
  }) {
    return CourseRecommendState(
      requestDraft: requestDraft ?? this.requestDraft,
      recommendations: recommendations ?? this.recommendations,
      confirmation: confirmation ?? this.confirmation,
      activeConfirmCatalogId: clearActiveConfirmCatalogId
          ? null
          : activeConfirmCatalogId ?? this.activeConfirmCatalogId,
      lastConfirmCatalogId: clearLastConfirmCatalogId
          ? null
          : lastConfirmCatalogId ?? this.lastConfirmCatalogId,
      lastConfirmFingerprint: clearLastConfirmFingerprint
          ? null
          : lastConfirmFingerprint ?? this.lastConfirmFingerprint,
      lastConfirmIdempotencyKey: clearLastConfirmIdempotencyKey
          ? null
          : lastConfirmIdempotencyKey ?? this.lastConfirmIdempotencyKey,
    );
  }
}
