import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/theme/app_theme.dart';
import '../../core/widgets/app_error_view.dart';
import '../../core/widgets/app_loading_view.dart';
import '../../core/widgets/app_scaffold.dart';
import '../../core/widgets/knowlink_widgets.dart';
import '../../shared/models/handout_models.dart';
import '../../shared/models/handout_state.dart';
import '../../shared/providers/course_flow_providers.dart';
import '../../shared/providers/handout_provider.dart';

class HandoutPage extends ConsumerStatefulWidget {
  const HandoutPage({
    required this.courseId,
    super.key,
  });

  final String courseId;

  @override
  ConsumerState<HandoutPage> createState() => _HandoutPageState();
}

class _HandoutPageState extends ConsumerState<HandoutPage> {
  final _questionController = TextEditingController();
  String? _lastCourseId;

  @override
  void initState() {
    super.initState();
    _questionController.addListener(_onQuestionChanged);
    _scheduleLoad();
  }

  @override
  void didUpdateWidget(covariant HandoutPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.courseId != widget.courseId) {
      _scheduleLoad();
    }
  }

  @override
  void dispose() {
    _questionController.removeListener(_onQuestionChanged);
    _questionController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(handoutProvider);
    final player = ref.watch(playerStateProvider);
    final notifier = ref.read(handoutProvider.notifier);
    final highlighted = state.highlightedChildFor(player.positionSec);
    final selectedChild = state.selectedOutlineChild;
    final selectedBlock = state.selectedBlock;

    return AppScaffold(
      title: '个性化互动讲义',
      activeTab: KnowLinkTab.handout,
      courseId: widget.courseId,
      body: _HandoutWorkspace(
        courseId: widget.courseId,
        state: state,
        player: player,
        highlightedChild: highlighted,
        selectedBlockId: selectedChild?.blockId,
        selectedBlock: selectedBlock,
        questionController: _questionController,
        onTogglePlay: () {
          ref.read(playerStateProvider.notifier).state = player.copyWith(
            isPlaying: !player.isPlaying,
          );
        },
        onSeek: (delta) {
          final next =
              (player.positionSec + delta).clamp(0, 24 * 60 * 60).toInt();
          ref.read(playerStateProvider.notifier).state = player.copyWith(
            positionSec: next,
          );
          notifier.syncHighlightedBlock(next);
          notifier.syncCurrentBlockFromPosition(
            courseId: widget.courseId,
            positionSec: next,
          );
        },
        onSelectChild: notifier.selectOutlineChild,
        onRefresh: () => notifier.refreshData(widget.courseId),
        onGenerate: () => notifier.generateAndPoll(widget.courseId),
        onGenerateBlock: selectedChild == null
            ? null
            : () => notifier.generateBlock(
                  selectedChild.blockId,
                  courseId: widget.courseId,
                ),
        onCitationTap: selectedChild == null
            ? null
            : (citation) => notifier.requestJumpTarget(
                  selectedChild.blockId,
                  citation: citation,
                ),
        onSubmitQuestion: () async {
          final text = _questionController.text;
          await notifier.submitQuestion(
            courseId: widget.courseId,
            question: text,
          );
          if (mounted &&
              ref.read(handoutProvider).qaSubmit.valueOrNull != null) {
            _questionController.clear();
          }
        },
      ),
    );
  }

  void _scheduleLoad() {
    if (_lastCourseId == widget.courseId) {
      return;
    }
    _lastCourseId = widget.courseId;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) {
        return;
      }
      ref.read(handoutProvider.notifier).load(widget.courseId);
    });
  }

  void _onQuestionChanged() {
    if (mounted) {
      setState(() {});
    }
  }
}

class _HandoutWorkspace extends StatelessWidget {
  const _HandoutWorkspace({
    required this.courseId,
    required this.state,
    required this.player,
    required this.highlightedChild,
    required this.selectedBlockId,
    required this.selectedBlock,
    required this.questionController,
    required this.onTogglePlay,
    required this.onSeek,
    required this.onSelectChild,
    required this.onRefresh,
    required this.onGenerate,
    required this.onGenerateBlock,
    required this.onCitationTap,
    required this.onSubmitQuestion,
  });

