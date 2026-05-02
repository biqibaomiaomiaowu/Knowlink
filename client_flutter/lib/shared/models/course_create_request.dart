import 'recommendation_enums.dart';

class CourseCreateRequestModel {
  const CourseCreateRequestModel({
    required this.title,
    required this.goalText,
    this.entryType = 'manual_import',
    this.examAt,
    this.preferredStyle = PreferredStyle.balanced,
  });

  final String title;
  final String entryType;
  final String goalText;
  final DateTime? examAt;
  final PreferredStyle preferredStyle;

  Map<String, dynamic> toJson() {
    return {
      'title': title,
      'entryType': entryType,
      'goalText': goalText,
      'examAt': examAt == null ? null : dateTimeToOffsetIsoString(examAt!),
      'preferredStyle': preferredStyle.name,
    };
  }
}
