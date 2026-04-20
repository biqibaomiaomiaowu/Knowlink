import 'recommendation_enums.dart';
import 'recommendation_request.dart';

class ConfirmRecommendationRequestModel {
  const ConfirmRecommendationRequestModel({
    required this.goalText,
    required this.preferredStyle,
    this.examAt,
    this.titleOverride,
  });

  final String goalText;
  final DateTime? examAt;
  final PreferredStyle preferredStyle;
  final String? titleOverride;

  factory ConfirmRecommendationRequestModel.fromRecommendationRequest(
    RecommendationRequestModel request, {
    String? titleOverride,
  }) {
    return ConfirmRecommendationRequestModel(
      goalText: request.goalText,
      examAt: request.examAt,
      preferredStyle: request.preferredStyle,
      titleOverride: titleOverride,
    );
  }

  factory ConfirmRecommendationRequestModel.fromJson(
      Map<String, dynamic> json) {
    return ConfirmRecommendationRequestModel(
      goalText: json['goalText'] as String,
      examAt: json['examAt'] == null
          ? null
          : DateTime.parse(json['examAt'] as String),
      preferredStyle: PreferredStyle.values.byName(
        json['preferredStyle'] as String,
      ),
      titleOverride: json['titleOverride'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'goalText': goalText,
      if (examAt != null) 'examAt': dateTimeToOffsetIsoString(examAt!),
      'preferredStyle': preferredStyle.name,
      if (titleOverride != null && titleOverride!.isNotEmpty)
        'titleOverride': titleOverride,
    };
  }
}
