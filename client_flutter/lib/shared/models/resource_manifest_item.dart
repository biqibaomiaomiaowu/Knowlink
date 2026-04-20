import 'recommendation_enums.dart';

class ResourceManifestItemModel {
  const ResourceManifestItemModel({
    required this.resourceType,
    required this.isRequired,
    required this.description,
  });

  final ResourceType resourceType;
  final bool isRequired;
  final String description;

  factory ResourceManifestItemModel.fromJson(Map<String, dynamic> json) {
    return ResourceManifestItemModel(
      resourceType: ResourceType.values.byName(json['resourceType'] as String),
      isRequired: json['required'] as bool,
      description: json['description'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'resourceType': resourceType.name,
      'required': isRequired,
      'description': description,
    };
  }
}
