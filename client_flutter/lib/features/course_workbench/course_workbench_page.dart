import 'dart:async';
import 'dart:math' as math;
import 'dart:typed_data';
import 'dart:ui';

import 'package:crypto/crypto.dart';
import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/theme/app_theme.dart';
import '../../core/network/api_client.dart';
import '../../core/widgets/app_error_view.dart';
import '../../core/widgets/app_loading_view.dart';
import '../../core/widgets/app_scaffold.dart';
import '../../core/widgets/knowlink_widgets.dart';
import '../../shared/models/course_lesson_models.dart';
import '../../shared/models/handout_models.dart';
import '../../shared/models/pipeline_status.dart';
import '../../shared/models/recommendation_enums.dart';
import '../../shared/models/resource_upload_models.dart';
import '../../shared/providers/course_recommend_provider.dart';
import '../../shared/services/course_lesson_api.dart';
import '../../shared/providers/course_workbench_provider.dart';

class CourseWorkbenchPage extends ConsumerWidget {
  const CourseWorkbenchPage({
    required this.courseId,
    super.key,
  });

  final String courseId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final workbench = ref.watch(courseWorkbenchProvider(courseId));
    return AppScaffold(
      title: '课程工作台',
      activeTab: KnowLinkTab.home,
      courseId: courseId,
      body: workbench.when(
        loading: () => const AppLoadingView(label: '正在加载课程工作台'),
        error: (error, _) => AppErrorView(
          message: '课程工作台加载失败：$error',
          onRetry: () => ref.invalidate(courseWorkbenchProvider(courseId)),
        ),
        data: (model) => _WorkbenchBody(model: model),
      ),
    );
  }
}

class _WorkbenchBody extends ConsumerWidget {
  const _WorkbenchBody({required this.model});

  final CourseWorkbenchModel model;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final course = model.course;
    return ListView(
      children: [
        Align(
          alignment: Alignment.centerLeft,
          child: OutlinedButton.icon(
            onPressed: () => _safeGo(context, '/courses'),
            icon: const Icon(Icons.arrow_back_rounded),
            label: const Text('返回课程库'),
          ),
        ),
        const SizedBox(height: 16),
        _WorkbenchTitleBar(
          model: model,
          onCreateLesson: () => _createLesson(context, ref, course.courseId),
        ),
        const SizedBox(height: 16),
        _WorkspaceCards(model: model),
        const SizedBox(height: 16),
        _LessonGrid(courseId: course.courseId, lessons: model.lessons),
      ],
    );
  }

  Future<void> _createLesson(
    BuildContext context,
    WidgetRef ref,
    String courseId,
  ) async {
    await _showLessonCreateDialog(
      context,
      courseId,
      onCreated: (result) {
        if (!context.mounted) {
          return;
        }
        ref.invalidate(courseWorkbenchProvider(courseId));
        _safeGo(
          context,
          '/courses/$courseId/lessons/${result.lesson.lessonId}/preparing',
          extra: result,
        );
      },
    );
  }
}

class _WorkbenchTitleBar extends StatelessWidget {
  const _WorkbenchTitleBar({
    required this.model,
    required this.onCreateLesson,
  });

  final CourseWorkbenchModel model;
  final VoidCallback onCreateLesson;

  @override
  Widget build(BuildContext context) {
    final course = model.course;
    final title = Row(
      children: [
        const SoftIcon(icon: Icons.article_outlined, size: 46),
        const SizedBox(width: 14),
        Expanded(
          child: Text(
            course.title,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.displaySmall,
          ),
        ),
      ],
    );
    final actions = Wrap(
      key: const Key('course_workbench_primary_entries'),
      spacing: 10,
      runSpacing: 10,
      children: [
        OutlinedButton.icon(
          onPressed: () => _safeGo(
            context,
            _entryRoute(model, 'course_qa', '/courses/${course.courseId}/qa'),
          ),
          icon: const Icon(Icons.forum_outlined),
          label: const Text('问 AI'),
        ),
        FilledButton.icon(
          onPressed: onCreateLesson,
          icon: const Icon(Icons.add_rounded),
          label: const Text('新建课时'),
        ),
      ],
    );

    return LayoutBuilder(
      builder: (context, constraints) {
        if (constraints.maxWidth < 760) {
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              title,
              const SizedBox(height: 14),
              actions,
            ],
          );
        }
        return Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Expanded(child: title),
            const SizedBox(width: 16),
            actions,
          ],
        );
      },
    );
  }
}

Future<void> _showLessonCreateDialog(
  BuildContext context,
  String courseId, {
  required ValueChanged<LessonPreparationPayload> onCreated,
}) {
  return showGeneralDialog<void>(
    context: context,
    barrierDismissible: true,
    barrierLabel: '关闭',
    barrierColor: Colors.transparent,
    transitionDuration: Duration.zero,
    pageBuilder: (context, animation, secondaryAnimation) {
      return _LessonCreateDialog(courseId: courseId, onCreated: onCreated);
    },
    transitionBuilder: (context, animation, secondaryAnimation, child) {
      final curved = CurvedAnimation(
        parent: animation,
        curve: Curves.easeOutCubic,
        reverseCurve: Curves.easeInCubic,
      );
      return FadeTransition(
        opacity: curved,
        child: ScaleTransition(
          scale: Tween<double>(begin: 0.98, end: 1).animate(curved),
          child: child,
        ),
      );
    },
  );
}

class LessonPreparationPayload {
  const LessonPreparationPayload({
    required this.lesson,
    required this.files,
  });

  final LessonSummaryModel lesson;
  final List<LessonPreparationUploadDraft> files;
}

class _LessonCreateDialog extends ConsumerStatefulWidget {
  const _LessonCreateDialog({
    required this.courseId,
    required this.onCreated,
  });

  final String courseId;
  final ValueChanged<LessonPreparationPayload> onCreated;

  @override
  ConsumerState<_LessonCreateDialog> createState() =>
      _LessonCreateDialogState();
}