  final String courseId;
  final HandoutState state;
  final PlayerState player;
  final HandoutOutlineChildModel? highlightedChild;
  final int? selectedBlockId;
  final HandoutBlockModel? selectedBlock;
  final TextEditingController questionController;
  final VoidCallback onTogglePlay;
  final ValueChanged<int> onSeek;
  final ValueChanged<HandoutOutlineChildModel> onSelectChild;
  final VoidCallback onRefresh;
  final VoidCallback onGenerate;
  final VoidCallback? onGenerateBlock;
  final ValueChanged<CitationModel>? onCitationTap;
  final VoidCallback onSubmitQuestion;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        if (constraints.maxWidth < 1120) {
          return ListView(
            children: [
              _OutlinePanel(
                courseId: courseId,
                state: state,
                highlightedBlockId: highlightedChild?.blockId,
                selectedBlockId: selectedBlockId,
                onSelect: onSelectChild,
                onRefresh: onRefresh,
                onGenerate: onGenerate,
              ),
              const SizedBox(height: 16),
              _LearningCenterPanel(
                courseId: courseId,
                state: state,
                player: player,
                highlightedChild: highlightedChild,
                selectedBlock: selectedBlock,
                onTogglePlay: onTogglePlay,
                onSeek: onSeek,
                onGenerateBlock: onGenerateBlock,
                onCitationTap: onCitationTap,
              ),
              const SizedBox(height: 16),
              _RightStudyPanel(
                state: state,
                selectedBlock: selectedBlock,
                controller: questionController,
                onCitationTap: onCitationTap,
                onSubmit: onSubmitQuestion,
              ),
            ],
          );
        }

        return Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            SizedBox(
              width: 294,
              child: _OutlinePanel(
                courseId: courseId,
                state: state,
                highlightedBlockId: highlightedChild?.blockId,
                selectedBlockId: selectedBlockId,
                onSelect: onSelectChild,
                onRefresh: onRefresh,
                onGenerate: onGenerate,
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: _LearningCenterPanel(
                courseId: courseId,
                state: state,
                player: player,
                highlightedChild: highlightedChild,
                selectedBlock: selectedBlock,
                onTogglePlay: onTogglePlay,
                onSeek: onSeek,
                onGenerateBlock: onGenerateBlock,
                onCitationTap: onCitationTap,
              ),
            ),
            const SizedBox(width: 16),
            SizedBox(
              width: 352,
              child: _RightStudyPanel(
                state: state,
                selectedBlock: selectedBlock,
                controller: questionController,
                onCitationTap: onCitationTap,
                onSubmit: onSubmitQuestion,
              ),
            ),
          ],
        );
      },
    );
  }
}

class _OutlinePanel extends StatelessWidget {
  const _OutlinePanel({
    required this.courseId,
    required this.state,
    required this.highlightedBlockId,
    required this.selectedBlockId,
    required this.onSelect,
    required this.onRefresh,
    required this.onGenerate,
  });

  final String courseId;
  final HandoutState state;
  final int? highlightedBlockId;
  final int? selectedBlockId;
  final ValueChanged<HandoutOutlineChildModel> onSelect;
  final VoidCallback onRefresh;
  final VoidCallback onGenerate;

  @override
  Widget build(BuildContext context) {
    final latest = state.latest.valueOrNull;
    final outline = state.outline.valueOrNull;
    final status = state.versionStatus.valueOrNull;
    final blockList = Padding(
      padding: const EdgeInsets.all(12),
      child: _BlockList(
        state: state,
        outline: outline,
        highlightedBlockId: highlightedBlockId,
        selectedBlockId: selectedBlockId,
        onSelect: onSelect,
      ),
    );

    return SectionCard(
      padding: EdgeInsets.zero,
      child: LayoutBuilder(
        builder: (context, constraints) {
          final hasBoundedHeight = constraints.hasBoundedHeight;
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            mainAxisSize:
                hasBoundedHeight ? MainAxisSize.max : MainAxisSize.min,
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(18, 16, 12, 14),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(
                        '讲义结构',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                    ),
                    IconButton(
                      tooltip: '刷新讲义',
                      onPressed: state.isLoading ? null : onRefresh,
                      icon: const Icon(Icons.refresh),
                    ),
                  ],
                ),
              ),
              const Divider(height: 1),
              Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      latest?.title ?? '课程 $courseId 的讲义',
                      style: const TextStyle(
                        color: AppTheme.ink,
                        fontWeight: FontWeight.w800,
                        fontSize: 15,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      latest?.summary ?? '读取最新讲义，并根据播放位置同步知识点。',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                    if (status != null) ...[
                      const SizedBox(height: 12),
                      _MiniProgress(
                        ready: status.readyBlocks,
                        total: status.totalBlocks,
                      ),
                    ],
                    if (outline != null &&
                        (outline.outlineUsedFallback ||
                            outline.outlineIssues.isNotEmpty)) ...[
                      const SizedBox(height: 12),
                      _OutlineIssueNotice(outline: outline),
                    ],
                    const SizedBox(height: 12),
                    OutlinedButton.icon(
                      onPressed: state.isGenerating ? null : onGenerate,
                      icon: const Icon(Icons.auto_awesome),
                      label: Text(state.isGenerating ? '生成中' : '重新生成讲义'),
                    ),
                  ],
                ),
              ),
              const Divider(height: 1),
              if (hasBoundedHeight)
                Expanded(child: blockList)
              else
                SizedBox(height: 480, child: blockList),
            ],
          );
        },
      ),
    );
  }
}

