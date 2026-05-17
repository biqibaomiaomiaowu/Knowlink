import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/theme/app_theme.dart';
import '../../core/widgets/app_error_view.dart';
import '../../core/widgets/app_loading_view.dart';
import '../../core/widgets/app_scaffold.dart';
import '../../core/widgets/knowlink_widgets.dart';
import '../../shared/models/quiz_models.dart';
import '../../shared/models/quiz_state.dart';
import '../../shared/providers/quiz_provider.dart';

class QuizPage extends ConsumerStatefulWidget {
  const QuizPage({
    this.quizId,
    this.courseId,
    super.key,
  });

  final String? quizId;
  final String? courseId;

  @override
  ConsumerState<QuizPage> createState() => _QuizPageState();
}

class _QuizPageState extends ConsumerState<QuizPage> {
  String? _loadedQuizId;
  String? _preparedCourseId;

  @override
  void initState() {
    super.initState();
    _scheduleEntrySync();
  }

  @override
  void didUpdateWidget(covariant QuizPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.quizId != widget.quizId ||
        oldWidget.courseId != widget.courseId) {
      _scheduleEntrySync();
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(quizProvider);
    final quiz = state.quizValue;
    final courseId = widget.courseId ?? quiz?.courseId.toString();
    final quizId = widget.quizId ?? quiz?.quizId.toString();

    return AppScaffold(
      title: '测验',
      activeTab: KnowLinkTab.quiz,
      courseId: courseId,
      quizId: quizId,
      body: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const PageTitle(
              title: '测验',
              subtitle: '围绕当前课程生成短测，提交后查看得分、掌握度变化和下一步复习建议。',
            ),
            _QuizStatusBar(
              quiz: quiz,
              state: state,
              courseId: courseId,
              questionCountLevel: state.questionCountLevel,
              onLevelChanged:
                  ref.read(quizProvider.notifier).setQuestionCountLevel,
              onGenerate: courseId == null
                  ? null
                  : () => ref.read(quizProvider.notifier).generateAndPoll(
                        courseId,
                        interval: const Duration(milliseconds: 20),
                      ),
            ),
            const SizedBox(height: 16),
            _QuizBody(
              state: state,
              courseId: courseId,
              onRetryLoad: quizId == null ? null : () => _loadQuiz(quizId),
              onSelectAnswer: (questionId, option) {
                ref.read(quizProvider.notifier).selectAnswer(
                      questionId: questionId,
                      selectedOption: option,
                    );
              },
              onSubmit: quiz == null
                  ? null
                  : () => ref.read(quizProvider.notifier).submit(quiz.quizId),
              onReview: courseId == null
                  ? null
                  : () => context.go('/courses/$courseId/review'),
            ),
          ],
        ),
      ),
    );
  }

  void _scheduleEntrySync() {
    final quizId = widget.quizId;
    if (quizId != null) {
      if (quizId == _loadedQuizId) {
        return;
      }
      _loadedQuizId = quizId;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) {
          return;
        }
        _loadQuiz(quizId);
      });
      return;
    }

    final courseId = widget.courseId;
    if (courseId == null || courseId == _preparedCourseId) {
      return;
    }
    _preparedCourseId = courseId;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) {
        return;
      }
      ref.read(quizProvider.notifier).prepareCourse(courseId);
    });
  }

  void _loadQuiz(String quizId) {
    final parsed = int.tryParse(quizId);
    if (parsed == null) {
      return;
    }
    ref.read(quizProvider.notifier).loadQuiz(parsed);
  }
}

class _QuizStatusBar extends StatelessWidget {
  const _QuizStatusBar({
    required this.quiz,
    required this.state,
    required this.courseId,
    required this.questionCountLevel,
    required this.onLevelChanged,
    required this.onGenerate,
  });

