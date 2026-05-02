import 'recommendation_enums.dart';

class ResourceUploadInitRequestModel {
  const ResourceUploadInitRequestModel({
    required this.resourceType,
    required this.filename,
    required this.mimeType,
    required this.sizeBytes,
    required this.checksum,
  });

  final ResourceType resourceType;
  final String filename;
  final String mimeType;
  final int sizeBytes;
  final String checksum;

  Map<String, dynamic> toJson() {
    return {
      'resourceType': resourceType.name,
      'filename': filename,
      'mimeType': mimeType,
      'sizeBytes': sizeBytes,
      'checksum': checksum,
    };
  }
}

class ResourceUploadInitResultModel {
  const ResourceUploadInitResultModel({
    required this.uploadUrl,
    required this.objectKey,
    required this.headers,
    required this.expiresAt,
  });

  final String uploadUrl;
  final String objectKey;
  final Map<String, String> headers;
  final DateTime expiresAt;

  factory ResourceUploadInitResultModel.fromJson(Map<String, dynamic> json) {
    return ResourceUploadInitResultModel(
      uploadUrl: json['uploadUrl'] as String,
      objectKey: json['objectKey'] as String,
      headers: (json['headers'] as Map<String, dynamic>? ?? const {})
          .map((key, value) => MapEntry(key, value.toString())),
      expiresAt: DateTime.parse(json['expiresAt'] as String),
    );
  }
}

class ResourceUploadCompleteRequestModel {
  const ResourceUploadCompleteRequestModel({
    required this.resourceType,
    required this.objectKey,
    required this.originalName,
    required this.mimeType,
    required this.sizeBytes,
    required this.checksum,
  });

  final ResourceType resourceType;
  final String objectKey;
  final String originalName;
  final String mimeType;
  final int sizeBytes;
  final String checksum;

  Map<String, dynamic> toJson() {
    return {
      'resourceType': resourceType.name,
      'objectKey': objectKey,
      'originalName': originalName,
      'mimeType': mimeType,
      'sizeBytes': sizeBytes,
      'checksum': checksum,
    };
  }
}

class CourseResourceModel {
  const CourseResourceModel({
    required this.resourceId,
    required this.resourceType,
    required this.originalName,
    required this.objectKey,
    required this.ingestStatus,
    required this.validationStatus,
    required this.processingStatus,
  });

  final int resourceId;
  final ResourceType resourceType;
  final String originalName;
  final String objectKey;
  final String ingestStatus;
  final String validationStatus;
  final String processingStatus;

  factory CourseResourceModel.fromJson(Map<String, dynamic> json) {
    return CourseResourceModel(
      resourceId: json['resourceId'] as int,
      resourceType: _resourceTypeFromName(json['resourceType'] as String),
      originalName: json['originalName'] as String,
      objectKey: json['objectKey'] as String,
      ingestStatus: json['ingestStatus'] as String,
      validationStatus: json['validationStatus'] as String,
      processingStatus: json['processingStatus'] as String,
    );
  }
}

class DeleteCourseResourceResultModel {
  const DeleteCourseResourceResultModel({
    required this.deleted,
    required this.resourceId,
  });

  final bool deleted;
  final int resourceId;

  factory DeleteCourseResourceResultModel.fromJson(Map<String, dynamic> json) {
    return DeleteCourseResourceResultModel(
      deleted: json['deleted'] as bool,
      resourceId: json['resourceId'] as int,
    );
  }
}

ResourceType _resourceTypeFromName(String value) {
  for (final type in ResourceType.values) {
    if (type.name == value) {
      return type;
    }
  }
  throw ArgumentError.value(value, 'resourceType', 'Unsupported resource type');
}
