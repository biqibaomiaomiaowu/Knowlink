import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/widgets/app_error_view.dart';
import '../../core/widgets/app_loading_view.dart';
import '../../core/widgets/app_scaffold.dart';
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
      body: ListView(
        children: [
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
                padding: EdgeInsets.all(16),
                child: Text('进入页面后会读取学习目标、掌握程度、时间预算和讲义偏好。'),
              ),
            )
          else
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(
                      '课程 ${widget.courseId} · 问卷版本 ${questions.version}',
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 16),
                    ...questions.questions.map(
                      (question) => Padding(
                        padding: const EdgeInsets.only(bottom: 16),
                        child: _QuestionField(
                          question: question,
                          value: state.answers[question.key],
                          errorText: state.validationErrors[question.key],
                          onChanged: (value) => notifier.updateAnswer(
                            question.key,
                            value,
                          ),
                        ),
                      ),
                    ),
                    if (state.submitResult.hasError) ...[
                      AppErrorView(
                        message: '保存问询答案失败：${state.submitResult.error}',
                        onRetry: () => notifier.submitAnswers(widget.courseId),
                      ),
                      const SizedBox(height: 12),
                    ],
                    if (saved) ...[
                      const _SavedBanner(),
                      const SizedBox(height: 12),
                    ],
                    FilledButton.icon(
                      onPressed: state.isSubmitting
                          ? null
                          : () => notifier.submitAnswers(widget.courseId),
                      icon: const Icon(Icons.save_outlined),
                      label: Text(state.isSubmitting ? '正在保存' : '保存问询答案'),
                    ),
                    const SizedBox(height: 12),
                    OutlinedButton.icon(
                      onPressed: saved
                          ? () =>
                              context.go('/courses/${widget.courseId}/handout')
                          : null,
                      icon: const Icon(Icons.menu_book_outlined),
                      label: const Text('进入讲义页'),
                    ),
                  ],
                ),
              ),
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
      return DropdownButtonFormField<String>(
        initialValue: value?.toString(),
        decoration: InputDecoration(
          labelText: question.label,
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
      );
    }

    if (question.type == 'number') {
      return TextField(
        decoration: InputDecoration(
          labelText: question.label,
          errorText: errorText,
          border: const OutlineInputBorder(),
        ),
        keyboardType: TextInputType.number,
        inputFormatters: [
          FilteringTextInputFormatter.digitsOnly,
        ],
        onChanged: onChanged,
      );
    }

    return TextField(
      decoration: InputDecoration(
        labelText: question.label,
        errorText: errorText,
        border: const OutlineInputBorder(),
      ),
      onChanged: onChanged,
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
