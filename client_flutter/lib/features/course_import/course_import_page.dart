import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/widgets/app_error_view.dart';
import '../../core/widgets/app_loading_view.dart';
import '../../core/widgets/app_scaffold.dart';
import '../../shared/models/course_import_state.dart';
import '../../shared/models/recommendation_enums.dart';
import '../../shared/providers/course_import_provider.dart';

class CourseImportPage extends ConsumerStatefulWidget {
  const CourseImportPage({
    this.courseId,
    super.key,
  });

  final String? courseId;

  @override
  ConsumerState<CourseImportPage> createState() => _CourseImportPageState();
}

class _CourseImportPageState extends ConsumerState<CourseImportPage> {
  late final TextEditingController _titleController;
  late final TextEditingController _goalController;
  late final TextEditingController _examAtController;
  String? _lastResourceCourseId;

  @override
  void initState() {
    super.initState();
    final draft = ref.read(courseImportProvider).draft;
    _titleController = TextEditingController(text: draft.title);
    _goalController = TextEditingController(text: draft.goalText);
    _examAtController = TextEditingController(text: draft.examAtText);
    _scheduleResourceFetch(widget.courseId);
  }

  @override
  void didUpdateWidget(covariant CourseImportPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.courseId != widget.courseId) {
      _scheduleResourceFetch(widget.courseId);
    }
  }

  @override
  void dispose() {
    _titleController.dispose();
    _goalController.dispose();
    _examAtController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(courseImportProvider);
    final notifier = ref.read(courseImportProvider.notifier);
    final createdCourseId =
        state.createdCourse.valueOrNull?.courseId.toString();
    final effectiveCourseId = widget.courseId ?? createdCourseId;

    ref.listen(courseImportProvider, (previous, next) {
      final previousCourseId = previous?.createdCourse.valueOrNull?.courseId;
      final course = next.createdCourse.valueOrNull;
      if (course != null && course.courseId != previousCourseId) {
        _scheduleResourceFetch(course.courseId.toString());
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('课程已创建，可以上传资料。')),
        );
      }
    });

    return AppScaffold(
      title: '自主导入',
      body: ListView(
        children: [
          _CourseCreateSection(
            titleController: _titleController,
            goalController: _goalController,
            examAtController: _examAtController,
            preferredStyle: state.draft.preferredStyle,
            examAtErrorText:
                state.draft.hasInvalidExamAt ? '请输入合法的 ISO 时间' : null,
            isCreating: state.isCreating,
            canSubmit: state.draft.canSubmit && !state.isCreating,
            onTitleChanged: (value) => notifier.updateDraft(title: value),
            onGoalChanged: (value) => notifier.updateDraft(goalText: value),
            onExamAtChanged: (value) => notifier.updateDraft(examAtText: value),
            onPreferredStyleChanged: (value) {
              if (value != null) {
                notifier.updateDraft(preferredStyle: value);
              }
            },
            onSubmit: notifier.createCourse,
          ),
          if (state.createdCourse.hasError) ...[
            const SizedBox(height: 12),
            AppErrorView(
              message: '创建课程失败：${state.createdCourse.error}',
              onRetry: notifier.createCourse,
            ),
          ],
          const SizedBox(height: 16),
          _UploadSection(
            courseId: effectiveCourseId,
            state: state,
            onPickFiles: notifier.pickFiles,
            onRemoveFile: notifier.removeQueuedFile,
            onUpload: effectiveCourseId == null
                ? null
                : () => notifier.uploadPendingFiles(effectiveCourseId),
            onDeleteResource: effectiveCourseId == null
                ? null
                : (resourceId) => notifier.deleteResource(
                      courseId: effectiveCourseId,
                      resourceId: resourceId,
                    ),
            onRefresh: effectiveCourseId == null
                ? null
                : () => notifier.fetchResources(effectiveCourseId),
          ),
          const SizedBox(height: 16),
          FilledButton.icon(
            onPressed: effectiveCourseId == null
                ? null
                : () => context.go('/courses/$effectiveCourseId/progress'),
            icon: const Icon(Icons.timeline),
            label: const Text('进入解析进度'),
          ),
        ],
      ),
    );
  }

  void _scheduleResourceFetch(String? courseId) {
    if (courseId == null ||
        courseId.isEmpty ||
        courseId == _lastResourceCourseId) {
      return;
    }
    _lastResourceCourseId = courseId;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) {
        return;
      }
      ref.read(courseImportProvider.notifier).fetchResources(courseId);
    });
  }
}

class _CourseCreateSection extends StatelessWidget {
  const _CourseCreateSection({
    required this.titleController,
    required this.goalController,
    required this.examAtController,
    required this.preferredStyle,
    required this.examAtErrorText,
    required this.isCreating,
    required this.canSubmit,
    required this.onTitleChanged,
    required this.onGoalChanged,
    required this.onExamAtChanged,
    required this.onPreferredStyleChanged,
    required this.onSubmit,
  });

