import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/theme/app_theme.dart';
import '../../core/widgets/app_error_view.dart';
import '../../core/widgets/app_loading_view.dart';
import '../../core/widgets/app_scaffold.dart';
import '../../core/widgets/knowlink_widgets.dart';
import '../../shared/models/course_lesson_models.dart';
import '../../shared/providers/course_flow_providers.dart';
import '../../shared/providers/course_library_provider.dart';
import '../../shared/services/course_lesson_api.dart';

class CourseLibraryPage extends ConsumerWidget {
  const CourseLibraryPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final courses = ref.watch(courseLibraryProvider);
    return AppScaffold(
      title: '课程库',
      activeTab: KnowLinkTab.library,
      body: courses.when(
        loading: () => const AppLoadingView(label: '正在加载课程库'),
        error: (error, _) => AppErrorView(
          message: '课程库加载失败：$error',
          onRetry: () => ref.invalidate(courseLibraryProvider),
        ),
        data: (items) => _CourseLibraryBody(items: items),
      ),
    );
  }
}

class _CourseLibraryBody extends ConsumerStatefulWidget {
  const _CourseLibraryBody({required this.items});

  final List<CourseLibraryItemModel> items;

  @override
  ConsumerState<_CourseLibraryBody> createState() => _CourseLibraryBodyState();
}

class _CourseLibraryBodyState extends ConsumerState<_CourseLibraryBody> {
  final Set<String> _selectedCourseIds = <String>{};
  var _selectionMode = false;
  var _isDeleting = false;

  @override
  void didUpdateWidget(covariant _CourseLibraryBody oldWidget) {
    super.didUpdateWidget(oldWidget);
    final visibleIds = widget.items.map((item) => item.courseId).toSet();
    _selectedCourseIds.removeWhere((id) => !visibleIds.contains(id));
    if (_selectedCourseIds.isEmpty && widget.items.isEmpty) {
      _selectionMode = false;
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      children: [
        _LibraryTitleBar(
          totalCount: widget.items.length,
          selectedCount: _selectedCourseIds.length,
          selectionMode: _selectionMode,
          isDeleting: _isDeleting,
          onEnterDeleteMode: widget.items.isEmpty ? null : _enterDeleteMode,
          onCancelDeleteMode: _cancelDeleteMode,
          onDeleteSelected: _selectedCourseIds.isEmpty || _isDeleting
              ? null
              : _confirmAndDeleteSelected,
        ),
        const _LibraryFilterCard(),
        const SizedBox(height: 16),
        if (widget.items.isEmpty)
          const SectionCard(child: Text('暂无课程。'))
        else
          LayoutBuilder(
            builder: (context, constraints) {
              final width = constraints.maxWidth;
              final columns = _libraryColumnCount(width);
              final tileWidth = (width - (columns - 1) * 16) / columns;
              return Wrap(
                spacing: 16,
                runSpacing: 16,
                children: [
                  for (final item in widget.items)
                    SizedBox(
                      width: tileWidth,
                      child: _CourseTile(
                        item: item,
                        selectionMode: _selectionMode,
                        selected: _selectedCourseIds.contains(item.courseId),
                        onSelectionChanged: (selected) =>
                            _setCourseSelected(item.courseId, selected),
                      ),
                    ),
                ],
              );
            },
          ),
      ],
    );
  }

  void _enterDeleteMode() {
    setState(() {
      _selectionMode = true;
    });
  }

  void _cancelDeleteMode() {
    setState(() {
      _selectionMode = false;
      _selectedCourseIds.clear();
    });
  }

  void _setCourseSelected(String courseId, bool selected) {
    setState(() {
      _selectionMode = true;
      if (selected) {
        _selectedCourseIds.add(courseId);
      } else {
        _selectedCourseIds.remove(courseId);
      }
    });
  }

  Future<void> _confirmAndDeleteSelected() async {
    final count = _selectedCourseIds.length;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('删除课程'),
        content: Text('确定删除已选择的 $count 门课程吗？相关课时、资料和学习记录将按后端删除规则处理。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('删除'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) {
      return;
    }

    final ids = _selectedCourseIds.toList(growable: false);
    setState(() {
      _isDeleting = true;
    });
    try {
      final api = ref.read(courseLessonApiProvider);
      for (final id in ids) {
        await api.deleteCourse(id);
      }
      if (!mounted) {
        return;
      }
      setState(() {
        _selectionMode = false;
        _selectedCourseIds.clear();
      });
      ref.invalidate(courseLibraryProvider);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('已删除 $count 门课程')),
      );
    } catch (error) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('删除课程失败：$error')),
      );
    } finally {
      if (mounted) {
        setState(() {
          _isDeleting = false;
        });
      }
    }
  }
}

class _LibraryTitleBar extends StatelessWidget {
  const _LibraryTitleBar({
    required this.totalCount,
    required this.selectedCount,
    required this.selectionMode,
    required this.isDeleting,
    required this.onEnterDeleteMode,
    required this.onCancelDeleteMode,
    required this.onDeleteSelected,
  });