class _LessonCreateDialogState extends ConsumerState<_LessonCreateDialog> {
  final _titleController = TextEditingController();
  final _bilibiliController = TextEditingController();
  final _timeBudgetController = TextEditingController();
  final _titleFocusNode = FocusNode();
  final _selectedFiles = <LessonPreparationUploadDraft>[];
  var _goal = '期末复习';
  var _mastery = '零基础';
  var _isPickingFiles = false;
  var _isSubmitting = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        _titleFocusNode.requestFocus();
      }
    });
  }

  @override
  void dispose() {
    _titleController.dispose();
    _bilibiliController.dispose();
    _timeBudgetController.dispose();
    _titleFocusNode.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: Stack(
        children: [
          Positioned.fill(
            child: GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTap: _isSubmitting ? null : _close,
              child: BackdropFilter(
                filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
                child: const ColoredBox(color: Color(0x573D4852)),
              ),
            ),
          ),
          SafeArea(
            child: LayoutBuilder(
              builder: (context, constraints) {
                final maxHeight = constraints.maxHeight <= 48
                    ? constraints.maxHeight
                    : constraints.maxHeight - 48;
                return Center(
                  child: ConstrainedBox(
                    constraints: BoxConstraints(
                      maxWidth: 680,
                      maxHeight: maxHeight,
                    ),
                    child: DecoratedBox(
                      decoration: BoxDecoration(
                        color: AppTheme.surface,
                        borderRadius: BorderRadius.circular(32),
                        boxShadow: AppTheme.shadowRaised,
                      ),
                      child: SingleChildScrollView(
                        padding: const EdgeInsets.all(28),
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            _LessonCreateHeader(
                              onClose: _isSubmitting ? null : _close,
                            ),
                            const SizedBox(height: 24),
                            _LessonModalInput(
                              label: '课时名称',
                              controller: _titleController,
                              focusNode: _titleFocusNode,
                              enabled: !_isSubmitting,
                              hintText: '例如：栈与队列专项复习',
                              onSubmitted: (_) => _submit(),
                            ),
                            const SizedBox(height: 18),
                            _LessonMaterialsPicker(
                              enabled: !_isSubmitting,
                              isPicking: _isPickingFiles,
                              selectedFiles: _selectedFiles,
                              onPick: _pickFiles,
                              onRemove: _removeFile,
                            ),
                            const SizedBox(height: 18),
                            _LessonModalInput(
                              label: '导入 B 站链接',
                              controller: _bilibiliController,
                              enabled: !_isSubmitting,
                              keyboardType: TextInputType.url,
                              hintText: 'https://www.bilibili.com/video/BV...',
                            ),
                            const SizedBox(height: 18),
                            _LessonModalSelect(
                              label: '学习目标',
                              value: _goal,
                              enabled: !_isSubmitting,
                              items: const ['期末复习', '日常学习'],
                              onChanged: (value) {
                                if (value != null) {
                                  setState(() => _goal = value);
                                }
                              },
                            ),
                            const SizedBox(height: 18),
                            _LessonModalSelect(
                              label: '当前掌握程度',
                              value: _mastery,
                              enabled: !_isSubmitting,
                              items: const [
                                '零基础',
                                '基础一般',
                                '已经学过，想查漏补缺',
                              ],
                              onChanged: (value) {
                                if (value != null) {
                                  setState(() => _mastery = value);
                                }
                              },
                            ),
                            const SizedBox(height: 18),
                            _LessonModalInput(
                              label: '时间预算',
                              controller: _timeBudgetController,
                              enabled: !_isSubmitting,
                              keyboardType:
                                  const TextInputType.numberWithOptions(
                                decimal: true,
                              ),
                              hintText: '例如：2',
                              suffix: const Text(
                                '小时',
                                style: TextStyle(
                                  color: AppTheme.muted,
                                  fontWeight: FontWeight.w800,
                                ),
                              ),
                            ),
                            const SizedBox(height: 20),
                            _LessonCreateActions(
                              isSubmitting: _isSubmitting,
                              onCancel: _close,
                              onSubmit: _submit,
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  void _close() {
    Navigator.of(context).pop();
  }

  Future<void> _pickFiles() async {
    if (_isSubmitting || _isPickingFiles) {
      return;
    }

    setState(() {
      _isPickingFiles = true;
    });

    try {
      final drafts = await _pickLessonUploadDrafts();
      if (!mounted) {
        return;
      }
      if (drafts.isEmpty) {
        return;
      }
      setState(() {
        _selectedFiles.addAll(drafts);
      });
    } catch (error) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('选择资料失败：$error')),
      );
    } finally {
      if (mounted) {
        setState(() {
          _isPickingFiles = false;
        });
      }
    }
  }

  void _removeFile(String fileId) {
    if (_isSubmitting) {
      return;
    }
    setState(() {
      _selectedFiles.removeWhere((file) => file.id == fileId);
    });
  }

  Future<void> _submit() async {
    if (_isSubmitting) {
      return;
    }
    final title = _titleController.text.trim();
    if (title.isEmpty) {
      _titleFocusNode.requestFocus();
      return;
    }

    setState(() {
      _isSubmitting = true;
    });

    LessonSummaryModel? createdLesson;
    try {
      createdLesson = await ref.read(courseLessonApiProvider).createLesson(
            courseId: widget.courseId,
            request: {
              'title': title,
              'sourceType': 'manual',
            },
            idempotencyKey:
                'lesson-create-${DateTime.now().microsecondsSinceEpoch}',
          );
      if (!mounted) {
        return;
      }
      _finishCreation(createdLesson);
    } catch (error) {
      if (!mounted) {
        return;
      }
      if (createdLesson != null) {
        _finishCreation(createdLesson);
        return;
      }
      setState(() {
        _isSubmitting = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('创建课时失败：$error')),
      );
    }
  }

  void _finishCreation(LessonSummaryModel lesson) {
    final payload = LessonPreparationPayload(
      lesson: lesson,
      files: List<LessonPreparationUploadDraft>.unmodifiable(_selectedFiles),
    );
    Navigator.of(context).pop();
    scheduleMicrotask(() {
      widget.onCreated(payload);
    });
  }
}

class LessonPreparationPage extends ConsumerStatefulWidget {
  const LessonPreparationPage({
    required this.courseId,
    required this.lessonId,
    this.payload,
    super.key,
  });

  final String courseId;
  final String lessonId;
  final LessonPreparationPayload? payload;

  @override
  ConsumerState<LessonPreparationPage> createState() =>
      _LessonPreparationPageState();
}

const _lessonPreparationPollInterval = Duration(seconds: 1);
const _lessonPreparationMaxAttempts = 60;

class _LessonPreparationPageState extends ConsumerState<LessonPreparationPage>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  PipelineStatusModel? _status;
  HandoutVersionStatusModel? _handoutStatus;
  Object? _error;
  var _uploadProgressPct = 0;
  var _overallProgressPct = 0;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1600),
    )..repeat();
    WidgetsBinding.instance.addPostFrameCallback((_) => _startPreparation());
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _startPreparation() async {
    try {
      final apiClient = ref.read(apiClientProvider);
      await _uploadPendingFiles(apiClient);
      if (!mounted) {
        return;
      }
      await apiClient.startParse(
        courseId: widget.courseId,
        idempotencyKey:
            'lesson-prepare-${widget.courseId}-${widget.lessonId}-${DateTime.now().microsecondsSinceEpoch}',
      );

      for (var attempt = 0;
          attempt < _lessonPreparationMaxAttempts;
          attempt += 1) {
        if (!mounted) {
          return;
        }
        final status = await apiClient.fetchPipelineStatus(widget.courseId);
        if (!mounted) {
          return;
        }
        setState(() {
          _status = status;
          _overallProgressPct = _overallProgressFromPipeline(status);
        });

        if (_lessonPreparationFailed(status)) {
          setState(() {
            _error = '资料解析或目录生成失败，请返回后重试。';
          });
          return;
        }
        if (_lessonPreparationReady(status)) {
          break;
        }
        await Future<void>.delayed(_lessonPreparationPollInterval);
        if (attempt == _lessonPreparationMaxAttempts - 1) {
          throw TimeoutException('资料解析等待超时');
        }
      }

      final generated = await apiClient.generateLessonHandout(
        courseId: widget.courseId,
        lessonId: widget.lessonId,
        idempotencyKey:
            'lesson-handout-${widget.courseId}-${widget.lessonId}-${DateTime.now().microsecondsSinceEpoch}',
      );
      final handoutVersionId = generated.entity.id;
      for (var attempt = 0;
          attempt < _lessonPreparationMaxAttempts;
          attempt += 1) {
        if (!mounted) {
          return;
        }
        final status = await apiClient.fetchHandoutVersionStatus(
          handoutVersionId,
        );
        if (!mounted) {
          return;
        }
        setState(() {
          _handoutStatus = status;
          _overallProgressPct = _overallProgressFromHandout(status);
        });
        if (_lessonHandoutReady(status)) {
          setState(() {
            _overallProgressPct = 100;
          });
          _safeGo(
            context,
            '/courses/${widget.courseId}/lessons/${widget.lessonId}/handout',
          );
          return;
        }
        if (_lessonHandoutFailed(status)) {
          setState(() {
            _error = '学习目录生成失败，请返回后重试。';
          });
          return;
        }
        await Future<void>.delayed(_lessonPreparationPollInterval);
        if (attempt == _lessonPreparationMaxAttempts - 1) {
          throw TimeoutException('学习目录生成等待超时');
        }
      }
    } catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = error;
      });
    }
  }

  Future<void> _uploadPendingFiles(ApiClient apiClient) async {
    final files =
        widget.payload?.files ?? const <LessonPreparationUploadDraft>[];
    if (files.isEmpty) {
      setState(() {
        _uploadProgressPct = 100;
        _overallProgressPct = 18;
      });
      return;
    }

    for (var index = 0; index < files.length; index += 1) {
      final file = files[index];
      final uploadInit = await apiClient.initResourceUpload(
        courseId: widget.courseId,
        request: ResourceUploadInitRequestModel(
          resourceType: file.resourceType,
          filename: file.name,
          mimeType: file.mimeType,
          sizeBytes: file.sizeBytes,
          checksum: file.checksum,
          scopeType: 'lesson',
          lessonId: widget.lessonId,
          usageRole: file.usageRole,
          lessonPlacement: file.lessonPlacement,
          visibleToCourseQa: true,
        ),
      );

      await apiClient.uploadObject(
        uploadUrl: uploadInit.uploadUrl,
        bytes: file.bytes,
        headers: uploadInit.headers,
        mimeType: file.mimeType,
      );

      await apiClient.completeResourceUpload(
        courseId: widget.courseId,
        request: ResourceUploadCompleteRequestModel(
          resourceType: file.resourceType,
          objectKey: uploadInit.objectKey,
          originalName: file.name,
          mimeType: file.mimeType,
          sizeBytes: file.sizeBytes,
          checksum: file.checksum,
          scopeType: 'lesson',
          lessonId: widget.lessonId,
          usageRole: file.usageRole,
          lessonPlacement: file.lessonPlacement,
          visibleToCourseQa: true,
        ),
        idempotencyKey:
            'lesson-upload-${widget.courseId}-${widget.lessonId}-${file.id}',
      );

      if (!mounted) {
        return;
      }
      final nextProgress = (((index + 1) / files.length) * 100).round();
      setState(() {
        _uploadProgressPct = nextProgress;
        _overallProgressPct = (nextProgress * 0.18).round();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final status = _status;
    final error = _error;
    return AppScaffold(
      title: '准备课时',
      activeTab: KnowLinkTab.handout,
      courseId: widget.courseId,
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 620),
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 34),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Center(
                  child: _LessonPreparationLoader(
                    controller: _controller,
                  ),
                ),
                const SizedBox(height: 28),
                const Text(
                  '正在准备课时',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    color: AppTheme.ink,
                    fontSize: 34,
                    height: 1,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 0,
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  error == null
                      ? '上传资料、解析资料和生成学习目录会连续执行，完成后自动进入课时学习。'
                      : error.toString(),
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    color: error == null ? AppTheme.muted : AppTheme.danger,
                    fontSize: 14,
                    height: 1.5,
                    fontWeight: FontWeight.w600,
                    letterSpacing: 0,
                  ),
                ),
                const SizedBox(height: 24),
                _LessonPreparationProgress(progressPct: _overallProgressPct),
                const SizedBox(height: 18),
                _LessonPreparationSteps(
                  uploadProgressPct: _uploadProgressPct,
                  status: status,
                  handoutStatus: _handoutStatus,
                ),
                if (error != null) ...[
                  const SizedBox(height: 22),
                  Align(
                    alignment: Alignment.center,
                    child: OutlinedButton.icon(
                      onPressed: () => _safeGo(
                        context,
                        '/courses/${widget.courseId}',
                      ),
                      icon: const Icon(Icons.arrow_back_rounded),
                      label: const Text('返回课程工作台'),
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _LessonPreparationLoader extends StatelessWidget {
  const _LessonPreparationLoader({required this.controller});

  final Animation<double> controller;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      key: const Key('lesson_preparation_loader'),
      width: 180,
      height: 148,
      child: AnimatedBuilder(
        animation: controller,
        builder: (context, child) {
          return CustomPaint(
            painter: _LoaderOfThingsPainter(progress: controller.value),
          );
        },
      ),
    );
  }
}

class _LessonPreparationProgress extends StatelessWidget {
  const _LessonPreparationProgress({required this.progressPct});

  final int progressPct;

  @override
  Widget build(BuildContext context) {
    final pct = progressPct.clamp(0, 100).toInt();
    return Column(
      children: [
        Text(
          '$pct%',
          key: const Key('lesson_preparation_progress_text'),
          textAlign: TextAlign.center,
          style: const TextStyle(
            color: AppTheme.ink,
            fontSize: 32,
            height: 1,
            fontWeight: FontWeight.w900,
            letterSpacing: 0,
          ),
        ),
        const SizedBox(height: 12),
        Container(
          height: 14,
          decoration: BoxDecoration(
            color: AppTheme.surface,
            borderRadius: BorderRadius.circular(999),
            boxShadow: AppTheme.shadowInsetLook,
          ),
          padding: const EdgeInsets.all(3),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(999),
            child: LinearProgressIndicator(
              minHeight: 8,
              value: pct / 100,
              backgroundColor: Colors.transparent,
              valueColor: const AlwaysStoppedAnimation<Color>(
                AppTheme.brandBlue,
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _LoaderOfThingsPainter extends CustomPainter {
  const _LoaderOfThingsPainter({required this.progress});

  final double progress;

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2 + 4);
    final shadowPaint = Paint()
      ..color = const Color(0x263D4852)
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 12);

    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(center.dx, center.dy + 33),
        width: 92,
        height: 18,
      ),
      shadowPaint,
    );

    for (var index = 5; index >= 0; index -= 1) {
      final depth = index / 5;
      final phase = (progress + index * 0.105) % 1;
      final lift = math.sin((progress * math.pi * 2) + index * 0.72) * 3.6;
      final ringCenter = Offset(
        center.dx,
        center.dy + (index - 2.5) * 8.2 + lift,
      );
      final width = 92 - index * 6.4;
      final height = 31 - index * 2.2;
      final roll = (phase - 0.5) * 0.28;
      final color = Color.lerp(
        AppTheme.brandBlue,
        AppTheme.success,
        depth,
      )!;
      _drawRing(
        canvas,
        center: ringCenter,
        width: width,
        height: height,
        roll: roll,
        color: color,
        opacity: 0.42 + (1 - depth) * 0.18,
        frontBoost: 0.32 + _wave(progress, index * 0.13) * 0.26,
      );
    }

    final glow = Paint()
      ..shader = RadialGradient(
        colors: [
          AppTheme.surface.withValues(alpha: 0.96),
          AppTheme.surface.withValues(alpha: 0.42),
          AppTheme.surface.withValues(alpha: 0),
        ],
      ).createShader(
        Rect.fromCircle(center: center, radius: 34),
      );
    canvas.drawCircle(center, 33, glow);

    final corePaint = Paint()
      ..color = AppTheme.surface
      ..style = PaintingStyle.fill;
    canvas.drawCircle(center, 18, corePaint);

    final coreStroke = Paint()
      ..color = AppTheme.brandBlue.withValues(alpha: 0.28)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2;
    canvas.drawCircle(center, 18, coreStroke);

    final sparkPaint = Paint()
      ..color = AppTheme.ink
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2
      ..strokeCap = StrokeCap.round;
    final sparkPath = Path()
      ..moveTo(center.dx, center.dy - 9)
      ..lineTo(center.dx, center.dy + 9)
      ..moveTo(center.dx - 9, center.dy)
      ..lineTo(center.dx + 9, center.dy);
    canvas.drawPath(sparkPath, sparkPaint);
  }

  void _drawRing(
    Canvas canvas, {
    required Offset center,
    required double width,
    required double height,
    required double roll,
    required Color color,
    required double opacity,
    required double frontBoost,
  }) {
    final rect =
        Rect.fromCenter(center: Offset.zero, width: width, height: height);
    canvas.save();
    canvas.translate(center.dx, center.dy);
    canvas.rotate(roll);

    final base = Paint()
      ..color = color.withValues(alpha: opacity)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3.2
      ..strokeCap = StrokeCap.round
      ..isAntiAlias = true;
    canvas.drawArc(rect, math.pi, math.pi, false, base);

    final front = Paint()
      ..color = color.withValues(
        alpha: (opacity + frontBoost).clamp(0, 1).toDouble(),
      )
      ..style = PaintingStyle.stroke
      ..strokeWidth = 5.2
      ..strokeCap = StrokeCap.round
      ..isAntiAlias = true;
    canvas.drawArc(rect, 0, math.pi, false, front);

    final highlight = Paint()
      ..color = Colors.white.withValues(alpha: 0.54)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.2
      ..strokeCap = StrokeCap.round
      ..isAntiAlias = true;
    canvas.drawArc(rect.deflate(1.8), 0.24, math.pi * 0.32, false, highlight);
    canvas.restore();
  }

  double _wave(double value, double phase) {
    final shifted = (value + phase) % 1;
    return 0.5 + 0.5 * math.sin(shifted * math.pi * 2);
  }

  @override
  bool shouldRepaint(covariant _LoaderOfThingsPainter oldDelegate) {
    return oldDelegate.progress != progress;
  }
}

class _LessonPreparationSteps extends StatelessWidget {
  const _LessonPreparationSteps({
    required this.uploadProgressPct,
    required this.status,
    required this.handoutStatus,
  });

  final int uploadProgressPct;
  final PipelineStatusModel? status;
  final HandoutVersionStatusModel? handoutStatus;

  @override
  Widget build(BuildContext context) {
    final pipelineStatus = status;
    final versionStatus = handoutStatus;
    final documentStatus = _combinedParseStatus(pipelineStatus);
    final outlineStatus = versionStatus?.status ??
        (pipelineStatus == null || !_lessonPreparationReady(pipelineStatus)
            ? _stepStatus(status, 'knowledge_extract')
            : 'running');
    return Column(
      key: const Key('lesson_preparation_steps'),
      children: [
        _LessonPreparationStepTile(
          icon: Icons.upload_file_outlined,
          label: '上传资料',
          status: uploadProgressPct >= 100 ? 'succeeded' : 'running',
          progressPct: uploadProgressPct,
        ),
        const SizedBox(height: 10),
        _LessonPreparationStepTile(
          icon: Icons.description_outlined,
          label: '解析资料',
          status: documentStatus,
          progressPct: _stepProgress(status, 'document_parse'),
        ),
        const SizedBox(height: 10),
        _LessonPreparationStepTile(
          icon: Icons.view_list_outlined,
          label: '生成学习目录',
          status: outlineStatus,
          progressPct: _handoutProgressPct(versionStatus) ??
              _stepProgress(status, 'knowledge_extract'),
        ),
      ],
    );
  }
}

class _LessonPreparationStepTile extends StatelessWidget {
  const _LessonPreparationStepTile({
    required this.icon,
    required this.label,
    required this.status,
    this.progressPct,
  });

  final IconData icon;
  final String label;
  final String status;
  final int? progressPct;

  @override
  Widget build(BuildContext context) {
    final done = _pipelineStepComplete(status);
    final failed = status == 'failed';
    final color = failed
        ? AppTheme.danger
        : done
            ? AppTheme.success
            : AppTheme.brandBlue;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(18),
        boxShadow: AppTheme.shadowSmall,
      ),
      child: Row(
        children: [
          Icon(icon, color: color, size: 22),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              label,
              style: const TextStyle(
                color: AppTheme.ink,
                fontSize: 15,
                fontWeight: FontWeight.w800,
                letterSpacing: 0,
              ),
            ),
          ),
          Text(
            done
                ? '完成'
                : failed
                    ? '失败'
                    : '${progressPct ?? 0}%',
            style: TextStyle(
              color: color,
              fontSize: 13,
              fontWeight: FontWeight.w800,
              letterSpacing: 0,
            ),
          ),
        ],
      ),
    );
  }
}

const _lessonResourceTypeGroup = XTypeGroup(
  label: 'KnowLink lesson resources',
  extensions: ['mp4', 'pdf', 'pptx', 'docx', 'srt'],
);

class LessonPreparationUploadDraft {
  const LessonPreparationUploadDraft({
    required this.id,
    required this.name,
    required this.resourceType,
    required this.mimeType,
    required this.sizeBytes,
    required this.checksum,
    required this.bytes,
  });

  final String id;
  final String name;
  final ResourceType resourceType;
  final String mimeType;
  final int sizeBytes;
  final String checksum;
  final Uint8List bytes;

  String get usageRole =>
      resourceType == ResourceType.mp4 ? 'primary_video' : 'lesson_material';

  String? get lessonPlacement =>
      resourceType == ResourceType.mp4 ? 'bind_existing' : null;
}

Future<List<LessonPreparationUploadDraft>> _pickLessonUploadDrafts() async {
  final files = await openFiles(
    acceptedTypeGroups: const [_lessonResourceTypeGroup],
  );
  final drafts = <LessonPreparationUploadDraft>[];
  for (final file in files) {
    drafts.add(await _lessonUploadDraftFromXFile(file));
  }
  return drafts;
}

Future<LessonPreparationUploadDraft> _lessonUploadDraftFromXFile(
  XFile file,
) async {
  final bytes = await file.readAsBytes();
  final resourceType = _lessonResourceTypeFromFilename(file.name);
  return LessonPreparationUploadDraft(
    id: 'lesson-upload-${DateTime.now().microsecondsSinceEpoch}-${file.name}',
    name: file.name,
    resourceType: resourceType,
    mimeType: _lessonMimeTypeFor(resourceType),
    sizeBytes: bytes.length,
    checksum: 'sha256:${sha256.convert(bytes).toString()}',
    bytes: Uint8List.fromList(bytes),
  );
}

ResourceType _lessonResourceTypeFromFilename(String filename) {
  final extension = filename.split('.').last.toLowerCase();
  for (final type in ResourceType.values) {
    if (type.name == extension) {
      return type;
    }
  }
  throw ArgumentError.value(filename, 'filename', '不支持的资料类型');
}

String _lessonMimeTypeFor(ResourceType type) {
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

class _LessonCreateHeader extends StatelessWidget {
  const _LessonCreateHeader({required this.onClose});

  final VoidCallback? onClose;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '新建课时',
                style: TextStyle(
                  color: AppTheme.ink,
                  fontSize: 36,
                  fontWeight: FontWeight.w800,
                  height: 1,
                  letterSpacing: 0,
                ),
              ),
              SizedBox(height: 8),
              Text(
                '填写课时信息后，可上传资料或导入 B 站视频作为学习内容。',
                style: TextStyle(
                  color: AppTheme.muted,
                  fontSize: 15,
                  fontWeight: FontWeight.w500,
                  height: 1.45,
                  letterSpacing: 0,
                ),
              ),
            ],
          ),
        ),
        const SizedBox(width: 16),
        SizedBox(
          width: 44,
          height: 44,
          child: Material(
            color: AppTheme.surface,
            borderRadius: BorderRadius.circular(16),
            child: InkWell(
              borderRadius: BorderRadius.circular(16),
              onTap: onClose,
              child: DecoratedBox(
                decoration: BoxDecoration(
                  color: AppTheme.surface,
                  borderRadius: BorderRadius.circular(16),
                  boxShadow: AppTheme.shadowSmall,
                ),
                child: const Center(
                  child: Text(
                    '×',
                    style: TextStyle(
                      color: AppTheme.ink,
                      fontSize: 24,
                      height: 1,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _LessonModalLabel extends StatelessWidget {
  const _LessonModalLabel(this.label);

  final String label;

  @override
  Widget build(BuildContext context) {
    return Text(
      label,
      style: const TextStyle(
        color: AppTheme.muted,
        fontSize: 12,
        fontWeight: FontWeight.w700,
        letterSpacing: 0.96,
      ),
    );
  }
}

class _LessonModalInput extends StatelessWidget {
  const _LessonModalInput({
    required this.label,
    required this.controller,
    required this.enabled,
    required this.hintText,
    this.focusNode,
    this.keyboardType,
    this.onSubmitted,
    this.suffix,
  });

  final String label;
  final TextEditingController controller;
  final FocusNode? focusNode;
  final bool enabled;
  final String hintText;
  final TextInputType? keyboardType;
  final ValueChanged<String>? onSubmitted;
  final Widget? suffix;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _LessonModalLabel(label),
        const SizedBox(height: 8),
        Container(
          height: 50,
          decoration: BoxDecoration(
            color: AppTheme.surface,
            borderRadius: BorderRadius.circular(16),
            boxShadow: AppTheme.shadowInsetLook,
          ),
          alignment: Alignment.center,
          child: TextField(
            controller: controller,
            focusNode: focusNode,
            enabled: enabled,
            keyboardType: keyboardType,
            textInputAction: onSubmitted == null
                ? TextInputAction.next
                : TextInputAction.done,
            onSubmitted: onSubmitted,
            style: const TextStyle(
              color: AppTheme.ink,
              fontSize: 14,
              fontWeight: FontWeight.w600,
              letterSpacing: 0,
            ),
            decoration: InputDecoration(
              hintText: hintText,
              hintStyle: const TextStyle(color: Color(0xFF9AA3AF)),
              suffixIcon: suffix == null
                  ? null
                  : Padding(
                      padding: const EdgeInsets.only(right: 16),
                      child: Center(widthFactor: 1, child: suffix),
                    ),
              border: InputBorder.none,
              enabledBorder: InputBorder.none,
              focusedBorder: InputBorder.none,
              disabledBorder: InputBorder.none,
              contentPadding: const EdgeInsets.symmetric(horizontal: 16),
            ),
          ),
        ),
      ],
    );
  }
}

class _LessonModalSelect extends StatelessWidget {
  const _LessonModalSelect({
    required this.label,
    required this.value,
    required this.enabled,
    required this.items,
    required this.onChanged,
  });

  final String label;
  final String value;
  final bool enabled;
  final List<String> items;
  final ValueChanged<String?> onChanged;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _LessonModalLabel(label),
        const SizedBox(height: 8),
        Container(
          height: 50,
          padding: const EdgeInsets.symmetric(horizontal: 16),
          decoration: BoxDecoration(
            color: AppTheme.surface,
            borderRadius: BorderRadius.circular(16),
            boxShadow: AppTheme.shadowInsetLook,
          ),
          alignment: Alignment.center,
          child: DropdownButtonHideUnderline(
            child: DropdownButton<String>(
              value: value,
              isExpanded: true,
              borderRadius: BorderRadius.circular(16),
              dropdownColor: AppTheme.surface,
              iconEnabledColor: AppTheme.ink,
              style: const TextStyle(
                color: AppTheme.ink,
                fontSize: 14,
                fontWeight: FontWeight.w600,
              ),
              items: [
                for (final item in items)
                  DropdownMenuItem(value: item, child: Text(item)),
              ],
              onChanged: enabled ? onChanged : null,
            ),
          ),
        ),
      ],
    );
  }
}

class _LessonMaterialsPicker extends StatelessWidget {
  const _LessonMaterialsPicker({
    required this.enabled,
    required this.isPicking,
    required this.selectedFiles,
    required this.onPick,
    required this.onRemove,
  });

  final bool enabled;
  final bool isPicking;
  final List<LessonPreparationUploadDraft> selectedFiles;
  final VoidCallback onPick;
  final ValueChanged<String> onRemove;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const _LessonModalLabel('上传资料'),
        const SizedBox(height: 8),
        Wrap(
          spacing: 10,
          runSpacing: 10,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            OutlinedButton(
              onPressed: enabled && !isPicking ? onPick : null,
              child: Text(isPicking ? '选择中...' : '上传资料'),
            ),
            if (selectedFiles.isEmpty)
              const Text(
                '暂未选择文件',
                style: TextStyle(
                  color: AppTheme.muted,
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                ),
              )
            else
              for (final file in selectedFiles)
                _LessonMaterialChip(
                  file: file,
                  enabled: enabled,
                  onRemove: onRemove,
                ),
          ],
        ),
        const SizedBox(height: 8),
        const Text(
          '支持 PDF、DOCX、PPTX、MP4、SRT 格式。创建课时后自动绑定到该课时。',
          style: TextStyle(
            color: AppTheme.muted,
            fontSize: 12,
            fontWeight: FontWeight.w500,
          ),
        ),
      ],
    );
  }
}

