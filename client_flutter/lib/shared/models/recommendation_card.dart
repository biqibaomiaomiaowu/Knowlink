import 'resource_manifest_item.dart';

class RecommendationCardModel {
  const RecommendationCardModel({
    required this.catalogId,
    required this.title,
    required this.provider,
    required this.level,
    required this.estimatedHours,
    required this.fitScore,
    required this.reasons,
    required this.defaultResourceManifest,
  });

  final String catalogId;
  final String title;
  final String provider;
  final String level;
  final int estimatedHours;
  final int fitScore;
  final List<String> reasons;
  final List<ResourceManifestItemModel> defaultResourceManifest;

  factory RecommendationCardModel.fromJson(Map<String, dynamic> json) {
    return RecommendationCardModel(
      catalogId: json['catalogId'] as String,
      title: json['title'] as String,
      provider: json['provider'] as String,
      level: json['level'] as String,
      estimatedHours: json['estimatedHours'] as int,
      fitScore: json['fitScore'] as int,
      reasons: (json['reasons'] as List<dynamic>).cast<String>(),
      defaultResourceManifest:
          (json['defaultResourceManifest'] as List<dynamic>)
              .map(
                (item) => ResourceManifestItemModel.fromJson(
                  Map<String, dynamic>.from(item as Map),
                ),
              )
              .toList(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'catalogId': catalogId,
      'title': title,
      'provider': provider,
      'level': level,
      'estimatedHours': estimatedHours,
      'fitScore': fitScore,
      'reasons': reasons,
      'defaultResourceManifest':
          defaultResourceManifest.map((item) => item.toJson()).toList(),
    };
  }
}