  final int totalCount;
  final int selectedCount;
  final bool selectionMode;
  final bool isDeleting;
  final VoidCallback? onEnterDeleteMode;
  final VoidCallback onCancelDeleteMode;
  final VoidCallback? onDeleteSelected;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 22),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final compact = constraints.maxWidth < 760;
          const title = Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _PrototypeTitleIcon(icon: Icons.library_books_outlined),
              SizedBox(width: 14),
              Expanded(
                child: Text(
                  '课程库',
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: AppTheme.ink,
                    fontSize: 42,
                    fontWeight: FontWeight.w800,
                    height: 1.02,
                    letterSpacing: 0,
                  ),
                ),
              ),
            ],
          );
          final actions = Wrap(
            spacing: 10,
            runSpacing: 10,
            alignment: compact ? WrapAlignment.start : WrapAlignment.end,
            children: selectionMode
                ? [
                    StatusPill(
                      label: '已选 $selectedCount / $totalCount',
                      color: selectedCount == 0
                          ? AppTheme.muted
                          : AppTheme.brandBlue,
                    ),
                    _LibraryActionButton(
                      label: '取消',
                      icon: Icons.close,
                      onPressed: isDeleting ? null : onCancelDeleteMode,
                    ),
                    _LibraryActionButton(
                      label: isDeleting ? '删除中' : '删除所选',
                      icon: Icons.delete_outline,
                      danger: true,
                      primary: true,
                      onPressed: onDeleteSelected,
                    ),
                  ]
                : [
                    _LibraryActionButton(
                      label: '删除课程',
                      icon: Icons.delete_outline,
                      danger: true,
                      onPressed: onEnterDeleteMode,
                    ),
                  ],
          );

          if (compact) {
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                title,
                const SizedBox(height: 16),
                actions,
              ],
            );
          }

          return Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Expanded(child: title),
              const SizedBox(width: 24),
              actions,
            ],
          );
        },
      ),
    );
  }
}

class _PrototypeTitleIcon extends StatelessWidget {
  const _PrototypeTitleIcon({required this.icon});

  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 46,
      height: 46,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
        boxShadow: AppTheme.shadowInsetLook,
      ),
      child: Icon(icon, color: AppTheme.brandBlue, size: 24),
    );
  }
}

class _LibraryActionButton extends StatelessWidget {
  const _LibraryActionButton({
    required this.label,
    required this.icon,
    required this.onPressed,
    this.danger = false,
    this.primary = false,
  });

  final String label;
  final IconData icon;
  final VoidCallback? onPressed;
  final bool danger;
  final bool primary;

  @override
  Widget build(BuildContext context) {
    final enabled = onPressed != null;
    final background = primary
        ? (danger ? AppTheme.danger : AppTheme.brandBlue)
        : AppTheme.surface;
    final foreground =
        primary ? Colors.white : (danger ? AppTheme.danger : AppTheme.ink);
    return Opacity(
      opacity: enabled ? 1 : 0.55,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: background,
          borderRadius: BorderRadius.circular(16),
          boxShadow: primary ? AppTheme.shadowAccent : AppTheme.shadowRaised,
        ),
        child: Material(
          color: Colors.transparent,
          borderRadius: BorderRadius.circular(16),
          child: InkWell(
            onTap: onPressed,
            borderRadius: BorderRadius.circular(16),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(icon, color: foreground, size: 18),
                  const SizedBox(width: 8),
                  Text(
                    label,
                    style: TextStyle(
                      color: foreground,
                      fontWeight: FontWeight.w800,
                    ),
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

int _libraryColumnCount(double width) {
  if (width >= 840) {
    return 4;
  }
  if (width >= 560) {
    return 2;
  }
  return 1;
}

class _LibraryFilterCard extends StatelessWidget {
  const _LibraryFilterCard();

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      padding: const EdgeInsets.all(16),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final compact = constraints.maxWidth < 760;
          const fields = [
            _InsetField(label: '搜索：数据结构'),
            _InsetField(label: '状态：全部课程'),
            _InsetField(label: '排序：最近学习优先'),
          ];
          if (compact) {
            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                for (final field in fields) ...[
                  field,
                  if (field != fields.last) const SizedBox(height: 10),
                ],
              ],
            );
          }
          return Row(
            children: [
              for (final field in fields) ...[
                Expanded(child: field),
                if (field != fields.last) const SizedBox(width: 12),
              ],
            ],
          );
        },
      ),
    );
  }
}

class _InsetField extends StatelessWidget {
  const _InsetField({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minHeight: 50),
      padding: const EdgeInsets.symmetric(horizontal: 16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
        boxShadow: AppTheme.shadowInsetLook,
      ),
      alignment: Alignment.centerLeft,
      child: Text(
        label,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: const TextStyle(
          color: AppTheme.muted,
          fontWeight: FontWeight.w800,
        ),
      ),
    );
  }
}

class _CourseTile extends ConsumerStatefulWidget {
  const _CourseTile({
    required this.item,
    required this.selectionMode,
    required this.selected,
    required this.onSelectionChanged,
  });