class _LessonMaterialChip extends StatelessWidget {
  const _LessonMaterialChip({
    required this.file,
    required this.enabled,
    required this.onRemove,
  });

  final LessonPreparationUploadDraft file;
  final bool enabled;
  final ValueChanged<String> onRemove;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(maxWidth: 260),
      padding: const EdgeInsets.only(left: 12, right: 6),
      height: 36,
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(18),
        boxShadow: AppTheme.shadowSmall,
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Flexible(
            child: Text(
              file.name,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: AppTheme.ink,
                fontSize: 13,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          const SizedBox(width: 4),
          SizedBox(
            width: 28,
            height: 28,
            child: IconButton(
              padding: EdgeInsets.zero,
              tooltip: '移除资料',
              onPressed: enabled ? () => onRemove(file.id) : null,
              icon: const Icon(Icons.close_rounded, size: 16),
            ),
          ),
        ],
      ),
    );
  }
}

class _LessonCreateActions extends StatelessWidget {
  const _LessonCreateActions({
    required this.isSubmitting,
    required this.onCancel,
    required this.onSubmit,
  });

  final bool isSubmitting;
  final VoidCallback onCancel;
  final VoidCallback onSubmit;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.end,
      children: [
        OutlinedButton(
          onPressed: isSubmitting ? null : onCancel,
          child: const Text('取消'),
        ),
        const SizedBox(width: 10),
        FilledButton(
          onPressed: isSubmitting ? null : onSubmit,
          child: isSubmitting
              ? const SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(
                    strokeWidth: 2.2,
                    color: Colors.white,
                  ),
                )
              : const Text('创建课时'),
        ),
      ],
    );
  }
}

