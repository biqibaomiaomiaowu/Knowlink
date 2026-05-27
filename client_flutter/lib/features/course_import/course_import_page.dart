import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../../app/theme/app_theme.dart';
import '../../core/widgets/app_error_view.dart';
import '../../core/widgets/app_loading_view.dart';
import '../../core/widgets/app_scaffold.dart';
import '../../core/widgets/knowlink_widgets.dart';
import '../../shared/models/bilibili_import_models.dart';
import '../../shared/models/bilibili_import_state.dart';
import '../../shared/models/course_import_state.dart';
import '../../shared/models/recommendation_enums.dart';
import '../../shared/models/resource_upload_models.dart';
import '../../shared/providers/bilibili_import_provider.dart';
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
  late final TextEditingController _bilibiliUrlController;
  String? _lastResourceCourseId;

  @override
  void initState() {
    super.initState();
    final draft = ref.read(courseImportProvider).draft;
    _titleController = TextEditingController(text: draft.title);
    _goalController = TextEditingController(text: draft.goalText);
    _examAtController = TextEditingController(text: draft.examAtText);
    _bilibiliUrlController = TextEditingController();
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
    _bilibiliUrlController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(courseImportProvider);
    final notifier = ref.read(courseImportProvider.notifier);
    final bilibiliState = ref.watch(bilibiliImportProvider);
    final bilibiliNotifier = ref.read(bilibiliImportProvider.notifier);
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
      activeTab: KnowLinkTab.import,
      courseId: effectiveCourseId,
      body: LayoutBuilder(
        builder: (context, constraints) {
          final isWide = constraints.maxWidth >= 980;
          final createSection = _CourseCreateSection(
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
          );
          final uploadSection = _UploadSection(
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
          );
          final bilibiliSection = _BilibiliImportSection(
            courseId: effectiveCourseId,
            urlController: _bilibiliUrlController,
            state: bilibiliState,
            onUrlChanged: bilibiliNotifier.updateSourceUrl,
            onPreview: effectiveCourseId == null
                ? null
                : () => _runBilibiliAction(
                      () => bilibiliNotifier.preview(effectiveCourseId),
                    ),
            onTogglePart: (partId, selected) => bilibiliNotifier.togglePart(
              partId,
              selected: selected,
            ),
            onCreateImport: effectiveCourseId == null
                ? null
                : () => _runBilibiliAction(() async {
                      await bilibiliNotifier.createImport(effectiveCourseId);
                      if (!_isActiveCourse(effectiveCourseId)) {
                        return;
                      }
                      final run = ref
                          .read(bilibiliImportProvider)
                          .currentRun
                          .valueOrNull;
                      if (run != null && !run.isTerminal) {
                        await bilibiliNotifier.pollCurrentRunUntilTerminal(
                          run.importRunId,
                        );
                      }
                      if (!_isActiveCourse(effectiveCourseId)) {
                        return;
                      }
                      await _refreshResourcesIfBilibiliImported(
                        effectiveCourseId,
                      );
                    }),
            onRetry: effectiveCourseId == null
                ? null
                : () => _runBilibiliAction(() async {
                      await bilibiliNotifier.retryCurrentRun();
                      if (!_isActiveCourse(effectiveCourseId)) {
                        return;
                      }
                      final run = ref
                          .read(bilibiliImportProvider)
                          .currentRun
                          .valueOrNull;
                      if (run != null && !run.isTerminal) {
                        await bilibiliNotifier.pollCurrentRunUntilTerminal(
                          run.importRunId,
                        );
                      }
                      if (!_isActiveCourse(effectiveCourseId)) {
                        return;
                      }
                      await _refreshResourcesIfBilibiliImported(
                        effectiveCourseId,
                      );
                    }),
            onCancel: () => _runBilibiliAction(
              bilibiliNotifier.cancelCurrentRun,
            ),
            onRefreshStatus: () {
              final currentRun = bilibiliState.currentRun.valueOrNull;
              if (currentRun != null) {
                _runBilibiliAction(
                  () async {
                    await bilibiliNotifier.refreshCurrentRun(
                      currentRun.importRunId,
                    );
                    await _refreshResourcesIfBilibiliImported(
                      effectiveCourseId,
                    );
                  },
                );
                return;
              }
              if (effectiveCourseId != null) {
                _runBilibiliAction(
                  () async {
                    await bilibiliNotifier.loadInitialState(effectiveCourseId);
                    await _refreshResourcesIfBilibiliImported(
                      effectiveCourseId,
                    );
                  },
                );
              }
            },
            onRefreshAuth: () => _runBilibiliAction(
              bilibiliNotifier.refreshAuthSession,
            ),
            onCreateQrSession: () => _runBilibiliAction(
              bilibiliNotifier.createQrSession,
            ),
            onPollQrSession: () => _runBilibiliAction(
              bilibiliNotifier.pollQrSession,
            ),
          );

          return ListView(
            children: [
              _ImportHero(courseId: effectiveCourseId),
              if (state.createdCourse.hasError) ...[
                const SizedBox(height: 12),
                AppErrorView(
                  message: '创建课程失败：${state.createdCourse.error}',
                  onRetry: notifier.createCourse,
                ),
              ],
              const SizedBox(height: 18),
              if (isWide)
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(child: createSection),
                    const SizedBox(width: 18),
                    Expanded(child: uploadSection),
                  ],
                )
              else ...[
                createSection,
                const SizedBox(height: 16),
                uploadSection,
              ],
              const SizedBox(height: 18),
              bilibiliSection,
              const SizedBox(height: 18),
              const _ImportGuideCard(),
              const SizedBox(height: 22),
              SizedBox(
                height: 58,
                child: FilledButton.icon(
                  onPressed: effectiveCourseId == null
                      ? null
                      : () =>
                          context.go('/courses/$effectiveCourseId/progress'),
                  icon: const Icon(Icons.analytics_outlined),
                  label: Text(
                    effectiveCourseId == null ? '先创建课程后开始解析' : '进入解析进度',
                  ),
                ),
              ),
            ],
          );
        },
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
    ref
        .read(bilibiliImportProvider.notifier)
        .activateCourse(courseId, clearState: false);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) {
        return;
      }
      ref.read(courseImportProvider.notifier).fetchResources(courseId);
      ref.read(bilibiliImportProvider.notifier).loadInitialState(courseId);
    });
  }

  Future<void> _runBilibiliAction(Future<void> Function() action) async {
    try {
      await action();
    } catch (error) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('B站导入操作失败：$error')),
      );
    }
  }

  Future<void> _refreshResourcesIfBilibiliImported(String? courseId) async {
    if (courseId == null || !_isActiveCourse(courseId)) {
      return;
    }
    final currentRun = ref.read(bilibiliImportProvider).currentRun.valueOrNull;
    if (currentRun?.isImported == true) {
      await ref.read(courseImportProvider.notifier).fetchResources(courseId);
    }
  }

  bool _isActiveCourse(String? courseId) {
    if (!mounted || courseId == null) {
      return false;
    }
    final activeCourseId = widget.courseId ??
        ref
            .read(courseImportProvider)
            .createdCourse
            .valueOrNull
            ?.courseId
            .toString();
    return activeCourseId == courseId;
  }
}