  final QuizModel? quiz;
  final QuizState state;
  final String? courseId;
  final QuizQuestionCountLevel questionCountLevel;
  final ValueChanged<QuizQuestionCountLevel> onLevelChanged;
  final VoidCallback? onGenerate;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      padding: const EdgeInsets.all(18),
      child: Wrap(
        spacing: 12,
        runSpacing: 12,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          StatusPill(
            label: quiz == null ? '未生成测验' : '测验编号：${quiz!.quizId}',
            icon: Icons.quiz_outlined,
          ),
          if (courseId != null)
            StatusPill(
              label: '课程编号：$courseId',
              color: const Color(0xFF64748B),
            ),
          if (quiz != null)
            StatusPill(
              label: _statusLabel(quiz!.status),
              color: _statusColor(quiz!.status),
            ),
          if (state.status.valueOrNull != null)
            StatusPill(
              label:
                  '题目 ${state.status.valueOrNull!.questionCount} · ${_statusLabel(state.status.valueOrNull!.status)}',
              color: _statusColor(state.status.valueOrNull!.status),
            ),
          _QuestionCountLevelSelector(
            selected: questionCountLevel,
            enabled: !state.isGenerating,
            onChanged: onLevelChanged,
          ),
          FilledButton.icon(
            onPressed: state.isGenerating ? null : onGenerate,
            icon: state.isGenerating
                ? const SizedBox.square(
                    dimension: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.auto_awesome),
            label: Text(state.isGenerating ? '生成中' : '生成测验'),
          ),
        ],
      ),
    );
  }
}

class _QuestionCountLevelSelector extends StatelessWidget {
  const _QuestionCountLevelSelector({
    required this.selected,
    required this.enabled,
    required this.onChanged,
  });

  final QuizQuestionCountLevel selected;
  final bool enabled;
  final ValueChanged<QuizQuestionCountLevel> onChanged;

  @override
  Widget build(BuildContext context) {
    return SegmentedButton<QuizQuestionCountLevel>(
      showSelectedIcon: false,
      selected: {selected},
      onSelectionChanged: enabled
          ? (selection) {
              final next = selection.firstOrNull;
              if (next != null) {
                onChanged(next);
              }
            }
          : null,
      segments: const [
        ButtonSegment(
          value: QuizQuestionCountLevel.small,
          label: Text('少量 1-3题'),
          icon: Icon(Icons.looks_one_outlined),
        ),
        ButtonSegment(
          value: QuizQuestionCountLevel.medium,
          label: Text('适中 3-5题'),
          icon: Icon(Icons.tune),
        ),
        ButtonSegment(
          value: QuizQuestionCountLevel.large,
          label: Text('多练 5-10题'),
          icon: Icon(Icons.add_task),
        ),
      ],
    );
  }
}

class _QuizBody extends StatelessWidget {
  const _QuizBody({
    required this.state,
    required this.courseId,
    required this.onRetryLoad,
    required this.onSelectAnswer,
    required this.onSubmit,
    required this.onReview,
  });

  final QuizState state;
  final String? courseId;
  final VoidCallback? onRetryLoad;
  final void Function(int questionId, String option) onSelectAnswer;
  final VoidCallback? onSubmit;
  final VoidCallback? onReview;

  @override
  Widget build(BuildContext context) {
    if (state.quiz.isLoading && state.quizValue == null) {
      return const AppLoadingView(label: '正在加载测验...');
    }
    if (state.quiz.hasError) {
      return AppErrorView(
        message: '测验加载失败：${state.quiz.error}',
        onRetry: onRetryLoad,
      );
    }
    if (state.generation.hasError) {
      return AppErrorView(
        message: '测验生成失败：${state.generation.error}',
      );
    }

    final quiz = state.quizValue;
    if (quiz == null) {
      return _EmptyQuizCard(courseId: courseId);
    }
    if (quiz.questions.isEmpty) {
      return const _EmptyQuestionsCard();
    }

    final wide = MediaQuery.sizeOf(context).width >= 980;
    final questions = _QuestionList(
      quiz: quiz,
      selectedAnswers: state.selectedAnswers,
      result: state.submissionValue,
      onSelectAnswer: onSelectAnswer,
    );
    final result = _QuizResultPanel(
      quiz: quiz,
      state: state,
      onSubmit: state.canSubmit ? onSubmit : null,
      onReview: onReview,
    );

    if (wide) {
      return Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(flex: 3, child: questions),
          const SizedBox(width: 16),
          Expanded(flex: 2, child: result),
        ],
      );
    }

    return Column(
      children: [
        questions,
        const SizedBox(height: 16),
        result,
      ],
    );
  }
}