  final TextEditingController titleController;
  final TextEditingController goalController;
  final TextEditingController examAtController;
  final PreferredStyle preferredStyle;
  final String? examAtErrorText;
  final bool isCreating;
  final bool canSubmit;
  final ValueChanged<String> onTitleChanged;
  final ValueChanged<String> onGoalChanged;
  final ValueChanged<String> onExamAtChanged;
  final ValueChanged<PreferredStyle?> onPreferredStyleChanged;
  final VoidCallback onSubmit;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              '创建课程',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: titleController,
              enabled: !isCreating,
              decoration: const InputDecoration(
                labelText: '课程标题',
                border: OutlineInputBorder(),
              ),
              onChanged: onTitleChanged,
            ),
            const SizedBox(height: 12),
            TextField(
              controller: goalController,
              enabled: !isCreating,
              decoration: const InputDecoration(
                labelText: '学习目标',
                border: OutlineInputBorder(),
              ),
              onChanged: onGoalChanged,
            ),
            const SizedBox(height: 12),
            TextField(
              controller: examAtController,
              enabled: !isCreating,
              decoration: InputDecoration(
                labelText: '考试时间（可选 ISO）',
                errorText: examAtErrorText,
                border: const OutlineInputBorder(),
              ),
              onChanged: onExamAtChanged,
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<PreferredStyle>(
              initialValue: preferredStyle,
              decoration: const InputDecoration(
                labelText: '讲义风格偏好',
                border: OutlineInputBorder(),
              ),
              items: const [
                DropdownMenuItem(
                  value: PreferredStyle.balanced,
                  child: Text('平衡讲解'),
                ),
                DropdownMenuItem(
                  value: PreferredStyle.exam,
                  child: Text('考试冲刺'),
                ),
                DropdownMenuItem(
                  value: PreferredStyle.detailed,
                  child: Text('详细解释'),
                ),
                DropdownMenuItem(
                  value: PreferredStyle.quick,
                  child: Text('只看重点'),
                ),
              ],
              onChanged: isCreating ? null : onPreferredStyleChanged,
            ),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: canSubmit ? onSubmit : null,
              icon: const Icon(Icons.add_circle_outline),
              label: Text(isCreating ? '正在创建' : '创建课程'),
            ),
          ],
        ),
      ),
    );
  }
}

class _UploadSection extends StatelessWidget {
  const _UploadSection({
    required this.courseId,
    required this.state,
    required this.onPickFiles,
    required this.onRemoveFile,
    required this.onUpload,
    required this.onDeleteResource,
    required this.onRefresh,
  });

  final String? courseId;
  final CourseImportState state;
  final VoidCallback onPickFiles;
  final ValueChanged<String> onRemoveFile;
  final VoidCallback? onUpload;
  final ValueChanged<int>? onDeleteResource;
  final VoidCallback? onRefresh;

  @override
  Widget build(BuildContext context) {
    final resources = state.resources.valueOrNull ?? const [];
    final hasUploadableFiles = state.uploadQueue.any(
      (item) => item.isPending || item.hasFailed,
    );

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                const Expanded(
                  child: Text(
                    '课程资料',
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
                IconButton(
                  tooltip: '刷新资源',
                  onPressed: onRefresh,
                  icon: const Icon(Icons.refresh),
                ),
              ],
            ),
            Text(
              courseId == null ? '请先创建课程或从推荐页进入。' : '当前课程：$courseId',
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                OutlinedButton.icon(
                  onPressed: courseId == null ? null : onPickFiles,
                  icon: const Icon(Icons.attach_file),
                  label: const Text('选择文件'),
                ),
                FilledButton.icon(
                  onPressed: courseId != null &&
                          hasUploadableFiles &&
                          !state.isUploading
                      ? onUpload
                      : null,
                  icon: const Icon(Icons.cloud_upload_outlined),
                  label: Text(state.isUploading ? '正在上传' : '上传队列'),
                ),
              ],
            ),
            if (state.uploadQueue.isNotEmpty) ...[
              const SizedBox(height: 12),
              ...state.uploadQueue.map(
                (item) => _UploadQueueTile(
                  item: item,
                  onRemove:
                      item.isUploading ? null : () => onRemoveFile(item.id),
                ),
              ),
            ],
            const SizedBox(height: 12),
            if (state.resources.isLoading)
              const AppLoadingView(label: '正在读取资源')
            else if (state.resources.hasError)
              AppErrorView(
                message: '资源列表暂不可用：${state.resources.error}',
                onRetry: onRefresh,
              )
            else if (resources.isEmpty)
              const Text('还没有上传完成的资源。')
            else
              ...resources.map(
                (resource) => ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.description_outlined),
                  title: Text(resource.originalName),
                  subtitle: Text(
                    '${resource.resourceType.name.toUpperCase()} · '
                    '${resource.validationStatus} · '
                    '${resource.processingStatus}',
                  ),
                  trailing: IconButton(
                    tooltip: '删除资源',
                    onPressed: onDeleteResource == null
                        ? null
                        : () => onDeleteResource!(resource.resourceId),
                    icon: const Icon(Icons.delete_outline),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _UploadQueueTile extends StatelessWidget {
  const _UploadQueueTile({
    required this.item,
    required this.onRemove,
  });

  final UploadQueueItemModel item;
  final VoidCallback? onRemove;

  @override
  Widget build(BuildContext context) {
    final statusLabel = switch (item.status) {
      'uploading' => '上传中',
      'ready' => '已完成',
      'failed' => '失败',
      _ => '待上传',
    };

    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: Icon(
        item.hasFailed
            ? Icons.error_outline
            : item.isReady
                ? Icons.check_circle_outline
                : Icons.insert_drive_file_outlined,
      ),
      title: Text(item.name),
      subtitle: Text(
        '${item.resourceType.name.toUpperCase()} · '
        '${item.sizeBytes} bytes · $statusLabel'
        '${item.errorMessage == null ? '' : '\n${item.errorMessage}'}',
      ),
      trailing: IconButton(
        tooltip: '移出队列',
        onPressed: onRemove,
        icon: const Icon(Icons.close),
      ),
    );
  }
}