class _WorkspaceCards extends StatelessWidget {
  const _WorkspaceCards({required this.model});

  final CourseWorkbenchModel model;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final twoColumns = constraints.maxWidth >= 760;
        final width =
            twoColumns ? (constraints.maxWidth - 16) / 2 : constraints.maxWidth;
        return Wrap(
          spacing: 16,
          runSpacing: 16,
          children: [
            SizedBox(
              width: width,
              child: _ResourceCard(resources: model.courseResources),
            ),
            SizedBox(
              width: width,
              child: _QuizCard(model: model),
            ),
          ],
        );
      },
    );
  }
}

class _ResourceCard extends StatelessWidget {
  const _ResourceCard({required this.resources});

  final List<ScopedResourceModel> resources;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Expanded(child: _SectionLabel('课程资料')),
              const SizedBox(width: 12),
              FilledButton.icon(
                onPressed: _noop,
                icon: const Icon(Icons.upload_file_outlined),
                label: const Text('上传资料'),
              ),
            ],
          ),
          const SizedBox(height: 16),
          if (resources.isEmpty)
            const Text('暂无课程级资料。')
          else
            Column(
              children: [
                for (final resource in resources) ...[
                  _SoftRow(
                    leading: _ResourceBadge(type: resource.resourceType),
                    title: resource.originalName,
                    subtitle: '${resource.scopeType} · ${resource.usageRole}',
                  ),
                  if (resource != resources.last) const SizedBox(height: 12),
                ],
              ],
            ),
        ],
      ),
    );
  }
}

