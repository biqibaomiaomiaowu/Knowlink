import 'recommendation_enums.dart';

class RecommendationRequestModel {
  const RecommendationRequestModel({
    required this.goalText,
    required this.selfLevel,
    required this.timeBudgetMinutes,
    required this.preferredStyle,
    this.examAt,
  });

  static const weekOneDefaults = RecommendationRequestModel(
    goalText: '高等数学期末复习',
    selfLevel: SelfLevel.intermediate,
    timeBudgetMinutes: 240,
    preferredStyle: PreferredStyle.exam,
  );

  final String goalText;
  final SelfLevel selfLevel;
  final int timeBudgetMinutes;
  final DateTime? examAt;
  final PreferredStyle preferredStyle;

  RecommendationRequestModel copyWith({
    String? goalText,
    SelfLevel? selfLevel,
    int? timeBudgetMinutes,
    DateTime? examAt,
    bool clearExamAt = false,
    PreferredStyle? preferredStyle,
  }) {
    return RecommendationRequestModel(
      goalText: goalText ?? this.goalText,
      selfLevel: selfLevel ?? this.selfLevel,
      timeBudgetMinutes: timeBudgetMinutes ?? this.timeBudgetMinutes,
      examAt: clearExamAt ? null : examAt ?? this.examAt,
      preferredStyle: preferredStyle ?? this.preferredStyle,
    );
  }

  factory RecommendationRequestModel.fromJson(Map<String, dynamic> json) {
    return RecommendationRequestModel(
      goalText: json['goalText'] as String,
      selfLevel: SelfLevel.values.byName(json['selfLevel'] as String),
      timeBudgetMinutes: json['timeBudgetMinutes'] as int,
      examAt: json['examAt'] == null
          ? null
          : DateTime.parse(json['examAt'] as String),
      preferredStyle: PreferredStyle.values.byName(
        json['preferredStyle'] as String,
      ),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'goalText': goalText,
      'selfLevel': selfLevel.name,
      'timeBudgetMinutes': timeBudgetMinutes,
      if (examAt != null) 'examAt': dateTimeToOffsetIsoString(examAt!),
      'preferredStyle': preferredStyle.name,
    };
  }
}
