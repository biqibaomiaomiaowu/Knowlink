import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/theme/app_theme.dart';
import '../../core/widgets/app_scaffold.dart';
import '../../core/widgets/knowlink_widgets.dart';
import '../../shared/models/soft_ui_models.dart';
import '../../shared/providers/soft_ui_provider.dart';

class QuizPage extends ConsumerStatefulWidget {
  const QuizPage({
    this.courseId,
    this.quizId,
    super.key,
  });

  final String? courseId;
  final String? quizId;

  @override
  ConsumerState<QuizPage> createState() => _QuizPageState();
}

class _QuizPageState extends ConsumerState<QuizPage> {
  var _activeTestId = 'test-1';
  var _questionCount = 15;
  var _difficulty = '中等';

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(softUiProvider);
    final tests = state.tests;
    final active = tests.firstWhere(
      (test) => test.id == _activeTestId,
      orElse: () => tests.first,
    );
    final courseId = widget.courseId ?? state.activeCourseId;
    return AppScaffold(
      title: '测试中心',
      activeTab: KnowLinkTab.test,
      courseId: courseId,
      lessonId: state.activeLessonId,
      body: ListView(
        children: [
          PageTitle(
            title: '测试中心',
            subtitle: '切换历史测试，调整题量和难度后生成新的阶段测验。',
            icon: Icons.fact_check_outlined,
            actions: [
              SoftButton(
                label: '重新生成测验',
                icon: Icons.refresh_rounded,
                primary: true,
                onPressed: () => _showQuizRegenerateModal(),
              ),
            ],
          ),
          LayoutBuilder(
            builder: (context, constraints) {
              final wide = constraints.maxWidth >= 1060;
              final history = _HistoryPanel(
                tests: tests,
                activeTestId: active.id,
                onSelect: (id) => setState(() => _activeTestId = id),
              );
              final paper = _PaperPanel(test: active);
              if (!wide) {
                return Column(
                  children: [
                    _GeneratorPanel(
                      count: _questionCount,
                      difficulty: _difficulty,
                      onCountChanged: (value) =>
                          setState(() => _questionCount = value),
                      onDifficultyChanged: (value) =>
                          setState(() => _difficulty = value),
                      onGenerate: _generate,
                    ),
                    const SizedBox(height: 16),
                    history,
                    const SizedBox(height: 16),
                    paper,
                  ],
                );
              }
              return Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    flex: 4,
                    child: Column(
                      children: [
                        _GeneratorPanel(
                          count: _questionCount,
                          difficulty: _difficulty,
                          onCountChanged: (value) =>
                              setState(() => _questionCount = value),
                          onDifficultyChanged: (value) =>
                              setState(() => _difficulty = value),
                          onGenerate: _generate,
                        ),
                        const SizedBox(height: 16),
                        history,
                      ],
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(flex: 6, child: paper),
                ],
              );
            },
          ),
        ],
      ),
    );
  }

  void _generate() {
    final test = ref.read(softUiProvider.notifier).generateTest(
          questionCount: _questionCount,
          difficulty: _difficulty,
        );
    setState(() => _activeTestId = test.id);
  }

  Future<void> _showQuizRegenerateModal() async {
    var count = _questionCount;
    var difficulty = _difficulty;
    final generated = await showDialog<bool>(
      context: context,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              backgroundColor: AppTheme.surface,
              surfaceTintColor: AppTheme.surface,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(32),
              ),
              title: const Text('重新生成综合测验'),
              content: SizedBox(
                width: 430,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('题目数量'),
                    const SizedBox(height: 8),
                    Slider(
                      value: count.toDouble(),
                      min: 5,
                      max: 20,
                      divisions: 15,
                      label: '$count',
                      onChanged: (value) =>
                          setDialogState(() => count = value.round()),
                    ),
                    const SizedBox(height: 12),
                    const Text('题目难度'),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 8,
                      children: ['基础', '中等', '困难'].map((item) {
                        final active = item == difficulty;
                        return ChoiceChip(
                          label: Text(item),
                          selected: active,
                          onSelected: (_) =>
                              setDialogState(() => difficulty = item),
                        );
                      }).toList(),
                    ),
                  ],
                ),
              ),
              actions: [
                SoftButton(
                  label: '取消',
                  onPressed: () => Navigator.of(context).pop(false),
                ),
                SoftButton(
                  label: '生成测验',
                  primary: true,
                  onPressed: () => Navigator.of(context).pop(true),
                ),
              ],
            );
          },
        );
      },
    );
    if (generated == true) {
      setState(() {
        _questionCount = count;
        _difficulty = difficulty;
      });
      _generate();
    }
  }
}