class _QuizCard extends StatelessWidget {
  const _QuizCard({required this.model});

  final CourseWorkbenchModel model;

  @override
  Widget build(BuildContext context) {
    final course = model.course;
    final completed = _progressCompleted(model);
    final total = _progressTotal(model);
    final score = course.overallMasteryScore == null
        ? model.progressPct
        : (course.overallMasteryScore! * 100).round();
    final quizRoute = _entryRoute(
      model,
      'comprehensive_quiz',
      '/courses/${course.courseId}/quiz',
    );
    final reviewRoute = '/courses/${course.courseId}/review'
        '?kind=comprehensive_quiz';
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionLabel('综合测验'),
          const SizedBox(height: 14),
          LayoutBuilder(
            builder: (context, constraints) {
              final twoColumns = constraints.maxWidth >= 360;
              final width = twoColumns
                  ? (constraints.maxWidth - 16) / 2
                  : constraints.maxWidth;
              return Wrap(
                spacing: 16,
                runSpacing: 16,
                children: [
                  SizedBox(
                    width: width,
                    child: _MetricTile(
                      label: '题目数量',
                      value: '$completed / $total',
                    ),
                  ),
                  SizedBox(
                    width: width,
                    child: _MetricTile(
                      label: '正确率',
                      value: '$score%',
                    ),
                  ),
                ],
              );
            },
          ),
          const SizedBox(height: 16),
          ProgressRail(value: model.progressPct / 100),
          const SizedBox(height: 16),
          Wrap(
            key: const Key('course_workbench_secondary_entries'),
            spacing: 10,
            runSpacing: 10,
            children: [
              FilledButton(
                onPressed: () => _safeGo(context, quizRoute),
                child: const Text('开始测验'),
              ),
              OutlinedButton(
                onPressed: () => _safeGo(context, reviewRoute),
                child: const Text('重新生成'),
              ),
              OutlinedButton(
                onPressed: () => _safeGo(context, reviewRoute),
                child: const Text('历史测验'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _MetricTile extends StatelessWidget {
  const _MetricTile({
    required this.label,
    required this.value,
  });

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minHeight: 104),
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(26),
        boxShadow: AppTheme.shadowInsetLook,
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              color: AppTheme.muted,
              fontSize: 12,
              fontWeight: FontWeight.w800,
              letterSpacing: 0,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            value,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              color: AppTheme.ink,
              fontSize: 34,
              fontWeight: FontWeight.w800,
              height: 1,
            ),
          ),
        ],
      ),
    );
  }
}