class _ImportHero extends StatelessWidget {
  const _ImportHero({
    required this.courseId,
  });

  final String? courseId;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Row(
          children: [
            _StepBadge(number: '2'),
            SizedBox(width: 14),
            Expanded(
              child: Text(
                '自主导入',
                style: TextStyle(
                  color: AppTheme.ink,
                  fontSize: 34,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 0,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        const Text(
          '上传课程视频与学习资料，开始智能解析，构建你的专属知识库。',
          style: TextStyle(
            color: AppTheme.muted,
            fontSize: 16,
            fontWeight: FontWeight.w600,
          ),
        ),
        if (courseId != null) ...[
          const SizedBox(height: 10),
          StatusPill(label: '课程 ID：$courseId'),
        ],
      ],
    );
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
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text('课程信息',
                style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800)),
            const SizedBox(height: 22),
            TextField(
              controller: titleController,
              enabled: !isCreating,
              decoration: const InputDecoration(
                labelText: '课程名称',
                hintText: '如：数据结构（C语言版）',
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
            const SizedBox(height: 18),
            FilledButton.icon(
              onPressed: canSubmit ? onSubmit : null,
              icon: const Icon(Icons.add_circle_outline),
              label: Text(isCreating ? '正在创建课程' : '创建课程'),
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
    final visibleItems = [
      ...state.uploadQueue.map(_UploadDisplayItem.fromQueue),
      ...resources.map(_UploadDisplayItem.fromResource),
    ];

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                const Expanded(
                  child: Text(
                    '上传教材 / PPT / 讲义 / 笔记',
                    style: TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.w800,
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
            const Text(
              '支持 PDF、PPTX、DOCX、视频等格式',
              style: TextStyle(
                color: AppTheme.muted,
                fontSize: 14,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 18),
            _UploadDropZone(
              enabled: courseId != null,
              isUploading: state.isUploading,
              onPickFiles: onPickFiles,
            ),
            const SizedBox(height: 16),
            Text(
              courseId == null ? '请先创建课程或从推荐页进入。' : '当前课程：$courseId',
              style: const TextStyle(
                color: AppTheme.muted,
                fontWeight: FontWeight.w600,
              ),
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
              const _EmptyUploadList()
            else
              _UploadedResourceList(
                items: visibleItems,
                onDeleteResource: onDeleteResource,
              ),
          ],
        ),
      ),
    );
  }
}

class _UploadDropZone extends StatelessWidget {
  const _UploadDropZone({
    required this.enabled,
    required this.isUploading,
    required this.onPickFiles,
  });

  final bool enabled;
  final bool isUploading;
  final VoidCallback onPickFiles;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(8),
      onTap: enabled && !isUploading ? onPickFiles : null,
      child: Container(
        constraints: const BoxConstraints(minHeight: 142),
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(
          color: const Color(0xFFF8FBFF),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: enabled ? AppTheme.brandBlue : AppTheme.line,
            style: BorderStyle.solid,
          ),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.cloud_upload_outlined,
              color: AppTheme.brandBlue,
              size: 38,
            ),
            const SizedBox(height: 10),
            Text(
              enabled ? '点击选择上传文件' : '创建课程后可上传文件',
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: AppTheme.brandBlue,
                fontSize: 16,
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 6),
            const Text(
              '单个文件最大 200MB，视频文件按后端限制处理',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: AppTheme.muted,
                fontSize: 13,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _BilibiliImportSection extends StatelessWidget {
  const _BilibiliImportSection({
    required this.courseId,
    required this.urlController,
    required this.state,
    required this.onUrlChanged,
    required this.onPreview,
    required this.onTogglePart,
    required this.onCreateImport,
    required this.onRetry,
    required this.onCancel,
    required this.onRefreshStatus,
    required this.onRefreshAuth,
    required this.onCreateQrSession,
    required this.onPollQrSession,
  });

  final String? courseId;
  final TextEditingController urlController;
  final BilibiliImportState state;
  final ValueChanged<String> onUrlChanged;
  final VoidCallback? onPreview;
  final void Function(String partId, bool selected) onTogglePart;
  final VoidCallback? onCreateImport;
  final VoidCallback? onRetry;
  final VoidCallback onCancel;
  final VoidCallback onRefreshStatus;
  final VoidCallback onRefreshAuth;
  final VoidCallback onCreateQrSession;
  final VoidCallback onPollQrSession;

  @override
  Widget build(BuildContext context) {
    final currentRun = state.currentRun.valueOrNull;
    final canPreview = courseId != null && state.canPreview;
    final isImportRunning = currentRun?.canCancel == true;
    final canCreate =
        courseId != null && state.canCreateImport && !isImportRunning;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                const Expanded(
                  child: Text(
                    'B站导入',
                    style: TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
                IconButton(
                  tooltip: '刷新状态',
                  onPressed: courseId == null ? null : onRefreshStatus,
                  icon: const Icon(Icons.refresh),
                ),
              ],
            ),
            const SizedBox(height: 12),
            _BilibiliAuthStatus(
              authSession: state.authSession,
              qrSession: state.qrSession,
              onRefreshAuth: onRefreshAuth,
              onCreateQrSession: onCreateQrSession,
              onPollQrSession: onPollQrSession,
            ),
            const SizedBox(height: 14),
            TextField(
              controller: urlController,
              enabled: courseId != null,
              decoration: const InputDecoration(
                labelText: 'B站链接',
                border: OutlineInputBorder(),
              ),
              onChanged: onUrlChanged,
            ),
            const SizedBox(height: 10),
            Text(
              courseId == null
                  ? '请先创建课程或从推荐页进入已有课程。'
                  : '粘贴 B站单视频、多 P、合集或番剧链接后预览可导入条目。',
              style: const TextStyle(
                color: AppTheme.muted,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 14),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                FilledButton.icon(
                  onPressed:
                      canPreview && !state.preview.isLoading ? onPreview : null,
                  icon: const Icon(Icons.visibility_outlined),
                  label: Text(
                    state.preview.isLoading ? '正在预览' : '预览B站资源',
                  ),
                ),
                FilledButton.icon(
                  onPressed: canCreate ? onCreateImport : null,
                  icon: const Icon(Icons.playlist_add_check),
                  label: Text(
                    isImportRunning
                        ? '导入进行中'
                        : state.currentTask.isLoading
                            ? '正在创建'
                            : '创建导入任务',
                  ),
                ),
                OutlinedButton.icon(
                  onPressed: courseId == null ? null : onRefreshStatus,
                  icon: const Icon(Icons.refresh),
                  label: const Text('刷新状态'),
                ),
                if (currentRun?.canCancel == true)
                  OutlinedButton.icon(
                    onPressed: state.isCanceling ? null : onCancel,
                    icon: const Icon(Icons.cancel_outlined),
                    label: const Text('取消导入'),
                  ),
              ],
            ),
            if (state.preview.isLoading) ...[
              const SizedBox(height: 16),
              const AppLoadingView(label: '正在预览B站资源'),
            ] else if (state.preview.hasError) ...[
              const SizedBox(height: 16),
              AppErrorView(
                message: 'B站资源预览失败：${state.preview.error}',
                onRetry: onPreview,
              ),
            ] else if (state.preview.valueOrNull != null) ...[
              const SizedBox(height: 16),
              _BilibiliPreviewCard(
                preview: state.preview.valueOrNull!,
                selectedPartIds: state.selectedPartIds,
                onTogglePart: onTogglePart,
              ),
            ],
            const SizedBox(height: 16),
            _BilibiliRunStatusCard(
              currentTask: state.currentTask,
              currentRun: state.currentRun,
              onRefreshStatus: onRefreshStatus,
              onRetry: onRetry,
            ),
          ],
        ),
      ),
    );
  }
}

class _BilibiliAuthStatus extends StatelessWidget {
  const _BilibiliAuthStatus({
    required this.authSession,
    required this.qrSession,
    required this.onRefreshAuth,
    required this.onCreateQrSession,
    required this.onPollQrSession,
  });