class _GeneratorPanel extends StatelessWidget {
  const _GeneratorPanel({
    required this.count,
    required this.difficulty,
    required this.onCountChanged,
    required this.onDifficultyChanged,
    required this.onGenerate,
  });

  final int count;
  final String difficulty;
  final ValueChanged<int> onCountChanged;
  final ValueChanged<String> onDifficultyChanged;
  final VoidCallback onGenerate;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionTitle('生成测试'),
          const SizedBox(height: 14),
          Text(
            '题目数量：$count',
            style: const TextStyle(
              color: AppTheme.text,
              fontWeight: FontWeight.w800,
            ),
          ),
          Slider(
            value: count.toDouble(),
            min: 5,
            max: 20,
            divisions: 15,
            label: '$count',
            onChanged: (value) => onCountChanged(value.round()),
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            children: ['基础', '中等', '困难'].map((item) {
              return ChoiceChip(
                label: Text(item),
                selected: item == difficulty,
                onSelected: (_) => onDifficultyChanged(item),
              );
            }).toList(),
          ),
          const SizedBox(height: 18),
          SoftButton(
            label: '生成测试',
            icon: Icons.auto_awesome_outlined,
            primary: true,
            onPressed: onGenerate,
          ),
        ],
      ),
    );
  }
}

class _HistoryPanel extends StatelessWidget {
  const _HistoryPanel({
    required this.tests,
    required this.activeTestId,
    required this.onSelect,
  });

  final List<SoftTest> tests;
  final String activeTestId;
  final ValueChanged<String> onSelect;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionTitle('历史测试'),
          const SizedBox(height: 12),
          ...tests.map(
            (test) => Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: SectionCard(
                inset: true,
                padding: const EdgeInsets.all(14),
                onTap: () => onSelect(test.id),
                child: Row(
                  children: [
                    SoftIcon(
                      icon: test.id == activeTestId
                          ? Icons.check_circle_outline
                          : Icons.description_outlined,
                      color: test.id == activeTestId
                          ? AppTheme.success
                          : AppTheme.accent,
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            test.title,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              color: AppTheme.text,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            '${test.questionCount} 题 · ${test.difficulty} · ${_formatDate(test.createdAt)}',
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
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _PaperPanel extends StatelessWidget {
  const _PaperPanel({required this.test});

  final SoftTest test;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(child: _SectionTitle(test.title)),
              StatusPill(
                label: test.score == null ? '未完成' : '${test.score} 分',
                color: test.score == null ? AppTheme.accentLight : AppTheme.success,
              ),
            ],
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              StatusPill(label: '${test.questionCount} 题'),
              StatusPill(label: test.difficulty),
              StatusPill(label: '用时 ${test.elapsedMinutes} 分钟'),
              StatusPill(label: '薄弱点 ${test.weakPoint}', color: AppTheme.danger),
            ],
          ),
          const SizedBox(height: 16),
          ...test.questions.take(5).toList().asMap().entries.map(
                (entry) => Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: QuestionCard(
                    index: entry.key + 1,
                    title: entry.value.title,
                    options: entry.value.options,
                  ),
                ),
              ),
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.title);

  final String title;

  @override
  Widget build(BuildContext context) {
    return Text(
      title,
      style: const TextStyle(
        color: AppTheme.text,
        fontSize: 22,
        fontWeight: FontWeight.w800,
      ),
    );
  }
}

String _formatDate(DateTime value) {
  return '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')}';
}
