import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/theme/app_theme.dart';
import '../../core/widgets/app_error_view.dart';
import '../../core/widgets/app_loading_view.dart';
import '../../core/widgets/app_scaffold.dart';
import '../../core/widgets/knowlink_widgets.dart';
import '../../shared/models/inquiry_models.dart';
import '../../shared/providers/inquiry_provider.dart';

class InquiryPage extends ConsumerStatefulWidget {
  const InquiryPage({
    required this.courseId,
    super.key,
  });

  final String courseId;

  @override
  ConsumerState<InquiryPage> createState() => _InquiryPageState();
}

class _InquiryPageState extends ConsumerState<InquiryPage> {
  String? _lastCourseId;

  @override
  void initState() {
    super.initState();
    _scheduleFetch();
  }

  @override
  void didUpdateWidget(covariant InquiryPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.courseId != widget.courseId) {
      _scheduleFetch();
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(inquiryProvider);
    final notifier = ref.read(inquiryProvider.notifier);
    final questions = state.questions.valueOrNull;
    final saved = state.submitResult.valueOrNull?.saved ?? false;

    return AppScaffold(
      title: 'AI 个性化问询',
      activeTab: KnowLinkTab.inquiry,
      courseId: widget.courseId,
      body: ListView(
        children: [
          const _InquiryHero(),
          const SizedBox(height: 22),
          if (state.questions.isLoading)
            const AppLoadingView(label: '正在读取问询题')
          else if (state.questions.hasError)
            AppErrorView(
              message: '问询题暂不可用：${state.questions.error}',
              onRetry: () => notifier.fetchQuestions(widget.courseId),
            )
          else if (questions == null)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(22),
                child: Text('进入页面后会读取学习目标、掌握程度、时间预算和讲义偏好。'),
              ),
            )
          else
            LayoutBuilder(
              builder: (context, constraints) {
                final form = _InquiryFormCard(
                  courseId: widget.courseId,
                  questions: questions,
                  answers: state.answers,
                  validationErrors: state.validationErrors,
                  submitError: state.submitResult.error,
                  hasSubmitError: state.submitResult.hasError,
                  saved: saved,
                  isSubmitting: state.isSubmitting,
                  onQuestionChanged: notifier.updateAnswer,
                  onSubmit: () => notifier.submitAnswers(widget.courseId),
                  onEnterHandout: saved
                      ? () => context.go('/courses/${widget.courseId}/handout')
                      : null,
                );
                const preview = _StrategyPreviewCard();
                if (constraints.maxWidth < 900) {
                  return Column(
                    children: [
                      form,
                      const SizedBox(height: 16),
                      const _StrategyPreviewCard(),
                    ],
                  );
                }
                return Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(flex: 7, child: form),
                    const SizedBox(width: 24),
                    const Expanded(flex: 5, child: preview),
                  ],
                );
              },
            ),
        ],
      ),
    );
  }

  void _scheduleFetch() {
    if (_lastCourseId == widget.courseId) {
      return;
    }
    _lastCourseId = widget.courseId;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) {
        return;
      }
      ref.read(inquiryProvider.notifier).fetchQuestions(widget.courseId);
    });
  }
}

class _InquiryHero extends StatelessWidget {
  const _InquiryHero();