class _MiniProgress extends StatelessWidget {
  const _MiniProgress({
    required this.ready,
    required this.total,
  });

  final int ready;
  final int total;

  @override
  Widget build(BuildContext context) {
    final value = total == 0 ? 0.0 : ready / total;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Icon(Icons.check_circle_outline, size: 16),
            const SizedBox(width: 6),
            Text(
              '已掌握 ${(value * 100).round()}%',
              style: const TextStyle(
                color: Color(0xFF16A34A),
                fontWeight: FontWeight.w800,
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        ProgressRail(value: value, color: const Color(0xFF22C55E)),
      ],
    );
  }
}

class _OutlineIssueNotice extends StatelessWidget {
  const _OutlineIssueNotice({
    required this.outline,
  });

  final HandoutOutlineModel outline;

  @override
  Widget build(BuildContext context) {
    final issueText = [
      if (outline.outlineUsedFallback) '目录已使用降级结构展示。',
      ...outline.outlineIssues,
    ].join('；');
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: const Color(0xFFFFFBEB),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xFFFDE68A)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(
            Icons.info_outline,
            size: 18,
            color: Color(0xFFB45309),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              issueText,
              style: const TextStyle(
                color: Color(0xFF92400E),
                fontSize: 12,
                fontWeight: FontWeight.w700,
                height: 1.35,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _BlockList extends StatelessWidget {
  const _BlockList({
    required this.state,
    required this.outline,
    required this.highlightedBlockId,
    required this.selectedBlockId,
    required this.onSelect,
  });

  final HandoutState state;
  final HandoutOutlineModel? outline;
  final int? highlightedBlockId;
  final int? selectedBlockId;
  final ValueChanged<HandoutOutlineChildModel> onSelect;

  @override
  Widget build(BuildContext context) {
    if (state.outline.isLoading) {
      return const AppLoadingView(label: '正在读取讲义目录');
    }
    if (state.outline.hasError) {
      return AppErrorView(message: '讲义目录暂不可用：${state.outline.error}');
    }
    final sections = outline?.items ?? const [];
    if (sections.isEmpty) {
      return const Text('暂无讲义目录。');
    }

    return ListView.builder(
      itemCount: sections.length,
      itemBuilder: (context, index) {
        final section = sections[index];
        return Padding(
          padding:
              EdgeInsets.only(bottom: index == sections.length - 1 ? 0 : 14),
          child: _OutlineSectionGroup(
            section: section,
            highlightedBlockId: highlightedBlockId,
            selectedBlockId: selectedBlockId,
            onSelect: onSelect,
          ),
        );
      },
    );
  }
}

class _OutlineSectionGroup extends StatelessWidget {
  const _OutlineSectionGroup({
    required this.section,
    required this.highlightedBlockId,
    required this.selectedBlockId,
    required this.onSelect,
  });

  final HandoutOutlineSectionModel section;
  final int? highlightedBlockId;
  final int? selectedBlockId;
  final ValueChanged<HandoutOutlineChildModel> onSelect;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _SectionHeader(section: section),
        const SizedBox(height: 6),
        if (section.children.isEmpty)
          const Padding(
            padding: EdgeInsets.only(left: 10, bottom: 4),
            child: Text(
              '该分组暂无二级目录。',
              style: TextStyle(
                color: AppTheme.muted,
                fontSize: 12,
                fontWeight: FontWeight.w700,
              ),
            ),
          )
        else
          for (final child in section.children)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: _BlockTile(
                child: child,
                isHighlighted: child.blockId == highlightedBlockId,
                isSelected: child.blockId == selectedBlockId,
                onTap: () => onSelect(child),
              ),
            ),
      ],
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({
    required this.section,
  });

  final HandoutOutlineSectionModel section;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(10, 8, 10, 8),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppTheme.line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            section.title,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              color: AppTheme.ink,
              fontWeight: FontWeight.w900,
              fontSize: 13,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            [
              '${section.children.length} 个二级目录',
              '${_formatSec(section.startSec)}-${_formatSec(section.endSec)}',
            ].join(' · '),
            style: const TextStyle(
              color: AppTheme.muted,
              fontSize: 12,
              fontWeight: FontWeight.w700,
            ),
          ),
          if (section.summary.isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(
              section.summary,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ],
      ),
    );
  }
}

