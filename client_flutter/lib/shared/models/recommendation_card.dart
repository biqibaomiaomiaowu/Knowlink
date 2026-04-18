class RecommendationCardModel {
  const RecommendationCardModel({
    required this.catalogId,
    required this.title,
    required this.provider,
    required this.level,
    required this.estimatedHours,
    required this.fitScore,
    required this.reasons,
  });

  final String catalogId;
  final String title;
  final String provider;
  final String level;
  final int estimatedHours;
  final int fitScore;
  final List<String> reasons;

  factory RecommendationCardModel.fromJson(Map<String, dynamic> json) {
    return RecommendationCardModel(
      catalogId: json['catalogId'] as String,
      title: json['title'] as String,
      provider: json['provider'] as String,
      level: json['level'] as String,
      estimatedHours: json['estimatedHours'] as int,
      fitScore: json['fitScore'] as int,
      reasons: (json['reasons'] as List<dynamic>).cast<String>(),
    );
  }
}