  final AsyncValue<BilibiliAuthSessionModel?> authSession;
  final AsyncValue<BilibiliQrSessionModel?> qrSession;
  final VoidCallback onRefreshAuth;
  final VoidCallback onCreateQrSession;
  final VoidCallback onPollQrSession;

  @override
  Widget build(BuildContext context) {
    if (authSession.isLoading) {
      return const AppLoadingView(label: '正在读取B站登录状态');
    }
    final authError = authSession.hasError ? authSession.error : null;
    final session = authSession.valueOrNull;
    final isActive = session?.isActive == true;
    final label = authError != null
        ? 'B站登录状态暂不可用'
        : isActive
            ? '已登录：${session?.userNickname ?? 'B站账号'}'
            : '未登录B站';

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (authError != null) ...[
          AppErrorView(
            message: 'B站登录状态暂不可用：$authError',
            onRetry: onRefreshAuth,
          ),
          const SizedBox(height: 10),
        ],
        Wrap(
          spacing: 8,
          runSpacing: 8,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            StatusPill(
              label: label,
              color: isActive ? const Color(0xFF16A34A) : AppTheme.muted,
              icon: authError != null
                  ? Icons.error_outline
                  : isActive
                      ? Icons.check_circle_outline
                      : Icons.account_circle_outlined,
            ),
            OutlinedButton.icon(
              onPressed: onCreateQrSession,
              icon: const Icon(Icons.qr_code_2),
              label: const Text('重新扫码'),
            ),
          ],
        ),
        if (qrSession.isLoading) ...[
          const SizedBox(height: 10),
          const AppLoadingView(label: '正在生成扫码会话'),
        ] else if (qrSession.hasError) ...[
          const SizedBox(height: 10),
          AppErrorView(
            message: '扫码会话创建失败：${qrSession.error}',
            onRetry: onCreateQrSession,
          ),
        ] else if (qrSession.valueOrNull != null) ...[
          const SizedBox(height: 10),
          _BilibiliQrSessionView(
            qrSession: qrSession.valueOrNull!,
            onPollQrSession: onPollQrSession,
          ),
        ],
      ],
    );
  }
}