class _BlockTile extends StatelessWidget {
  const _BlockTile({
    required this.child,
    required this.isHighlighted,
    required this.isSelected,
    required this.onTap,
  });

  final HandoutOutlineChildModel child;
  final bool isHighlighted;
  final bool isSelected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = isSelected
        ? AppTheme.brandBlue
        : isHighlighted
            ? const Color(0xFF7C3AED)
            : AppTheme.muted;

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Material(
        color: isSelected ? const Color(0xFFEFF6FF) : Colors.transparent,
        borderRadius: BorderRadius.circular(8),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(8),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
            child: Row(
              children: [
                Icon(
                  isSelected
                      ? Icons.radio_button_checked
                      : Icons.radio_button_unchecked,
                  color: color,
                  size: 16,
                ),
                const SizedBox(width: 9),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        child.title,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          color: color,
                          fontWeight:
                              isSelected ? FontWeight.w800 : FontWeight.w600,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Wrap(
                        spacing: 6,
                        runSpacing: 4,
                        children: [
                          Text(
                            _statusLabel(child.generationStatus),
                            style: TextStyle(
                              color: color,
                              fontSize: 11,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          Text(
                            '${_formatSec(child.startSec)}-${_formatSec(child.endSec)}',
                            style: const TextStyle(
                              color: AppTheme.muted,
                              fontSize: 11,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                          if (child.topicTags.isNotEmpty)
                            Text(
                              child.topicTags.take(2).join(' / '),
                              style: const TextStyle(
                                color: AppTheme.muted,
                                fontSize: 11,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _LearningCenterPanel extends StatelessWidget {
  const _LearningCenterPanel({
    required this.courseId,
    required this.state,
    required this.player,
    required this.highlightedChild,
    required this.selectedBlock,
    required this.onTogglePlay,
    required this.onSeek,
    required this.onGenerateBlock,
    required this.onCitationTap,
  });

  final String courseId;
  final HandoutState state;
  final PlayerState player;
  final HandoutOutlineChildModel? highlightedChild;
  final HandoutBlockModel? selectedBlock;
  final VoidCallback onTogglePlay;
  final ValueChanged<int> onSeek;
  final VoidCallback? onGenerateBlock;
  final ValueChanged<CitationModel>? onCitationTap;

  @override
  Widget build(BuildContext context) {
    final block = selectedBlock;
    final highlightedBlock = highlightedChild == null
        ? null
        : state.blockForId(highlightedChild!.blockId);
    return SectionCard(
      padding: const EdgeInsets.all(20),
      child: ListView(
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  '当前知识点：  ${block?.title ?? '等待同步'}',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
              ),
              const StatusPill(label: '学习模式'),
              const SizedBox(width: 12),
              StatusPill(
                label: '已掌握 ${_masteryFor(block)}%',
                color: const Color(0xFF16A34A),
              ),
            ],
          ),
          const SizedBox(height: 18),
          _VideoStage(
            courseId: courseId,
            block: highlightedBlock ?? block,
            player: player,
            onTogglePlay: onTogglePlay,
            onSeek: onSeek,
          ),
          const SizedBox(height: 18),
          _ContentPanel(
            state: state,
            block: block,
            onGenerateBlock: onGenerateBlock,
            onCitationTap: onCitationTap,
          ),
        ],
      ),
    );
  }

  int _masteryFor(HandoutBlockModel? block) {
    if (block == null) {
      return 0;
    }
    if (block.status == 'ready') {
      return 60;
    }
    if (block.status == 'generating') {
      return 35;
    }
    return 20;
  }
}

class _VideoStage extends StatelessWidget {
  const _VideoStage({
    required this.courseId,
    required this.block,
    required this.player,
    required this.onTogglePlay,
    required this.onSeek,
  });

  final String courseId;
  final HandoutBlockModel? block;
  final PlayerState player;
  final VoidCallback onTogglePlay;
  final ValueChanged<int> onSeek;

  @override
  Widget build(BuildContext context) {
    final block = this.block;
    final positionLabel = _formatSec(player.positionSec);
    final duration = block == null ? 12 * 60 + 48 : block.endSec;
    final value = duration == 0 ? 0.0 : player.positionSec / duration;

    return Container(
      height: 472,
      decoration: BoxDecoration(
        color: const Color(0xFF070B12),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Stack(
        children: [
          Positioned.fill(
            child: DecoratedBox(
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(8),
                gradient: const RadialGradient(
                  center: Alignment.topRight,
                  radius: 1.2,
                  colors: [Color(0xFF1E293B), Color(0xFF020617)],
                ),
              ),
            ),
          ),
          Positioned(
            left: 22,
            top: 22,
            right: 22,
            child: Text(
              block == null ? '等待讲义块同步播放位置' : block.title,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 24,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
          Positioned(
            left: 22,
            top: 76,
            width: 280,
            child: Text(
              block?.summary ?? 'AI 将根据当前视频片段同步讲义 block、来源引用与追问上下文。',
              style: const TextStyle(
                color: Colors.white,
                height: 1.8,
                fontSize: 16,
              ),
            ),
          ),
          Positioned(
            right: 22,
            top: 70,
            width: 360,
            bottom: 70,
            child: _VideoContextBoard(block: block),
          ),
          Positioned(
            left: 22,
            bottom: 68,
            child: Text(
              '课程 $courseId · $positionLabel',
              style: const TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          Positioned(
            left: 18,
            right: 18,
            bottom: 14,
            child: LayoutBuilder(
              builder: (context, constraints) {
                final compact = constraints.maxWidth < 520;
                return Row(
                  children: [
                    IconButton(
                      tooltip: player.isPlaying ? '暂停' : '播放',
                      onPressed: onTogglePlay,
                      color: Colors.white,
                      icon: Icon(
                        player.isPlaying ? Icons.pause : Icons.play_arrow,
                      ),
                    ),
                    Flexible(
                      child: Text(
                        '$positionLabel / ${_formatSec(duration)}',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(color: Colors.white),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      flex: compact ? 2 : 4,
                      child: ProgressRail(
                        value: value,
                        color: AppTheme.brandBlue,
                      ),
                    ),
                    if (!compact) ...[
                      const SizedBox(width: 10),
                      TextButton(
                        onPressed: () => onSeek(-30),
                        child: const Text(
                          '-30s',
                          style: TextStyle(color: Colors.white),
                        ),
                      ),
                    ],
                    TextButton(
                      onPressed: () => onSeek(30),
                      child: Text(
                        compact ? '+30' : '+30s',
                        style: const TextStyle(color: Colors.white),
                      ),
                    ),
                    if (!compact) ...[
                      const Icon(Icons.volume_up_outlined, color: Colors.white),
                      const SizedBox(width: 12),
                      const Icon(Icons.fullscreen, color: Colors.white),
                    ],
                  ],
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _VideoContextBoard extends StatelessWidget {
  const _VideoContextBoard({
    required this.block,
  });

  final HandoutBlockModel? block;

  @override
  Widget build(BuildContext context) {
    final block = this.block;
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.06),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
      ),
      child: block == null
          ? const Center(
              child: Text(
                '等待播放位置同步到讲义块',
                style: TextStyle(color: Colors.white70),
              ),
            )
          : Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _statusLabel(block.status),
                  style: const TextStyle(
                    color: Color(0xFFA7F3D0),
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  block.summary.isEmpty ? block.title : block.summary,
                  maxLines: 7,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: Colors.white,
                    height: 1.55,
                    fontSize: 14,
                  ),
                ),
                const Spacer(),
                Text(
                  '${_formatSec(block.startSec)}-${_formatSec(block.endSec)}',
                  style: const TextStyle(
                    color: Colors.white70,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
    );
  }
}

class _ContentPanel extends StatelessWidget {
  const _ContentPanel({
    required this.state,
    required this.block,
    required this.onGenerateBlock,
    required this.onCitationTap,
  });

  final HandoutState state;
  final HandoutBlockModel? block;
  final VoidCallback? onGenerateBlock;
  final ValueChanged<CitationModel>? onCitationTap;

  @override
  Widget build(BuildContext context) {
    final block = this.block;
    return Container(
      decoration: BoxDecoration(
        border: Border.all(color: AppTheme.line),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const _TabHeader(),
          Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  '知识点解析',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 12),
                if (block == null)
                  const Text('选择讲义块后展示正文和引用。')
                else ...[
                  _BlockContent(
                    block: block,
                    isGeneratingBlock: state.blockGenerateRequest.isLoading,
                    onGenerateBlock: onGenerateBlock,
                  ),
                  if (state.blockGenerateRequest.hasError) ...[
                    const SizedBox(height: 12),
                    AppErrorView(
                      message: '生成当前块失败：${state.blockGenerateRequest.error}',
                    ),
                  ],
                  const SizedBox(height: 14),
                  _CitationList(
                    citations: block.citations,
                    onTap: onCitationTap,
                  ),
                  const SizedBox(height: 12),
                  _JumpTargetView(state: state),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _TabHeader extends StatelessWidget {
  const _TabHeader();

  @override
  Widget build(BuildContext context) {
    const tabs = ['知识点解析', '例题讲解', '关联题', '扩展阅读'];
    return Container(
      height: 54,
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: AppTheme.line)),
      ),
      child: Row(
        children: [
          for (final tab in tabs)
            Expanded(
              child: Container(
                alignment: Alignment.center,
                decoration: tab == tabs.first
                    ? const BoxDecoration(
                        border: Border(
                          bottom: BorderSide(
                            color: AppTheme.brandBlue,
                            width: 3,
                          ),
                        ),
                      )
                    : null,
                child: Text(
                  tab,
                  style: TextStyle(
                    color:
                        tab == tabs.first ? AppTheme.brandBlue : AppTheme.ink,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _BlockContent extends StatelessWidget {
  const _BlockContent({
    required this.block,
    required this.isGeneratingBlock,
    required this.onGenerateBlock,
  });

  final HandoutBlockModel block;
  final bool isGeneratingBlock;
  final VoidCallback? onGenerateBlock;

  @override
  Widget build(BuildContext context) {
    if (block.status == 'failed') {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text('该讲义块生成失败，可重试生成。'),
          const SizedBox(height: 10),
          OutlinedButton.icon(
            onPressed: isGeneratingBlock ? null : onGenerateBlock,
            icon: const Icon(Icons.refresh),
            label: const Text('重新生成当前块'),
          ),
        ],
      );
    }
    if (block.status != 'ready') {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            '该讲义块状态为${_statusLabel(block.status)}，正文生成后会展示结构化讲义内容。',
          ),
          const SizedBox(height: 10),
          OutlinedButton.icon(
            onPressed: isGeneratingBlock ? null : onGenerateBlock,
            icon: const Icon(Icons.auto_awesome),
            label: Text(isGeneratingBlock ? '正在生成当前块' : '生成当前块'),
          ),
        ],
      );
    }
    final content = block.contentMd;
    if (content == null || content.trim().isEmpty) {
      return const Text('该讲义块暂无正文。');
    }
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppTheme.line),
      ),
      child: MarkdownBody(
        data: content,
        selectable: true,
        styleSheet: MarkdownStyleSheet.fromTheme(Theme.of(context)).copyWith(
          p: const TextStyle(
            color: AppTheme.ink,
            height: 1.5,
            fontSize: 14,
          ),
          h1: Theme.of(context).textTheme.titleLarge?.copyWith(
                color: AppTheme.ink,
                fontWeight: FontWeight.w900,
              ),
          h2: Theme.of(context).textTheme.titleMedium?.copyWith(
                color: AppTheme.ink,
                fontWeight: FontWeight.w900,
              ),
          h3: Theme.of(context).textTheme.titleSmall?.copyWith(
                color: AppTheme.ink,
                fontWeight: FontWeight.w900,
              ),
          listBullet: const TextStyle(
            color: AppTheme.ink,
            height: 1.45,
          ),
          blockquoteDecoration: const BoxDecoration(
            color: Color(0xFFEFF6FF),
            border: Border(
              left: BorderSide(color: AppTheme.brandBlue, width: 3),
            ),
          ),
        ),
      ),
    );
  }
}

class _CitationList extends StatelessWidget {
  const _CitationList({
    required this.citations,
    required this.onTap,
  });

  final List<CitationModel> citations;
  final ValueChanged<CitationModel>? onTap;

  @override
  Widget build(BuildContext context) {
    if (citations.isEmpty) {
      return const Text('暂无引用。');
    }
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        border: Border.all(color: AppTheme.line),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text('来源引用', style: Theme.of(context).textTheme.titleSmall),
              const Spacer(),
              const Text(
                '点击引用定位',
                style: TextStyle(
                  color: AppTheme.muted,
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: citations
                .map(
                  (citation) => SourceChip(
                    icon: _citationIcon(citation),
                    label: _citationLabel(citation),
                    onTap: onTap == null ? null : () => onTap!(citation),
                  ),
                )
                .toList(),
          ),
        ],
      ),
    );
  }
}

class _JumpTargetView extends StatelessWidget {
  const _JumpTargetView({
    required this.state,
  });

  final HandoutState state;

  @override
  Widget build(BuildContext context) {
    final citation = state.selectedCitation;
    final citationLine = citation == null
        ? null
        : Row(
            children: [
              const Icon(Icons.link, size: 18, color: AppTheme.brandBlue),
              const SizedBox(width: 8),
              Expanded(child: Text('引用位置：${_citationLabel(citation)}')),
            ],
          );

    if (state.jumpTarget.isLoading) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (citationLine != null) ...[
            citationLine,
            const SizedBox(height: 8),
          ],
          const LinearProgressIndicator(),
        ],
      );
    }
    if (state.jumpTarget.hasError) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (citationLine != null) ...[
            citationLine,
            const SizedBox(height: 8),
          ],
          Text('跳转信息暂不可用：${state.jumpTarget.error}'),
        ],
      );
    }
    final target = state.jumpTarget.valueOrNull;
    if (target == null) {
      return const Text('点击讲义块或引用后展示后端返回的跳转位置。');
    }
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFFEFF6FF),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xFFBFDBFE)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (citationLine != null) ...[
            citationLine,
            const SizedBox(height: 8),
          ],
          Row(
            children: [
              const Icon(Icons.near_me_outlined, size: 18),
              const SizedBox(width: 8),
              Expanded(child: Text('跳转位置：${target.displayText}')),
            ],
          ),
        ],
      ),
    );
  }
}

class _RightStudyPanel extends StatelessWidget {
  const _RightStudyPanel({
    required this.state,
    required this.selectedBlock,
    required this.controller,
    required this.onCitationTap,
    required this.onSubmit,
  });

  final HandoutState state;
  final HandoutBlockModel? selectedBlock;
  final TextEditingController controller;
  final ValueChanged<CitationModel>? onCitationTap;
  final VoidCallback onSubmit;

  @override
  Widget build(BuildContext context) {
    return ListView(
      children: [
        _QaPanel(
          state: state,
          selectedBlock: selectedBlock,
          controller: controller,
          onCitationTap: onCitationTap,
          onSubmit: onSubmit,
        ),
        const SizedBox(height: 16),
        _RelatedStudyPanel(selectedBlock: selectedBlock),
      ],
    );
  }
}

class _QaPanel extends StatelessWidget {
  const _QaPanel({
    required this.state,
    required this.selectedBlock,
    required this.controller,
    required this.onCitationTap,
    required this.onSubmit,
  });

  final HandoutState state;
  final HandoutBlockModel? selectedBlock;
  final TextEditingController controller;
  final ValueChanged<CitationModel>? onCitationTap;
  final VoidCallback onSubmit;

  @override
  Widget build(BuildContext context) {
    final selectedBlock = this.selectedBlock;
    final canSubmit = selectedBlock != null &&
        !state.isSubmittingQuestion &&
        controller.text.trim().isNotEmpty;

    return SectionCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              const SoftIcon(icon: Icons.smart_toy_outlined, size: 34),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  'AI 思考问答（当前块 QA）',
                  style: Theme.of(context).textTheme.titleSmall,
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          if (state.qaSubmit.hasError) ...[
            AppErrorView(message: '提交 QA 失败：${state.qaSubmit.error}'),
            const SizedBox(height: 12),
          ],
          if (state.selectedBlockQaMessages.isEmpty)
            _QaEmptyState(
              selectedBlock: selectedBlock,
            )
          else
            ...state.selectedBlockQaMessages.reversed.map(
              (message) => _QaAnswerCard(
                message: message,
                onCitationTap: onCitationTap,
              ),
            ),
          const SizedBox(height: 12),
          TextField(
            controller: controller,
            enabled: selectedBlock != null && !state.isSubmittingQuestion,
            minLines: 1,
            maxLines: 3,
            decoration: InputDecoration(
              hintText: selectedBlock == null ? '请先选择讲义块' : '继续提问...',
              suffixIcon: IconButton(
                tooltip: '发送',
                onPressed: canSubmit ? onSubmit : null,
                icon: const Icon(Icons.send_outlined),
              ),
            ),
          ),
          const SizedBox(height: 10),
          FilledButton.icon(
            onPressed: canSubmit ? onSubmit : null,
            icon: const Icon(Icons.send),
            label: Text(state.isSubmittingQuestion ? '正在提交' : '提交问题'),
          ),
        ],
      ),
    );
  }
}

class _QaEmptyState extends StatelessWidget {
  const _QaEmptyState({
    required this.selectedBlock,
  });

  final HandoutBlockModel? selectedBlock;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        border: Border.all(color: AppTheme.line),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        selectedBlock == null ? '请先选择讲义块。' : '当前块还没有问答记录。',
        style: const TextStyle(
          color: AppTheme.muted,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

class _QaAnswerCard extends StatelessWidget {
  const _QaAnswerCard({
    required this.message,
    required this.onCitationTap,
  });

  final QaMessageModel message;
  final ValueChanged<CitationModel>? onCitationTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: DecoratedBox(
        decoration: BoxDecoration(
          border: Border.all(color: AppTheme.line),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  const Icon(Icons.smart_toy_outlined, size: 18),
                  const SizedBox(width: 8),
                  Expanded(child: Text('回答 #${message.messageId}')),
                ],
              ),
              const SizedBox(height: 8),
              Text(message.answerMd),
              const SizedBox(height: 8),
              _CitationList(
                citations: message.citations,
                onTap: onCitationTap,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _RelatedStudyPanel extends StatelessWidget {
  const _RelatedStudyPanel({
    required this.selectedBlock,
  });

  final HandoutBlockModel? selectedBlock;

  @override
  Widget build(BuildContext context) {
    final title = selectedBlock?.title ?? '相关知识点';
    return SectionCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  '延伸学习',
                  style: Theme.of(context).textTheme.titleSmall,
                ),
              ),
              StatusPill(
                label: selectedBlock == null ? '待选择' : '当前块',
                color: selectedBlock == null
                    ? const Color(0xFF64748B)
                    : AppTheme.brandBlue,
              ),
            ],
          ),
          const SizedBox(height: 12),
          _RelatedItem(
            icon: Icons.link,
            title: title == '相关知识点' ? '相邻知识点' : title,
            subtitle: '结合当前讲义块的上下文继续学习。',
          ),
          const SizedBox(height: 10),
          const _RelatedItem(
            icon: Icons.assignment_outlined,
            title: '来源回看',
            subtitle: '回到对应视频或资料位置核对依据。',
            color: Color(0xFF22C55E),
          ),
          const SizedBox(height: 10),
          const _RelatedItem(
            icon: Icons.quiz_outlined,
            title: '错题巩固',
            subtitle: '用当前知识点生成针对性练习。',
            color: Color(0xFF8B5CF6),
          ),
        ],
      ),
    );
  }
}

class _RelatedItem extends StatelessWidget {
  const _RelatedItem({
    required this.icon,
    required this.title,
    required this.subtitle,
    this.color = AppTheme.brandBlue,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        border: Border.all(color: AppTheme.line),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          SoftIcon(icon: icon, color: color, size: 42),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    color: AppTheme.ink,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 4),
                Text(subtitle, style: Theme.of(context).textTheme.bodySmall),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

IconData _citationIcon(CitationModel citation) {
  if (citation.startSec != null) {
    return Icons.play_circle_outline;
  }
  if (citation.slideNo != null) {
    return Icons.description_outlined;
  }
  if (citation.pageNo != null) {
    return Icons.picture_as_pdf_outlined;
  }
  return Icons.link;
}

String _formatSec(int seconds) {
  final minutes = seconds ~/ 60;
  final rest = seconds % 60;
  return '$minutes:${rest.toString().padLeft(2, '0')}';
}

String _citationLabel(CitationModel citation) {
  if (citation.refLabel == citation.locatorText) {
    return citation.refLabel;
  }
  return '${citation.refLabel} · ${citation.locatorText}';
}

String _statusLabel(String status) {
  return switch (status) {
    'ready' => '已生成',
    'pending' => '待生成',
    'generating' => '生成中',
    'failed' => '生成失败',
    'outline_ready' => '目录已生成',
    'partial_success' => '部分成功',
    'draft' => '草稿',
    'superseded' => '已被替换',
    _ => '状态待确认',
  };
}