class _EmptyQuizCard extends StatelessWidget {
  const _EmptyQuizCard({
    required this.courseId,
  });

  final String? courseId;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('还没有测验', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 10),
          const Text(
            '完成讲义学习后，可以为当前课程生成 3 到 5 道短测题。',
            style: TextStyle(
              color: AppTheme.muted,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 16),
          if (courseId == null)
            const StatusPill(label: '缺少课程编号', color: Color(0xFFEF4444))
          else
            const StatusPill(label: '可生成', color: Color(0xFF22C55E)),
        ],
      ),
    );
  }
}

class _EmptyQuestionsCard extends StatelessWidget {
  const _EmptyQuestionsCard();

  @override
  Widget build(BuildContext context) {
    return const SectionCard(
      child: Text(
        '当前测验没有题目。请重新生成测验或稍后刷新。',
        style: TextStyle(color: AppTheme.muted, fontWeight: FontWeight.w700),
      ),
    );
  }
}

class _QuestionList extends StatelessWidget {
  const _QuestionList({
    required this.quiz,
    required this.selectedAnswers,
    required this.result,
    required this.onSelectAnswer,
  });

  final QuizModel quiz;
  final Map<int, String> selectedAnswers;
  final SubmitQuizResultModel? result;
  final void Function(int questionId, String option) onSelectAnswer;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      padding: const EdgeInsets.all(22),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text('题目', style: Theme.of(context).textTheme.titleLarge),
              const Spacer(),
              StatusPill(label: '${quiz.questionCount} 题'),
            ],
          ),
          const SizedBox(height: 16),
          for (var index = 0; index < quiz.questions.length; index++) ...[
            _QuestionCard(
              index: index,
              question: quiz.questions[index],
              selectedOption: selectedAnswers[quiz.questions[index].questionId],
              result: _resultFor(quiz.questions[index].questionId),
              locked: result != null,
              onSelectAnswer: onSelectAnswer,
            ),
            if (index != quiz.questions.length - 1) const Divider(height: 32),
          ],
        ],
      ),
    );
  }

  QuizAttemptItemResultModel? _resultFor(int questionId) {
    final items = result?.items ?? const [];
    for (final item in items) {
      if (item.questionId == questionId) {
        return item;
      }
    }
    return null;
  }
}

class _QuestionCard extends StatelessWidget {
  const _QuestionCard({
    required this.index,
    required this.question,
    required this.selectedOption,
    required this.result,
    required this.locked,
    required this.onSelectAnswer,
  });

  final int index;
  final QuizQuestionModel question;
  final String? selectedOption;
  final QuizAttemptItemResultModel? result;
  final bool locked;
  final void Function(int questionId, String option) onSelectAnswer;

  @override
  Widget build(BuildContext context) {
    final resultLabel = _questionResultLabel(result, selectedOption);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Wrap(
          spacing: 10,
          runSpacing: 8,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            StatusPill(label: '第 ${index + 1} 题'),
            if (resultLabel != null) resultLabel,
          ],
        ),
        const SizedBox(height: 12),
        MarkdownBody(
          data: question.stemMd.isEmpty ? '题干待生成' : question.stemMd,
          selectable: false,
          styleSheet: MarkdownStyleSheet.fromTheme(Theme.of(context)).copyWith(
            p: const TextStyle(
              color: AppTheme.ink,
              fontSize: 18,
              fontWeight: FontWeight.w800,
              height: 1.45,
            ),
          ),
        ),
        const SizedBox(height: 14),
        for (final option in question.options) ...[
          _OptionTile(
            option: option,
            selected: selectedOption == option,
            locked: locked,
            result: result,
            onTap: () => onSelectAnswer(question.questionId, option),
          ),
          const SizedBox(height: 10),
        ],
        if (result?.explanationMd?.isNotEmpty ?? false) ...[
          const SizedBox(height: 8),
          _ExplanationBox(explanationMd: result!.explanationMd!),
        ],
      ],
    );
  }
}