  @override
  Widget build(BuildContext context) {
    return const Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(Icons.auto_awesome, color: AppTheme.brandBlue, size: 34),
            SizedBox(width: 18),
            Expanded(
              child: Text(
                'AI 个性化问询',
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
        SizedBox(height: 10),
        Text(
          '在生成讲义前，系统将先了解你的学习目标与偏好，为你量身定制最适合的互动讲义。',
          style: TextStyle(
            color: AppTheme.muted,
            fontSize: 16,
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
    );
  }
}

class _InquiryFormCard extends StatelessWidget {
  const _InquiryFormCard({
    required this.courseId,
    required this.questions,
    required this.answers,
    required this.validationErrors,
    required this.submitError,
    required this.hasSubmitError,
    required this.saved,
    required this.isSubmitting,
    required this.onQuestionChanged,
    required this.onSubmit,
    required this.onEnterHandout,
  });

  final String courseId;
  final InquiryQuestionsModel questions;
  final Map<String, Object> answers;
  final Map<String, String> validationErrors;
  final Object? submitError;
  final bool hasSubmitError;
  final bool saved;
  final bool isSubmitting;
  final void Function(String key, Object value) onQuestionChanged;
  final VoidCallback onSubmit;
  final VoidCallback? onEnterHandout;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              '课程 $courseId · 问卷版本 ${questions.version}',
              style: const TextStyle(
                color: AppTheme.ink,
                fontSize: 18,
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 20),
            ...questions.questions.map(
              (question) => Padding(
                padding: const EdgeInsets.only(bottom: 20),
                child: _QuestionField(
                  question: question,
                  value: answers[question.key],
                  errorText: validationErrors[question.key],
                  onChanged: (value) => onQuestionChanged(question.key, value),
                ),
              ),
            ),
            if (hasSubmitError) ...[
              AppErrorView(
                message: '保存问询答案失败：$submitError',
                onRetry: onSubmit,
              ),
              const SizedBox(height: 12),
            ],
            if (saved) ...[
              const _SavedBanner(),
              const SizedBox(height: 12),
            ],
            FilledButton.icon(
              onPressed: isSubmitting ? null : onSubmit,
              icon: const Icon(Icons.save_outlined),
              label: Text(isSubmitting ? '正在保存' : '保存问询答案'),
            ),
            const SizedBox(height: 12),
            OutlinedButton.icon(
              onPressed: onEnterHandout,
              icon: const Icon(Icons.menu_book_outlined),
              label: const Text('进入讲义页'),
            ),
          ],
        ),
      ),
    );
  }
}

class _QuestionField extends StatelessWidget {
  const _QuestionField({
    required this.question,
    required this.value,
    required this.errorText,
    required this.onChanged,
  });

  final InquiryQuestionModel question;
  final Object? value;
  final String? errorText;
  final ValueChanged<Object> onChanged;

  @override
  Widget build(BuildContext context) {
    if (question.type == 'single_select') {
      return _QuestionShell(
        icon: _iconForQuestion(question.key),
        label: question.label,
        child: DropdownButtonFormField<String>(
          initialValue: value?.toString(),
          decoration: InputDecoration(
            hintText: '请选择${question.label}',
            errorText: errorText,
            border: const OutlineInputBorder(),
          ),
          items: question.options
              .map(
                (option) => DropdownMenuItem<String>(
                  value: option.value,
                  child: Text(option.label),
                ),
              )
              .toList(),
          onChanged: (value) {
            if (value != null) {
              onChanged(value);
            }
          },
        ),
      );
    }

    if (question.type == 'multi_select') {
      final selected = <String>{};
      final rawValue = value;
      if (rawValue is Iterable) {
        for (final item in rawValue) {
          selected.add(item.toString());
        }
      }
      return _QuestionShell(
        icon: _iconForQuestion(question.key),
        label: '${question.label}（可多选）',
        child: Wrap(
          spacing: 12,
          runSpacing: 10,
          children: [
            for (final option in question.options)
              FilterChip(
                selected: selected.contains(option.value),
                label: Text(option.label),
                avatar: Icon(_iconForOption(option.value), size: 18),
                onSelected: (checked) {
                  final next = <String>{...selected};
                  if (checked) {
                    next.add(option.value);
                  } else {
                    next.remove(option.value);
                  }
                  onChanged(next.toList());
                },
              ),
            if (errorText != null)
              Text(
                errorText!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
          ],
        ),
      );
    }

    if (question.type == 'number') {
      return _QuestionShell(
        icon: _iconForQuestion(question.key),
        label: question.label,
        child: TextField(
          decoration: InputDecoration(
            hintText: '请选择或输入数值',
            errorText: errorText,
            border: const OutlineInputBorder(),
          ),
          keyboardType: TextInputType.number,
          inputFormatters: [
            FilteringTextInputFormatter.digitsOnly,
          ],
          onChanged: onChanged,
        ),
      );
    }

    return _QuestionShell(
      icon: _iconForQuestion(question.key),
      label: question.label,
      child: TextField(
        minLines: 4,
        maxLines: 6,
        maxLength: 300,
        decoration: InputDecoration(
          hintText: '请输入你希望讲义特别关注的内容、排除的内容或其他个性化要求...',
          errorText: errorText,
          border: const OutlineInputBorder(),
        ),
        onChanged: onChanged,
      ),
    );
  }

  IconData _iconForQuestion(String key) {
    final lower = key.toLowerCase();
    if (lower.contains('goal')) {
      return Icons.ads_click;
    }
    if (lower.contains('level') || lower.contains('master')) {
      return Icons.bar_chart;
    }
    if (lower.contains('time') || lower.contains('budget')) {
      return Icons.schedule;
    }
    if (lower.contains('style') || lower.contains('preference')) {
      return Icons.star_border;
    }
    return Icons.chat_bubble_outline;
  }

  IconData _iconForOption(String value) {
    final lower = value.toLowerCase();
    if (lower.contains('detail')) {
      return Icons.description_outlined;
    }
    if (lower.contains('exam') || lower.contains('test')) {
      return Icons.bolt_outlined;
    }
    if (lower.contains('quick')) {
      return Icons.flash_on_outlined;
    }
    return Icons.star_border;
  }
}

class _QuestionShell extends StatelessWidget {
  const _QuestionShell({
    required this.icon,
    required this.label,
    required this.child,
  });