  final CourseLibraryItemModel item;
  final bool selectionMode;
  final bool selected;
  final ValueChanged<bool> onSelectionChanged;

  @override
  ConsumerState<_CourseTile> createState() => _CourseTileState();
}

class _CourseTileState extends ConsumerState<_CourseTile> {
  var _hovered = false;

  @override
  Widget build(BuildContext context) {
    final item = widget.item;
    final progressValue = item.overallMasteryScore?.clamp(0, 1).toDouble() ?? 0;
    final pillLabel =
        item.isCurrent ? '当前课程' : _statusLabel(item.learningStatus);
    final progressColor = progressValue < 0.34
        ? AppTheme.accentLight
        : item.isCurrent
            ? AppTheme.success
            : AppTheme.brandBlue;
    final elevated = _hovered || widget.selected;
    return MouseRegion(
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: AnimatedContainer(
        key: Key('course_tile_surface_${item.courseId}'),
        duration: const Duration(milliseconds: 180),
        curve: Curves.easeOutCubic,
        transform: Matrix4.translationValues(0, elevated ? -2 : 0, 0),
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.circular(28),
          boxShadow: elevated ? AppTheme.shadowSmall : AppTheme.shadowInsetLook,
        ),
        child: Stack(
          children: [
            GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTap: widget.selectionMode
                  ? () => widget.onSelectionChanged(!widget.selected)
                  : () => _openWorkbench(context),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  StatusPill(
                    label: pillLabel,
                    color:
                        item.isCurrent ? AppTheme.success : AppTheme.brandBlue,
                  ),
                  const SizedBox(height: 12),
                  Text(
                    item.title,
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
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      StatusPill(label: '${item.lessonCount} 课时'),
                    ],
                  ),
                  const SizedBox(height: 14),
                  ProgressRail(
                    value: progressValue,
                    color: progressColor,
                  ),
                  const SizedBox(height: 14),
                  _CourseTileButton(
                    label: widget.selectionMode
                        ? (widget.selected ? '已选择' : '选择课程')
                        : '继续学习',
                    icon: widget.selectionMode
                        ? (widget.selected
                            ? Icons.check_rounded
                            : Icons.check_box_outline_blank)
                        : Icons.play_arrow_rounded,
                    onPressed: widget.selectionMode
                        ? () => widget.onSelectionChanged(!widget.selected)
                        : () => _continueLearning(context),
                  ),
                ],
              ),
            ),
            if (widget.selectionMode)
              Positioned(
                right: 0,
                top: 0,
                child: _SelectionBadge(selected: widget.selected),
              ),
          ],
        ),
      ),
    );
  }

  void _continueLearning(BuildContext context) {
    final item = widget.item;
    ref.read(courseFlowProvider.notifier).startCourse(item.courseId);
    final lessonId = item.currentLessonId;
    if (lessonId == null) {
      _go(context, '/courses/${item.courseId}');
      return;
    }
    ref.read(activeLessonProvider.notifier).state = LessonResumeTarget(
      courseId: item.courseId,
      lessonId: lessonId,
    );
    _go(context, '/courses/${item.courseId}/lessons/$lessonId/handout');
  }

  void _openWorkbench(BuildContext context) {
    final item = widget.item;
    ref.read(courseFlowProvider.notifier).startCourse(item.courseId);
    _go(context, '/courses/${item.courseId}');
  }

  void _go(BuildContext context, String path) {
    try {
      context.go(path);
    } catch (_) {
      // Widget tests can mount this page without a router.
    }
  }
}

class _CourseTileButton extends StatelessWidget {
  const _CourseTileButton({
    required this.label,
    required this.icon,
    required this.onPressed,
  });

  final String label;
  final IconData icon;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerLeft,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: AppTheme.brandBlue,
          borderRadius: BorderRadius.circular(16),
          boxShadow: AppTheme.shadowAccent,
        ),
        child: Material(
          color: Colors.transparent,
          borderRadius: BorderRadius.circular(16),
          child: InkWell(
            onTap: onPressed,
            borderRadius: BorderRadius.circular(16),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(icon, color: Colors.white, size: 18),
                  const SizedBox(width: 8),
                  Text(
                    label,
                    style: const TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(width: 8),
                  const Icon(
                    Icons.chevron_right_rounded,
                    color: Colors.white,
                    size: 18,
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

class _SelectionBadge extends StatelessWidget {
  const _SelectionBadge({required this.selected});

  final bool selected;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 34,
      height: 34,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: selected ? AppTheme.brandBlue : AppTheme.surface,
        borderRadius: BorderRadius.circular(14),
        boxShadow: selected ? AppTheme.shadowAccent : AppTheme.shadowInsetLook,
      ),
      child: Icon(
        selected ? Icons.check_rounded : Icons.check_box_outline_blank,
        color: selected ? Colors.white : AppTheme.muted,
        size: 18,
      ),
    );
  }
}

String _statusLabel(String status) {
  return switch (status) {
    'learning_ready' => '可继续学习',
    'draft' => '草稿',
    'completed' => '已完成',
    'archived' => '已归档',
    _ => status,
  };
}