class _BilibiliQrSessionView extends StatelessWidget {
  const _BilibiliQrSessionView({
    required this.qrSession,
    required this.onPollQrSession,
  });

  final BilibiliQrSessionModel qrSession;
  final VoidCallback onPollQrSession;

  @override
  Widget build(BuildContext context) {
    final qrCodeUrl = qrSession.qrCodeUrl;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '扫码状态：${qrSession.status}',
          style: const TextStyle(
            color: AppTheme.muted,
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(height: 10),
        if (qrCodeUrl == null)
          const Text(
            '二维码链接暂不可用',
            style: TextStyle(
              color: AppTheme.muted,
              fontWeight: FontWeight.w600,
            ),
          )
        else ...[
          DecoratedBox(
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: AppTheme.line),
            ),
            child: Padding(
              padding: const EdgeInsets.all(8),
              child: QrImageView(
                data: qrCodeUrl,
                version: QrVersions.auto,
                size: 132,
                backgroundColor: Colors.white,
              ),
            ),
          ),
        ],
        const SizedBox(height: 10),
        OutlinedButton.icon(
          onPressed: qrSession.isTerminal ? null : onPollQrSession,
          icon: const Icon(Icons.sync),
          label: const Text('刷新扫码状态'),
        ),
      ],
    );
  }
}

