import 'course_summary.dart';

class ConfirmRecommendationResultModel {
  const ConfirmRecommendationResultModel({
    required this.course,
    required this.createdFromCatalogId,
  });

  final CourseSummaryModel course;
  final String createdFromCatalogId;

  factory ConfirmRecommendationResultModel.fromJson(
    Map<String, dynamic> json,
  ) {
    return ConfirmRecommendationResultModel(
      course: CourseSummaryModel.fromJson(
        Map<String, dynamic>.from(json['course'] as Map),
      ),
      createdFromCatalogId: json['createdFromCatalogId'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'course': course.toJson(),
      'createdFromCatalogId': createdFromCatalogId,
    };
  }
}
