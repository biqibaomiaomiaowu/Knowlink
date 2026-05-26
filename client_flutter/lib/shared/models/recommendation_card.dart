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
    this.reasonMaterials = const [],
    this.nextAction = const RecommendationNextActionModel(
      type: 'confirm_course',
      label: '选择课程并进入导入',
    ),
    required this.defaultResourceManifest,
  });

  final String catalogId;
  final String title;
  final String provider;
  final String level;
  final int estimatedHours;
  final int fitScore;
  final List<String> reasons;
  final List<String> reasonMaterials;
  final RecommendationNextActionModel nextAction;
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
      reasonMaterials: (json['reasonMaterials'] as List<dynamic>? ?? const [])
          .cast<String>(),
      nextAction: json['nextAction'] == null
          ? const RecommendationNextActionModel(
              type: 'confirm_course',
              label: '选择课程并进入导入',
            )
          : RecommendationNextActionModel.fromJson(
              Map<String, dynamic>.from(json['nextAction'] as Map),
            ),
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
      'reasonMaterials': reasonMaterials,
      'nextAction': nextAction.toJson(),
      'defaultResourceManifest':
          defaultResourceManifest.map((item) => item.toJson()).toList(),
    };
  }
}

class RecommendationNextActionModel {
  const RecommendationNextActionModel({
    required this.type,
    required this.label,
  });

  factory RecommendationNextActionModel.fromJson(Map<String, dynamic> json) {
    return RecommendationNextActionModel(
      type: json['type'] as String? ?? 'confirm_course',
      label: json['label'] as String? ?? '选择课程并进入导入',
    );
  }

  final String type;
  final String label;

  bool get canConfirmCourse => type == 'confirm_course';

  Map<String, dynamic> toJson() {
    return {
      'type': type,
      'label': label,
    };
  }
}
