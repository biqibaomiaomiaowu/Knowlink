import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'review_models.dart';

class ReviewState {
  const ReviewState({
    required this.review,
    required this.regeneration,
    required this.runStatus,
    required this.completion,
    this.completingTaskId,
    this.isPolling = false,
  });

  factory ReviewState.initial() {
    return const ReviewState(
      review: AsyncData<CourseReviewModel?>(null),
      regeneration: AsyncData<ReviewRegenerateResultModel?>(null),
      runStatus: AsyncData<ReviewRunStatusModel?>(null),
      completion: AsyncData<CompleteReviewTaskResultModel?>(null),
    );
  }

  final AsyncValue<CourseReviewModel?> review;
  final AsyncValue<ReviewRegenerateResultModel?> regeneration;
  final AsyncValue<ReviewRunStatusModel?> runStatus;
  final AsyncValue<CompleteReviewTaskResultModel?> completion;
  final int? completingTaskId;
  final bool isPolling;

  CourseReviewModel? get reviewValue => review.valueOrNull;
  CourseReviewModel? get tasksValue => reviewValue;
  ReviewRunStatusModel? get runStatusValue => runStatus.valueOrNull;
  bool get isRegenerating => regeneration.isLoading || isPolling;
  bool get isCompleting => completion.isLoading;

  ReviewState copyWith({
    AsyncValue<CourseReviewModel?>? review,
    AsyncValue<ReviewRegenerateResultModel?>? regeneration,
    AsyncValue<ReviewRunStatusModel?>? runStatus,
    AsyncValue<CompleteReviewTaskResultModel?>? completion,
    int? completingTaskId,
    bool clearCompletingTaskId = false,
    bool? isPolling,
  }) {
    return ReviewState(
      review: review ?? this.review,
      regeneration: regeneration ?? this.regeneration,
      runStatus: runStatus ?? this.runStatus,
      completion: completion ?? this.completion,
      completingTaskId: clearCompletingTaskId
          ? null
          : completingTaskId ?? this.completingTaskId,
      isPolling: isPolling ?? this.isPolling,
    );
  }
}