class _BilibiliPreviewCard extends StatelessWidget {
  const _BilibiliPreviewCard({
    required this.preview,
    required this.selectedPartIds,
    required this.onTogglePart,
  });

  final BilibiliPreviewModel preview;
  final Set<String> selectedPartIds;
  final void Function(String partId, bool selected) onTogglePart;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              preview.title,
              style: const TextStyle(
                color: AppTheme.ink,
                fontSize: 17,
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              '${preview.sourceTypeLabel} · ${preview.totalParts} 个条目 · '
              '默认${preview.defaultSelectionModeLabel}',
              style: const TextStyle(
                color: AppTheme.muted,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 10),
            ...preview.parts.map(
              (part) => CheckboxListTile(
                value: selectedPartIds.contains(part.partId),
                contentPadding: EdgeInsets.zero,
                title: Text(part.title),
                subtitle: Text('P${part.pageNo} · ${part.displayDuration}'),
                controlAffinity: ListTileControlAffinity.leading,
                onChanged: (selected) => onTogglePart(
                  part.partId,
                  selected ?? false,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _BilibiliRunStatusCard extends StatelessWidget {
  const _BilibiliRunStatusCard({
    required this.currentTask,
    required this.currentRun,
    required this.onRefreshStatus,
    required this.onRetry,
  });

  final AsyncValue<BilibiliImportTaskModel?> currentTask;
  final AsyncValue<BilibiliImportRunModel?> currentRun;
  final VoidCallback onRefreshStatus;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    if (currentRun.isLoading || currentTask.isLoading) {
      return const AppLoadingView(label: '正在读取导入状态');
    }
    if (currentRun.hasError) {
      return AppErrorView(
        message: '导入状态暂不可用：${currentRun.error}',
        onRetry: onRefreshStatus,
      );
    }
    if (currentTask.hasError) {
      return AppErrorView(
        message: '导入任务创建失败：${currentTask.error}',
        onRetry: onRefreshStatus,
      );
    }

    final run = currentRun.valueOrNull;
    final task = currentTask.valueOrNull;
    if (run == null && task == null) {
      return const SizedBox.shrink();
    }

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              '导入状态',
              style: TextStyle(
                color: AppTheme.ink,
                fontSize: 17,
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                if (task != null) StatusPill(label: _taskStatusLabel(task)),
                if (run != null) StatusPill(label: run.statusLabel),
              ],
            ),
            if (run?.previewTitle != null) ...[
              const SizedBox(height: 8),
              Text(
                run!.previewTitle!,
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
            ],
            if (run != null) ...[
              const SizedBox(height: 8),
              Text(
                '${run.stageLabel} · ${run.progressPct}%',
                style: const TextStyle(
                  color: AppTheme.muted,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 8),
              ProgressRail(value: run.progressPct / 100),
            ],
            if (run?.resourceIdsLabel != null) ...[
              const SizedBox(height: 8),
              Text(
                run!.resourceIdsLabel!,
                style: const TextStyle(
                  color: AppTheme.muted,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
            if (run?.failureReason != null) ...[
              const SizedBox(height: 8),
              Text(
                run!.failureReason!,
                style: const TextStyle(
                  color: Color(0xFFB91C1C),
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
            if (run?.canRetry == true) ...[
              const SizedBox(height: 12),
              Align(
                alignment: Alignment.centerLeft,
                child: OutlinedButton.icon(
                  onPressed: onRetry,
                  icon: const Icon(Icons.refresh),
                  label: const Text('重试导入'),
                ),
              ),
            ],
            if (run?.isImported == true) ...[
              const SizedBox(height: 12),
              Align(
                alignment: Alignment.centerLeft,
                child: FilledButton.icon(
                  onPressed: () =>
                      context.go('/courses/${run!.courseId}/progress'),
                  icon: const Icon(Icons.manage_search),
                  label: const Text('进入解析'),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  String _taskStatusLabel(BilibiliImportTaskModel task) {
    return switch (task.status) {
      'queued' => '已入队',
      'running' => '处理中',
      'succeeded' => '已完成',
      'failed' => '失败',
      'canceled' => '已取消',
      _ => task.status,
    };
  }
}

class _UploadedResourceList extends StatelessWidget {
  const _UploadedResourceList({
    required this.items,
    required this.onDeleteResource,
  });

  final List<_UploadDisplayItem> items;
  final ValueChanged<int>? onDeleteResource;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: items
          .map(
            (item) => Container(
              margin: const EdgeInsets.only(bottom: 8),
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              decoration: BoxDecoration(
                border: Border.all(color: AppTheme.line),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  _FileTypeIcon(type: item.type),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          item.name,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            color: AppTheme.ink,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        const SizedBox(height: 3),
                        Text(
                          item.detail,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            color: AppTheme.muted,
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 10),
                  const Icon(
                    Icons.check_circle_outline,
                    color: Color(0xFF22C55E),
                    size: 22,
                  ),
                  IconButton(
                    tooltip: '删除资源',
                    onPressed:
                        item.resourceId == null || onDeleteResource == null
                            ? null
                            : () => onDeleteResource!(item.resourceId!),
                    icon: const Icon(Icons.delete_outline),
                  ),
                ],
              ),
            ),
          )
          .toList(),
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

class _ImportGuideCard extends StatelessWidget {
  const _ImportGuideCard();

  @override
  Widget build(BuildContext context) {
    return const Card(
      child: Padding(
        padding: EdgeInsets.all(22),
        child: Wrap(
          spacing: 34,
          runSpacing: 20,
          alignment: WrapAlignment.spaceBetween,
          children: [
            _GuideItem(
              icon: Icons.description_outlined,
              title: '支持的文件类型',
              lines: ['PDF、PPTX、DOCX、MP4、MOV、AVI 等', '文档最大 200MB，视频按后端限制处理'],
            ),
            _GuideItem(
              icon: Icons.lightbulb_outline,
              title: '建议',
              lines: ['建议按章节或知识点拆分资料，提升解析效果', 'PPT 建议包含完整的文字内容'],
              color: Color(0xFFF97316),
            ),
            _GuideItem(
              icon: Icons.info_outline,
              title: '说明',
              lines: ['上传后系统将自动解析内容并生成知识结构', '解析完成后可在「课程」页查看'],
            ),
          ],
        ),
      ),
    );
  }
}

class _GuideItem extends StatelessWidget {
  const _GuideItem({
    required this.icon,
    required this.title,
    required this.lines,
    this.color = AppTheme.brandBlue,
  });

  final IconData icon;
  final String title;
  final List<String> lines;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 360,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SoftIcon(icon: icon, color: color, size: 44),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    color: AppTheme.ink,
                    fontSize: 15,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 8),
                for (final line in lines)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 3),
                    child: Text(
                      line,
                      style: const TextStyle(
                        color: AppTheme.muted,
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _EmptyUploadList extends StatelessWidget {
  const _EmptyUploadList();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FBFF),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppTheme.line),
      ),
      child: const Text(
        '还没有上传完成的资源。',
        style: TextStyle(color: AppTheme.muted, fontWeight: FontWeight.w600),
      ),
    );
  }
}

class _StepBadge extends StatelessWidget {
  const _StepBadge({required this.number});

  final String number;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 42,
      height: 42,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF60A5FA), AppTheme.brandBlueDark],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(8),
        boxShadow: const [
          BoxShadow(
            color: Color(0x262563EB),
            blurRadius: 12,
            offset: Offset(0, 6),
          ),
        ],
      ),
      child: Text(
        number,
        style: const TextStyle(
          color: Colors.white,
          fontSize: 24,
          fontWeight: FontWeight.w800,
        ),
      ),
    );
  }
}

class _FileTypeIcon extends StatelessWidget {
  const _FileTypeIcon({required this.type});

  final String type;

  @override
  Widget build(BuildContext context) {
    final lower = type.toLowerCase();
    final color = switch (lower) {
      'pdf' => const Color(0xFFEF4444),
      'pptx' => const Color(0xFFF97316),
      'docx' => const Color(0xFF3B82F6),
      'mp4' || 'mov' || 'avi' => const Color(0xFF8B5CF6),
      _ => AppTheme.brandBlue,
    };
    return Container(
      width: 34,
      height: 34,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        lower.toUpperCase().substring(0, lower.length > 3 ? 3 : lower.length),
        style: const TextStyle(
          color: Colors.white,
          fontSize: 9,
          fontWeight: FontWeight.w800,
        ),
      ),
    );
  }
}

class _UploadDisplayItem {
  const _UploadDisplayItem({
    required this.name,
    required this.type,
    required this.detail,
    this.resourceId,
  });

  final String name;
  final String type;
  final String detail;
  final int? resourceId;

  factory _UploadDisplayItem.fromQueue(UploadQueueItemModel item) {
    final statusLabel = switch (item.status) {
      'uploading' => '上传中',
      'ready' => '已完成',
      'failed' => '失败',
      _ => '待上传',
    };
    return _UploadDisplayItem(
      name: item.name,
      type: item.resourceType.name,
      detail: '${item.sizeBytes} bytes · $statusLabel',
    );
  }

  factory _UploadDisplayItem.fromResource(CourseResourceModel resource) {
    return _UploadDisplayItem(
      name: resource.originalName,
      type: resource.resourceType.name,
      detail: '${resource.validationStatus} · ${resource.processingStatus}',
      resourceId: resource.resourceId,
    );
  }
}