class _OptionTile extends StatelessWidget {
  const _OptionTile({
    required this.option,
    required this.selected,
    required this.locked,
    required this.result,
    required this.onTap,
  });

  final String option;
  final bool selected;
  final bool locked;
  final QuizAttemptItemResultModel? result;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final correctAnswer = result?.correctAnswer;
    final isCorrectAnswer = correctAnswer != null && correctAnswer == option;
    final isWrongSelection =
        selected && result?.isCorrect == false && correctAnswer != option;
    final color = isCorrectAnswer
        ? const Color(0xFF16A34A)
        : isWrongSelection
            ? const Color(0xFFEF4444)
            : selected
                ? AppTheme.brandBlue
                : AppTheme.line;

    return InkWell(
      onTap: locked ? null : onTap,
      borderRadius: BorderRadius.circular(8),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: selected || isCorrectAnswer
              ? color.withValues(alpha: 0.08)
              : Colors.white,
          border: Border.all(color: color, width: selected ? 1.4 : 1),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Row(
          children: [
            Icon(
              selected
                  ? Icons.radio_button_checked
                  : Icons.radio_button_unchecked,
              color: selected || isCorrectAnswer ? color : AppTheme.muted,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                option,
                style: const TextStyle(
                  color: AppTheme.ink,
                  fontWeight: FontWeight.w700,
                  fontSize: 16,
                ),
              ),
            ),
            if (isCorrectAnswer)
              const Icon(Icons.check_circle, color: Color(0xFF16A34A))
            else if (isWrongSelection)
              const Icon(Icons.cancel, color: Color(0xFFEF4444)),
          ],
        ),
      ),
    );
  }
}

class _ExplanationBox extends StatelessWidget {
  const _ExplanationBox({
    required this.explanationMd,
  });

  final String explanationMd;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FBFF),
        border: Border.all(color: const Color(0xFFBFDBFE)),
        borderRadius: BorderRadius.circular(8),
      ),
      child: MarkdownBody(data: explanationMd),
    );
  }
}

class _QuizResultPanel extends StatelessWidget {
  const _QuizResultPanel({
    required this.quiz,
    required this.state,
    required this.onSubmit,
    required this.onReview,
  });

  final QuizModel quiz;
  final QuizState state;
  final VoidCallback? onSubmit;
  final VoidCallback? onReview;

  @override
  Widget build(BuildContext context) {
    final result = state.submissionValue;
    return SectionCard(
      padding: const EdgeInsets.all(22),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('提交结果', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 14),
          if (state.submission.isLoading)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 18),
              child: Center(child: CircularProgressIndicator()),
            )
          else if (state.submission.hasError)
            Text(
              '提交失败：${state.submission.error}',
              style: const TextStyle(
                color: Color(0xFFEF4444),
                fontWeight: FontWeight.w700,
              ),
            )
          else if (result == null)
            _BeforeSubmitSummary(
              answeredCount: state.selectedAnswers.length,
              totalCount: quiz.questions.length,
            )
          else
            _AfterSubmitSummary(result: result),
          const SizedBox(height: 16),
          if (result == null)
            GradientButton(
              label: state.submission.isLoading ? '提交中' : '提交答案',
              icon: Icons.send_rounded,
              onPressed: onSubmit,
            )
          else
            GradientButton(
              label: '查看复习任务',
              icon: Icons.calendar_today_outlined,
              onPressed: onReview,
            ),
        ],
      ),
    );
  }
}

class _BeforeSubmitSummary extends StatelessWidget {
  const _BeforeSubmitSummary({
    required this.answeredCount,
    required this.totalCount,
  });

