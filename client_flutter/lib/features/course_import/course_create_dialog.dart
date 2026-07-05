import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/theme/app_theme.dart';
import '../../shared/models/course_create_request.dart';
import '../../shared/models/course_import_state.dart';
import '../../shared/models/course_summary.dart';
import '../../shared/providers/course_flow_providers.dart';
import '../../shared/providers/course_library_provider.dart';
import '../../shared/providers/course_recommend_provider.dart';

Future<CourseSummaryModel?> showCourseCreateDialog(BuildContext context) {
  return showGeneralDialog<CourseSummaryModel>(
    context: context,
    barrierDismissible: true,
    barrierLabel: '关闭',
    barrierColor: Colors.transparent,
    transitionDuration: const Duration(milliseconds: 180),
    pageBuilder: (context, animation, secondaryAnimation) {
      return const _CourseCreateDialog();
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

class _CourseCreateDialog extends ConsumerStatefulWidget {
  const _CourseCreateDialog();

  @override
  ConsumerState<_CourseCreateDialog> createState() =>
      _CourseCreateDialogState();
}

class _CourseCreateDialogState extends ConsumerState<_CourseCreateDialog> {
  final _titleController = TextEditingController();
  final _titleFocusNode = FocusNode();
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
                      maxWidth: 560,
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
                            _CourseCreateDialogHeader(
                              onClose: _isSubmitting ? null : _close,
                            ),
                            const SizedBox(height: 24),
                            _CourseNameField(
                              controller: _titleController,
                              focusNode: _titleFocusNode,
                              enabled: !_isSubmitting,
                              onSubmitted: (_) => _submit(),
                            ),
                            const SizedBox(height: 20),
                            _CourseCreateActions(
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

    try {
      final course = await ref.read(apiClientProvider).createCourse(
            request: CourseCreateRequestModel(
              title: title,
              goalText: CourseImportDraftModel.defaultGoalText,
            ),
            idempotencyKey:
                'course-create-${DateTime.now().microsecondsSinceEpoch}',
          );
      ref.read(courseFlowProvider.notifier).syncCreatedCourse(
            courseId: course.courseId,
            lifecycleStatus: course.lifecycleStatus,
            pipelineStage: course.pipelineStage,
            pipelineStatus: course.pipelineStatus,
          );
      ref.invalidate(courseLibraryProvider);
      if (!mounted) {
        return;
      }
      Navigator.of(context).pop(course);
    } catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _isSubmitting = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('创建课程失败：$error')),
      );
    }
  }
}

class _CourseCreateDialogHeader extends StatelessWidget {
  const _CourseCreateDialogHeader({required this.onClose});

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
                '新建课程',
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
                '填写课程基础信息后，可继续补充资料并生成学习计划。',
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

class _CourseNameField extends StatelessWidget {
  const _CourseNameField({
    required this.controller,
    required this.focusNode,
    required this.enabled,
    required this.onSubmitted,
  });

  final TextEditingController controller;
  final FocusNode focusNode;
  final bool enabled;
  final ValueChanged<String> onSubmitted;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          '课程名称',
          style: TextStyle(
            color: AppTheme.muted,
            fontSize: 12,
            fontWeight: FontWeight.w700,
            letterSpacing: 0.96,
          ),
        ),
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
            textInputAction: TextInputAction.done,
            onSubmitted: onSubmitted,
            style: const TextStyle(
              color: AppTheme.ink,
              fontSize: 14,
              fontWeight: FontWeight.w600,
              letterSpacing: 0,
            ),
            decoration: const InputDecoration(
              hintText: '例如：操作系统期末复习',
              hintStyle: TextStyle(color: Color(0xFF9AA3AF)),
              border: InputBorder.none,
              enabledBorder: InputBorder.none,
              focusedBorder: InputBorder.none,
              disabledBorder: InputBorder.none,
              contentPadding: EdgeInsets.symmetric(horizontal: 16),
            ),
          ),
        ),
      ],
    );
  }
}

class _CourseCreateActions extends StatelessWidget {
  const _CourseCreateActions({
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
              : const Text('创建课程'),
        ),
      ],
    );
  }
}
