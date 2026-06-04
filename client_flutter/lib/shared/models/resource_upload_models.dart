import 'recommendation_enums.dart';

class ResourceUploadInitRequestModel {
  const ResourceUploadInitRequestModel({
    required this.resourceType,
    required this.filename,
    required this.mimeType,
    required this.sizeBytes,
    required this.checksum,
    this.scopeType,
    this.lessonId,
    this.usageRole,
    this.lessonPlacement,
    this.lessonTitle,
    this.visibleToCourseQa,
  });

  final ResourceType resourceType;
  final String filename;
  final String mimeType;
  final int sizeBytes;
  final String checksum;
  final String? scopeType;
  final String? lessonId;
  final String? usageRole;
  final String? lessonPlacement;
  final String? lessonTitle;
  final bool? visibleToCourseQa;

  Map<String, dynamic> toJson() {
    return {
      'resourceType': resourceType.name,
      'filename': filename,
      'mimeType': mimeType,
      'sizeBytes': sizeBytes,
      'checksum': checksum,
      if (scopeType != null) 'scopeType': scopeType,
      if (lessonId != null) 'lessonId': lessonId,
      if (usageRole != null) 'usageRole': usageRole,
      if (lessonPlacement != null) 'lessonPlacement': lessonPlacement,
      if (lessonTitle != null) 'lessonTitle': lessonTitle,
      if (visibleToCourseQa != null) 'visibleToCourseQa': visibleToCourseQa,
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
    this.scopeType,
    this.lessonId,
    this.usageRole,
    this.lessonPlacement,
    this.lessonTitle,
    this.visibleToCourseQa,
  });

  final ResourceType resourceType;
  final String objectKey;
  final String originalName;
  final String mimeType;
  final int sizeBytes;
  final String checksum;
  final String? scopeType;
  final String? lessonId;
  final String? usageRole;
  final String? lessonPlacement;
  final String? lessonTitle;
  final bool? visibleToCourseQa;

  Map<String, dynamic> toJson() {
    return {
      'resourceType': resourceType.name,
      'objectKey': objectKey,
      'originalName': originalName,
      'mimeType': mimeType,
      'sizeBytes': sizeBytes,
      'checksum': checksum,
      if (scopeType != null) 'scopeType': scopeType,
      if (lessonId != null) 'lessonId': lessonId,
      if (usageRole != null) 'usageRole': usageRole,
      if (lessonPlacement != null) 'lessonPlacement': lessonPlacement,
      if (lessonTitle != null) 'lessonTitle': lessonTitle,
      if (visibleToCourseQa != null) 'visibleToCourseQa': visibleToCourseQa,
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
    this.scopeType = 'course',
    this.lessonId,
    this.usageRole = 'course_material',
    this.visibleToCourseQa = true,
    this.durationSec,
  });

  final int resourceId;
  final ResourceType resourceType;
  final String originalName;
  final String objectKey;
  final String ingestStatus;
  final String validationStatus;
  final String processingStatus;
  final String scopeType;
  final String? lessonId;
  final String usageRole;
  final bool visibleToCourseQa;
  final int? durationSec;

  factory CourseResourceModel.fromJson(Map<String, dynamic> json) {
    return CourseResourceModel(
      resourceId: json['resourceId'] as int,
      resourceType: _resourceTypeFromName(json['resourceType'] as String),
      originalName: json['originalName'] as String,
      objectKey: json['objectKey'] as String,
      ingestStatus: json['ingestStatus'] as String,
      validationStatus: json['validationStatus'] as String,
      processingStatus: json['processingStatus'] as String,
      scopeType: json['scopeType'] as String? ?? 'course',
      lessonId: json['lessonId']?.toString(),
      usageRole: json['usageRole'] as String? ?? 'course_material',
      visibleToCourseQa: json['visibleToCourseQa'] as bool? ?? true,
      durationSec: json['durationSec'] as int?,
    );
  }
}

class CourseResourcePlaybackModel {
  const CourseResourcePlaybackModel({
    required this.resourceId,
    required this.resourceType,
    required this.playbackUrl,
    required this.mimeType,
    required this.expiresAt,
    this.durationSec,
  });

  final int resourceId;
  final ResourceType resourceType;
  final String playbackUrl;
  final String mimeType;
  final DateTime expiresAt;
  final int? durationSec;

  factory CourseResourcePlaybackModel.fromJson(Map<String, dynamic> json) {
    return CourseResourcePlaybackModel(
      resourceId: json['resourceId'] as int,
      resourceType: _resourceTypeFromName(json['resourceType'] as String),
      playbackUrl: json['playbackUrl'] as String,
      mimeType: json['mimeType'] as String,
      expiresAt: DateTime.parse(json['expiresAt'] as String),
      durationSec: json['durationSec'] as int?,
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
