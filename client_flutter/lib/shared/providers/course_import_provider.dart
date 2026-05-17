import 'dart:typed_data';

import 'package:crypto/crypto.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/course_create_request.dart';
import '../models/course_import_state.dart';
import '../models/recommendation_enums.dart';
import '../models/resource_upload_models.dart';
import 'course_flow_providers.dart';
import 'course_recommend_provider.dart';

class CourseImportController extends AutoDisposeNotifier<CourseImportState> {
  @override
  CourseImportState build() => const CourseImportState();

  void updateDraft({
    String? title,
    String? goalText,
    String? examAtText,
    PreferredStyle? preferredStyle,
  }) {
    state = state.copyWith(
      draft: state.draft.copyWith(
        title: title,
        goalText: goalText,
        examAtText: examAtText,
        preferredStyle: preferredStyle,
      ),
      createdCourse: const AsyncData(null),
    );
  }

  Future<void> createCourse() async {
    if (!state.draft.canSubmit || state.isCreating) {
      return;
    }

    final draft = state.draft;
    final request = CourseCreateRequestModel(
      title: draft.title.trim(),
      goalText: draft.goalText.trim(),
      examAt: draft.parsedExamAt,
      preferredStyle: draft.preferredStyle,
    );
    state = state.copyWith(createdCourse: const AsyncLoading());

    try {
      final course = await ref.read(apiClientProvider).createCourse(
            request: request,
            idempotencyKey:
                'course-create-${DateTime.now().microsecondsSinceEpoch}',
          );
      ref.read(courseFlowProvider.notifier).syncCreatedCourse(
            courseId: course.courseId,
            lifecycleStatus: course.lifecycleStatus,
            pipelineStage: course.pipelineStage,
            pipelineStatus: course.pipelineStatus,
          );
      state = state.copyWith(createdCourse: AsyncData(course));
      await fetchResources(course.courseId.toString());
    } catch (error, stackTrace) {
      state = state.copyWith(
        createdCourse: AsyncError(error, stackTrace),
      );
    }
  }

  Future<void> fetchResources(String courseId) async {
    state = state.copyWith(resources: const AsyncLoading());

    try {
      final resources = await ref.read(apiClientProvider).fetchCourseResources(
            courseId,
          );
      state = state.copyWith(resources: AsyncData(resources));
    } catch (error, stackTrace) {
      state = state.copyWith(resources: AsyncError(error, stackTrace));
    }
  }

  Future<void> deleteResource({
    required String courseId,
    required int resourceId,
  }) async {
    final previous = state.resources.valueOrNull ?? const [];
    state = state.copyWith(
      resources: AsyncData(
        previous.where((item) => item.resourceId != resourceId).toList(),
      ),
    );

    try {
      await ref.read(apiClientProvider).deleteCourseResource(
            courseId: courseId,
            resourceId: resourceId,
          );
      await fetchResources(courseId);
    } catch (error, stackTrace) {
      state = state.copyWith(resources: AsyncError(error, stackTrace));
    }
  }

  Future<void> pickFiles() async {
    final result = await FilePicker.platform.pickFiles(
      allowMultiple: true,
      withData: true,
      type: FileType.custom,
      allowedExtensions: const ['mp4', 'pdf', 'pptx', 'docx', 'srt'],
    );
    if (result == null) {
      return;
    }

    addFilesForUpload(
      result.files.map(_queueItemFromPlatformFile).toList(),
    );
  }

  void addFilesForUpload(List<UploadQueueItemModel> items) {
    if (items.isEmpty) {
      return;
    }
    state = state.copyWith(
      uploadQueue: [
        ...state.uploadQueue,
        ...items,
      ],
    );
  }

  void removeQueuedFile(String itemId) {
    state = state.copyWith(
      uploadQueue: state.uploadQueue
          .where((item) => item.id != itemId || item.isUploading)
          .toList(),
    );
  }

  Future<void> uploadPendingFiles(String courseId) async {
    if (state.isUploading) {
      return;
    }

    final pendingItems = state.uploadQueue
        .where((item) => item.isPending || item.hasFailed)
        .toList();
    for (final item in pendingItems) {
      await _uploadItem(courseId: courseId, item: item);
    }

    await fetchResources(courseId);
  }

  Future<void> _uploadItem({
    required String courseId,
    required UploadQueueItemModel item,
  }) async {
    _replaceQueueItem(
      item.copyWith(status: 'uploading', clearErrorMessage: true),
    );

    try {
      final apiClient = ref.read(apiClientProvider);
      final uploadInit = await apiClient.initResourceUpload(
        courseId: courseId,
        request: ResourceUploadInitRequestModel(
          resourceType: item.resourceType,
          filename: item.name,
          mimeType: item.mimeType,
          sizeBytes: item.sizeBytes,
          checksum: item.checksum,
        ),
      );

      await apiClient.uploadObject(
        uploadUrl: uploadInit.uploadUrl,
        bytes: item.bytes,
        headers: uploadInit.headers,
        mimeType: item.mimeType,
      );

      final resource = await apiClient.completeResourceUpload(
        courseId: courseId,
        request: ResourceUploadCompleteRequestModel(
          resourceType: item.resourceType,
          objectKey: uploadInit.objectKey,
          originalName: item.name,
          mimeType: item.mimeType,
          sizeBytes: item.sizeBytes,
          checksum: item.checksum,
        ),
        idempotencyKey: 'upload-complete-$courseId-${item.id}',
      );

      _replaceQueueItem(
        item.copyWith(
          status: 'ready',
          resource: resource,
          clearErrorMessage: true,
        ),
      );
    } catch (error) {
      _replaceQueueItem(
        item.copyWith(
          status: 'failed',
          errorMessage: error.toString(),
        ),
      );
    }
  }

  void _replaceQueueItem(UploadQueueItemModel updatedItem) {
    state = state.copyWith(
      uploadQueue: state.uploadQueue
          .map((item) => item.id == updatedItem.id ? updatedItem : item)
          .toList(),
    );
  }

  UploadQueueItemModel _queueItemFromPlatformFile(PlatformFile file) {
    final bytes = file.bytes;
    if (bytes == null) {
      throw StateError('无法读取文件 ${file.name} 的内容');
    }

    final resourceType = _resourceTypeFromFilename(file.name);
    return UploadQueueItemModel(
      id: 'upload-${DateTime.now().microsecondsSinceEpoch}-${file.name}',
      name: file.name,
      resourceType: resourceType,
      mimeType: _mimeTypeFor(resourceType),
      sizeBytes: file.size,
      checksum: 'sha256:${sha256.convert(bytes).toString()}',
      bytes: Uint8List.fromList(bytes),
    );
  }
}

final courseImportProvider =
    AutoDisposeNotifierProvider<CourseImportController, CourseImportState>(
  CourseImportController.new,
);

ResourceType _resourceTypeFromFilename(String filename) {
  final extension = filename.split('.').last.toLowerCase();
  for (final type in ResourceType.values) {
    if (type.name == extension) {
      return type;
    }
  }
  throw ArgumentError.value(filename, 'filename', '不支持的资料类型');
}

String _mimeTypeFor(ResourceType type) {
  switch (type) {
    case ResourceType.mp4:
      return 'video/mp4';
    case ResourceType.pdf:
      return 'application/pdf';
    case ResourceType.pptx:
      return 'application/vnd.openxmlformats-officedocument.presentationml.presentation';
    case ResourceType.docx:
      return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
    case ResourceType.srt:
      return 'application/x-subrip';
  }
}
