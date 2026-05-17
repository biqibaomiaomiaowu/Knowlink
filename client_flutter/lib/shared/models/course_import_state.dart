import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'course_summary.dart';
import 'recommendation_enums.dart';
import 'resource_upload_models.dart';

class CourseImportDraftModel {
  const CourseImportDraftModel({
    this.title = 'KnowLink 固定联调课',
    this.goalText = '期末复习',
    this.examAtText = '',
    this.preferredStyle = PreferredStyle.balanced,
  });

  final String title;
  final String goalText;
  final String examAtText;
  final PreferredStyle preferredStyle;

  DateTime? get parsedExamAt {
    final trimmed = examAtText.trim();
    return trimmed.isEmpty ? null : DateTime.tryParse(trimmed);
  }

  bool get hasInvalidExamAt {
    return examAtText.trim().isNotEmpty && parsedExamAt == null;
  }

  bool get canSubmit {
    return title.trim().isNotEmpty &&
        goalText.trim().isNotEmpty &&
        !hasInvalidExamAt;
  }

  CourseImportDraftModel copyWith({
    String? title,
    String? goalText,
    String? examAtText,
    PreferredStyle? preferredStyle,
  }) {
    return CourseImportDraftModel(
      title: title ?? this.title,
      goalText: goalText ?? this.goalText,
      examAtText: examAtText ?? this.examAtText,
      preferredStyle: preferredStyle ?? this.preferredStyle,
    );
  }
}

class UploadQueueItemModel {
  const UploadQueueItemModel({
    required this.id,
    required this.name,
    required this.resourceType,
    required this.mimeType,
    required this.sizeBytes,
    required this.checksum,
    required this.bytes,
    this.status = 'pending',
    this.errorMessage,
    this.resource,
  });

  final String id;
  final String name;
  final ResourceType resourceType;
  final String mimeType;
  final int sizeBytes;
  final String checksum;
  final Uint8List bytes;
  final String status;
  final String? errorMessage;
  final CourseResourceModel? resource;

  bool get isPending => status == 'pending';
  bool get isUploading => status == 'uploading';
  bool get isReady => status == 'ready';
  bool get hasFailed => status == 'failed';

  UploadQueueItemModel copyWith({
    String? status,
    String? errorMessage,
    bool clearErrorMessage = false,
    CourseResourceModel? resource,
  }) {
    return UploadQueueItemModel(
      id: id,
      name: name,
      resourceType: resourceType,
      mimeType: mimeType,
      sizeBytes: sizeBytes,
      checksum: checksum,
      bytes: bytes,
      status: status ?? this.status,
      errorMessage:
          clearErrorMessage ? null : errorMessage ?? this.errorMessage,
      resource: resource ?? this.resource,
    );
  }
}

class CourseImportState {
  const CourseImportState({
    this.draft = const CourseImportDraftModel(),
    this.createdCourse = const AsyncData<CourseSummaryModel?>(null),
    this.resources = const AsyncData<List<CourseResourceModel>>([]),
    this.uploadQueue = const [],
  });

  final CourseImportDraftModel draft;
  final AsyncValue<CourseSummaryModel?> createdCourse;
  final AsyncValue<List<CourseResourceModel>> resources;
  final List<UploadQueueItemModel> uploadQueue;

  bool get isCreating => createdCourse.isLoading;
  bool get isRefreshingResources => resources.isLoading;
  bool get isUploading => uploadQueue.any((item) => item.isUploading);
  bool get hasReadyResources => resources.valueOrNull?.isNotEmpty ?? false;

  CourseImportState copyWith({
    CourseImportDraftModel? draft,
    AsyncValue<CourseSummaryModel?>? createdCourse,
    AsyncValue<List<CourseResourceModel>>? resources,
    List<UploadQueueItemModel>? uploadQueue,
  }) {
    return CourseImportState(
      draft: draft ?? this.draft,
      createdCourse: createdCourse ?? this.createdCourse,
      resources: resources ?? this.resources,
      uploadQueue: uploadQueue ?? this.uploadQueue,
    );
  }
}