class _LessonGrid extends StatelessWidget {
  const _LessonGrid({
    required this.courseId,
    required this.lessons,
  });

  final String courseId;
  final List<LessonSummaryModel> lessons;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionLabel('课时'),
          const SizedBox(height: 14),
          if (lessons.isEmpty)
            const Text('暂无课时。')
          else
            LayoutBuilder(
              builder: (context, constraints) {
                final columns = _lessonColumnCount(constraints.maxWidth);
                final width =
                    (constraints.maxWidth - (columns - 1) * 16) / columns;
                return Wrap(
                  spacing: 16,
                  runSpacing: 16,
                  children: [
                    for (final lesson in lessons)
                      SizedBox(
                        width: width,
                        child: _LessonTile(
                          courseId: courseId,
                          lesson: lesson,
                        ),
                      ),
                  ],
                );
              },
            ),
        ],
      ),
    );
  }
}

class _LessonTile extends StatelessWidget {
  const _LessonTile({
    required this.courseId,
    required this.lesson,
  });

  final String courseId;
  final LessonSummaryModel lesson;

  @override
  Widget build(BuildContext context) {
    final progress = _lessonProgress(lesson);
    final completed = _lessonCompleted(lesson, progress);
    final progressColor = completed
        ? AppTheme.success
        : progress == 0
            ? AppTheme.accentLight
            : AppTheme.brandBlue;
    final route = '/courses/$courseId/lessons/${lesson.lessonId}/handout';
    return DecoratedBox(
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(28),
        boxShadow: AppTheme.shadowInsetLook,
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(28),
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            onTap: () => _safeGo(context, route),
            child: Padding(
              padding: const EdgeInsets.all(18),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  StatusPill(
                    label: completed ? '已完成' : '未完成',
                    color: completed ? AppTheme.success : AppTheme.accentLight,
                  ),
                  const SizedBox(height: 12),
                  Text(
                    lesson.title,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: AppTheme.ink,
                      fontSize: 20,
                      fontWeight: FontWeight.w800,
                      height: 1.15,
                    ),
                  ),
                  const SizedBox(height: 14),
                  StatusPill(label: '${(progress * 100).round()}%'),
                  const SizedBox(height: 14),
                  ProgressRail(value: progress, color: progressColor),
                  const SizedBox(height: 18),
                  FilledButton.icon(
                    onPressed: () => _safeGo(context, route),
                    icon: const Icon(Icons.play_arrow_outlined),
                    label: const Text('继续学习'),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _SoftRow extends StatelessWidget {
  const _SoftRow({
    required this.leading,
    required this.title,
    this.subtitle,
  });

  final Widget leading;
  final String title;
  final String? subtitle;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(22),
        boxShadow: AppTheme.shadowInsetLook,
      ),
      child: Row(
        children: [
          leading,
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: AppTheme.ink,
                    fontSize: 15,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                if (subtitle != null && subtitle!.isNotEmpty) ...[
                  const SizedBox(height: 4),
                  Text(
                    subtitle!,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: AppTheme.muted,
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      height: 1.3,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _SectionLabel extends StatelessWidget {
  const _SectionLabel(this.text);

  final String text;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 24,
          height: 24,
          decoration: BoxDecoration(
            color: AppTheme.surface,
            borderRadius: BorderRadius.circular(999),
            boxShadow: AppTheme.shadowInsetLook,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Text(
            text,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              color: AppTheme.ink,
              fontSize: 22,
              fontWeight: FontWeight.w800,
              height: 1.15,
            ),
          ),
        ),
      ],
    );
  }
}

class _ResourceBadge extends StatelessWidget {
  const _ResourceBadge({required this.type});

  final String type;

  @override
  Widget build(BuildContext context) {
    return _SoftBadge(
      label: _resourceLabel(type),
      color: _resourceColor(type),
    );
  }
}

class _SoftBadge extends StatelessWidget {
  const _SoftBadge({
    required this.label,
    required this.color,
  });

  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 44,
      height: 44,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(18),
        boxShadow: AppTheme.shadowRaised,
      ),
      child: Text(
        label,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: TextStyle(
          color: color,
          fontSize: 11,
          fontWeight: FontWeight.w800,
        ),
      ),
    );
  }
}

int _lessonColumnCount(double width) {
  if (width >= 840) {
    return 4;
  }
  if (width >= 560) {
    return 2;
  }
  return 1;
}

bool _lessonPreparationReady(PipelineStatusModel status) {
  final parseReady = _stepComplete(status, 'caption_extract') &&
      _stepComplete(status, 'document_parse');
  final outlineReady = _stepComplete(status, 'knowledge_extract') ||
      status.sourceOverview?.outlineReady == true ||
      _pipelineStepComplete(status.handoutOutline?.status ?? '');
  return parseReady && outlineReady;
}

bool _lessonPreparationFailed(PipelineStatusModel status) {
  if (status.courseStatus.pipelineStatus == 'failed') {
    return true;
  }
  return status.steps.any((step) {
    return step.status == 'failed' &&
        (step.code == 'caption_extract' ||
            step.code == 'document_parse' ||
            step.code == 'knowledge_extract');
  });
}

bool _lessonHandoutReady(HandoutVersionStatusModel status) {
  return status.status == 'outline_ready' ||
      status.status == 'ready' ||
      status.status == 'partial_success' ||
      status.outlineStatus == 'ready';
}

bool _lessonHandoutFailed(HandoutVersionStatusModel status) {
  return status.status == 'failed' || status.outlineStatus == 'failed';
}

int _overallProgressFromPipeline(PipelineStatusModel status) {
  final pct = status.progressPct.clamp(0, 100).toInt();
  final value = (18 + pct * 0.52).round();
  return value.clamp(18, 70).toInt();
}

int _overallProgressFromHandout(HandoutVersionStatusModel status) {
  final pct = _handoutProgressPct(status) ?? 0;
  final value = (70 + pct * 0.30).round();
  return value.clamp(70, 100).toInt();
}

int? _handoutProgressPct(HandoutVersionStatusModel? status) {
  if (status == null) {
    return null;
  }
  if (_lessonHandoutReady(status)) {
    return 100;
  }
  if (status.totalBlocks <= 0) {
    return status.status == 'generating' ? 50 : 0;
  }
  return ((status.readyBlocks / status.totalBlocks) * 100)
      .round()
      .clamp(0, 100)
      .toInt();
}

bool _stepComplete(PipelineStatusModel status, String code) {
  return _pipelineStepComplete(_stepStatus(status, code));
}

bool _pipelineStepComplete(String status) {
  return status == 'succeeded' ||
      status == 'skipped' ||
      status == 'ready' ||
      status == 'outline_ready' ||
      status == 'partial_success';
}

String _stepStatus(PipelineStatusModel? status, String code) {
  if (status == null) {
    return 'queued';
  }
  for (final step in status.steps) {
    if (step.code == code) {
      return step.status;
    }
  }
  return 'queued';
}

int? _stepProgress(PipelineStatusModel? status, String code) {
  if (status == null) {
    return null;
  }
  for (final step in status.steps) {
    if (step.code == code) {
      return step.progressPct;
    }
  }
  return null;
}

String _combinedParseStatus(PipelineStatusModel? status) {
  final caption = _stepStatus(status, 'caption_extract');
  final document = _stepStatus(status, 'document_parse');
  if (caption == 'failed' || document == 'failed') {
    return 'failed';
  }
  if (_pipelineStepComplete(caption) && _pipelineStepComplete(document)) {
    return 'succeeded';
  }
  if (caption == 'running' || document == 'running') {
    return 'running';
  }
  return 'queued';
}

int _progressCompleted(CourseWorkbenchModel model) {
  return _intValue(model.progress['completedLessonCount']) ??
      model.lessons
          .where((lesson) => _lessonCompleted(lesson, _lessonProgress(lesson)))
          .length;
}

int _progressTotal(CourseWorkbenchModel model) {
  return _intValue(model.progress['totalLessonCount']) ??
      _intValue(model.progress['lessonCount']) ??
      model.course.lessonCount;
}

double _lessonProgress(LessonSummaryModel lesson) {
  final score = lesson.masteryScore;
  if (score != null) {
    return score.clamp(0, 1).toDouble();
  }
  return _statusLooksComplete(lesson.lessonStatus) ? 1 : 0;
}

bool _lessonCompleted(LessonSummaryModel lesson, double progress) {
  return progress >= 0.995 || _statusLooksComplete(lesson.lessonStatus);
}

bool _statusLooksComplete(String status) {
  final normalized = status.toLowerCase();
  return normalized.contains('complete') ||
      normalized.contains('completed') ||
      normalized.contains('done') ||
      normalized.contains('finished');
}

String _entryRoute(
  CourseWorkbenchModel model,
  String key,
  String fallback,
) {
  final entry = _entryFor(model.quickEntries, key);
  return entry?.route ?? entry?.targetPath ?? entry?.target ?? fallback;
}

PlaceholderEntryModel? _entryFor(
  List<PlaceholderEntryModel> entries,
  String key,
) {
  for (final entry in entries) {
    if (entry.key == key) {
      return entry;
    }
  }
  return null;
}

int? _intValue(Object? value) {
  if (value == null) {
    return null;
  }
  if (value is int) {
    return value;
  }
  if (value is num) {
    return value.round();
  }
  return int.tryParse(value.toString());
}

String _resourceLabel(String type) {
  final text = type.trim();
  if (text.isEmpty) {
    return 'FILE';
  }
  if (text.length <= 4) {
    return text.toUpperCase();
  }
  return text.substring(0, 4).toUpperCase();
}

Color _resourceColor(String type) {
  final normalized = type.toLowerCase();
  if (normalized.contains('pdf')) {
    return AppTheme.danger;
  }
  if (normalized.contains('doc') || normalized.contains('srt')) {
    return AppTheme.success;
  }
  return AppTheme.brandBlue;
}

void _safeGo(BuildContext context, String path, {Object? extra}) {
  try {
    context.go(path, extra: extra);
  } catch (_) {
    // Widget tests can mount this page without a router.
  }
}

void _noop() {}