  final int answeredCount;
  final int totalCount;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        MetricBox(
          icon: Icons.checklist_rtl,
          label: '已作答',
          value: '$answeredCount/$totalCount',
          detail: answeredCount == totalCount ? '可以提交' : '请完成所有题目',
        ),
        const SizedBox(height: 12),
        const Text(
          '提交后会更新掌握度，并生成下一步复习任务。',
          style: TextStyle(color: AppTheme.muted, fontWeight: FontWeight.w600),
        ),
      ],
    );
  }
}

class _AfterSubmitSummary extends StatelessWidget {
  const _AfterSubmitSummary({
    required this.result,
  });

  final SubmitQuizResultModel result;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Wrap(
          spacing: 12,
          runSpacing: 12,
          children: [
            MetricBox(
              icon: Icons.scoreboard_outlined,
              label: '得分',
              value: '${result.score}/${result.totalScore}',
            ),
            MetricBox(
              icon: Icons.track_changes,
              label: '正确率',
              value: '${(result.accuracy * 100).round()}%',
            ),
          ],
        ),
        const SizedBox(height: 16),
        Text('掌握度变化', style: Theme.of(context).textTheme.titleSmall),
        const SizedBox(height: 10),
        if (result.masteryDelta.isEmpty)
          const Text(
            '暂无掌握度变化。',
            style:
                TextStyle(color: AppTheme.muted, fontWeight: FontWeight.w600),
          )
        else
          for (final delta in result.masteryDelta)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: _MasteryDeltaRow(delta: delta),
            ),
        if (result.recommendedReviewAction != null) ...[
          const SizedBox(height: 12),
          _RecommendedActionCard(action: result.recommendedReviewAction!),
        ],
      ],
    );
  }
}

class _MasteryDeltaRow extends StatelessWidget {
  const _MasteryDeltaRow({
    required this.delta,
  });

  final MasteryDeltaModel delta;

  @override
  Widget build(BuildContext context) {
    final improved = delta.delta >= 0;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        border: Border.all(color: AppTheme.line),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          Icon(
            improved ? Icons.trending_up : Icons.trending_down,
            color: improved ? const Color(0xFF16A34A) : const Color(0xFFEF4444),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              delta.knowledgePoint,
              style: const TextStyle(
                color: AppTheme.ink,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
          StatusPill(
            label: '${improved ? '+' : ''}${(delta.delta * 100).round()}%',
            color: improved ? const Color(0xFF16A34A) : const Color(0xFFEF4444),
          ),
        ],
      ),
    );
  }
}

class _RecommendedActionCard extends StatelessWidget {
  const _RecommendedActionCard({
    required this.action,
  });

  final RecommendedReviewActionModel action;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFFFFBEB),
        border: Border.all(color: const Color(0xFFFED7AA)),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.auto_awesome, color: Color(0xFFF97316)),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              action.reason.isEmpty ? '建议进入复习任务继续巩固。' : action.reason,
              style: const TextStyle(
                color: Color(0xFF92400E),
                height: 1.45,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

StatusPill? _questionResultLabel(
  QuizAttemptItemResultModel? result,
  String? selectedOption,
) {
  if (result == null) {
    return selectedOption == null
        ? null
        : const StatusPill(label: '已选择', color: Color(0xFF64748B));
  }
  if (result.isCorrect == true) {
    return const StatusPill(label: '正确', color: Color(0xFF16A34A));
  }
  if (result.isCorrect == false) {
    return const StatusPill(label: '待巩固', color: Color(0xFFEF4444));
  }
  return const StatusPill(label: '已提交', color: Color(0xFF64748B));
}

String _statusLabel(String status) {
  return switch (status) {
    'ready' => '已就绪',
    'queued' => '排队中',
    'running' || 'generating' => '生成中',
    'failed' => '生成失败',
    'partial_success' => '部分完成',
    _ => '状态待确认',
  };
}

Color _statusColor(String status) {
  return switch (status) {
    'ready' => const Color(0xFF16A34A),
    'failed' => const Color(0xFFEF4444),
    'queued' || 'running' || 'generating' => const Color(0xFFF97316),
    _ => const Color(0xFF64748B),
  };
}