  final IconData icon;
  final String label;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(icon, color: AppTheme.brandBlue, size: 24),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                label,
                style: const TextStyle(
                  color: AppTheme.ink,
                  fontSize: 17,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        child,
      ],
    );
  }
}

class _StrategyPreviewCard extends StatelessWidget {
  const _StrategyPreviewCard();

  @override
  Widget build(BuildContext context) {
    return const Card(
      child: Padding(
        padding: EdgeInsets.all(28),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.lightbulb_outline, color: AppTheme.brandBlue),
                SizedBox(width: 12),
                Expanded(
                  child: Text(
                    '个性化策略预览',
                    style: TextStyle(
                      color: AppTheme.ink,
                      fontSize: 20,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
              ],
            ),
            SizedBox(height: 14),
            Text(
              '基于你的选择，系统将采用以下策略生成讲义，并影响后续复习与学习效果。',
              style: TextStyle(
                color: Color(0xFF334155),
                fontSize: 15,
                height: 1.6,
                fontWeight: FontWeight.w600,
              ),
            ),
            SizedBox(height: 22),
            _StrategyItem(
              icon: Icons.ads_click,
              title: '目标导向内容筛选',
              detail: '聚焦与你的学习目标相关的核心知识点，过滤不必要的内容，提升学习效率。',
            ),
            _StrategyItem(
              icon: Icons.bar_chart,
              title: '掌握程度适配',
              detail: '根据你的当前水平调整讲解深度与例题难度，确保内容既具挑战性又易于理解。',
            ),
            _StrategyItem(
              icon: Icons.schedule,
              title: '时间优化编排',
              detail: '在你的时间预算与周期内，合理分配内容篇幅与练习量，保证学习节奏可持续。',
            ),
            _StrategyItem(
              icon: Icons.star_border,
              title: '偏好驱动结构设计',
              detail: '按照你的内容偏好组织讲义结构与呈现方式，突出重点，强化记忆与应用。',
            ),
            SizedBox(height: 10),
            _StrategyNotice(),
          ],
        ),
      ),
    );
  }
}

class _StrategyItem extends StatelessWidget {
  const _StrategyItem({
    required this.icon,
    required this.title,
    required this.detail,
  });

  final IconData icon;
  final String title;
  final String detail;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: const Color(0xFFF3F7FF),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SoftIcon(icon: icon, size: 52),
          const SizedBox(width: 18),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    color: AppTheme.ink,
                    fontSize: 17,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 7),
                Text(
                  detail,
                  style: const TextStyle(
                    color: Color(0xFF334155),
                    fontSize: 14,
                    height: 1.45,
                    fontWeight: FontWeight.w600,
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

class _StrategyNotice extends StatelessWidget {
  const _StrategyNotice();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFEFF6FF),
        border: Border.all(color: const Color(0xFFBFDBFE)),
        borderRadius: BorderRadius.circular(8),
      ),
      child: const Row(
        children: [
          Icon(Icons.info_outline, color: AppTheme.brandBlue, size: 20),
          SizedBox(width: 10),
          Expanded(
            child: Text(
              '生成后，你仍可在学习过程中调整偏好，系统将持续优化你的讲义与复习计划。',
              style: TextStyle(
                color: AppTheme.brandBlue,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _SavedBanner extends StatelessWidget {
  const _SavedBanner();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.primaryContainer,
        borderRadius: BorderRadius.circular(8),
      ),
      child: const Row(
        children: [
          Icon(Icons.check_circle_outline),
          SizedBox(width: 8),
          Expanded(child: Text('问询答案已保存。')),
        ],
      ),
    );
  }
}
