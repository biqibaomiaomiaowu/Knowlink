import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/widgets/app_error_view.dart';
import '../../core/widgets/app_loading_view.dart';
import '../../core/widgets/app_scaffold.dart';
import '../../shared/models/confirm_recommendation_result.dart';
import '../../shared/models/recommendation_card.dart';
import '../../shared/models/recommendation_enums.dart';
import '../../shared/models/resource_manifest_item.dart';
import '../../shared/providers/course_flow_providers.dart';
import '../../shared/providers/course_recommend_provider.dart';

class CourseRecommendPage extends ConsumerStatefulWidget {
  const CourseRecommendPage({super.key});

  @override
  ConsumerState<CourseRecommendPage> createState() =>
      _CourseRecommendPageState();
}

class _CourseRecommendPageState extends ConsumerState<CourseRecommendPage> {
  static const int _minimumTimeBudgetMinutes = 30;
  static const String _timeBudgetValidationMessage =
      '\u8bf7\u8f93\u5165\u4e0d\u5c11\u4e8e 30 \u7684\u6574\u6570\u5206\u949f\u6570';

  late final TextEditingController _goalTextController;
  late final TextEditingController _timeBudgetController;
  late final TextEditingController _examAtController;
  late final ScrollController _scrollController;
  String? _timeBudgetErrorText;
  String? _examAtErrorText;

  @override
  void initState() {
    super.initState();
    final draft = ref.read(courseRecommendProvider).requestDraft;
    _goalTextController = TextEditingController(text: draft.goalText);
    _timeBudgetController = TextEditingController(
      text: draft.timeBudgetMinutes.toString(),
    );
    _examAtController = TextEditingController(
      text: draft.examAt?.toIso8601String() ?? '',
    );
    _scrollController = ScrollController();
  }

  @override
  void dispose() {
    _goalTextController.dispose();
    _timeBudgetController.dispose();
    _examAtController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(courseRecommendProvider);
    final notifier = ref.read(courseRecommendProvider.notifier);
    final isDraftLocked = state.isFetchingRecommendations || state.isConfirming;
    final isSubmitDisabled = isDraftLocked ||
        _timeBudgetErrorText != null ||
        _examAtErrorText != null;

    ref.listen(courseRecommendProvider, (previous, next) {
      final previousCourseId =
          previous?.confirmation.valueOrNull?.course.courseId;
      final course = next.confirmation.valueOrNull?.course;
      if (course != null && course.courseId != previousCourseId) {
        ref.read(courseFlowProvider.notifier).syncCreatedCourse(
              courseId: course.courseId,
              lifecycleStatus: course.lifecycleStatus,
              pipelineStage: course.pipelineStage,
              pipelineStatus: course.pipelineStatus,
            );
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('课程已创建，可继续准备资料。'),
          ),
        );
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (!_scrollController.hasClients) {
            return;
          }
          _scrollController.animateTo(
            _scrollController.position.maxScrollExtent,
            duration: const Duration(milliseconds: 250),
            curve: Curves.easeOut,
          );
        });
      }
    });

    final recommendations = state.recommendations.valueOrNull ?? const [];
    final confirmation = state.confirmation.valueOrNull;
    final confirmedCard = _findCardByCatalogId(
      recommendations,
      confirmation?.createdFromCatalogId,
    );

    return AppScaffold(
      title: '智能课程推荐',
      body: ListView(
        controller: _scrollController,
        children: [
          _RequestDraftCard(
            goalTextController: _goalTextController,
            timeBudgetController: _timeBudgetController,
            examAtController: _examAtController,
            timeBudgetErrorText: _timeBudgetErrorText,
            examAtErrorText: _examAtErrorText,
            selfLevel: state.requestDraft.selfLevel,
            preferredStyle: state.requestDraft.preferredStyle,
            isDraftLocked: isDraftLocked,
            isLoading: state.isFetchingRecommendations,
            isSubmitDisabled: isSubmitDisabled,
            onGoalTextChanged: (value) => notifier.updateDraft(goalText: value),
            onTimeBudgetChanged: (value) {
              final trimmed = value.trim();
              if (trimmed.isEmpty) {
                setState(() {
                  _timeBudgetErrorText = '请输入大于 0 的整数分钟数';
                });
                _timeBudgetErrorText = _timeBudgetValidationMessage;
                notifier.updateDraft();
                return;
              }
              final minutes = int.tryParse(trimmed);
              if (minutes != null && minutes >= _minimumTimeBudgetMinutes) {
                setState(() {
                  _timeBudgetErrorText = null;
                });
                notifier.updateDraft(timeBudgetMinutes: minutes);
              } else {
                setState(() {
                  _timeBudgetErrorText = '请输入大于 0 的整数';
                });
                _timeBudgetErrorText = _timeBudgetValidationMessage;
                notifier.updateDraft();
              }
            },
            onExamAtChanged: (value) {
              final trimmed = value.trim();
              if (trimmed.isEmpty) {
                setState(() {
                  _examAtErrorText = null;
                });
                notifier.updateDraft(clearExamAt: true);
                return;
              }

              final parsed = DateTime.tryParse(trimmed);
              if (parsed != null) {
                setState(() {
                  _examAtErrorText = null;
                });
                notifier.updateDraft(examAt: parsed);
              } else {
                setState(() {
                  _examAtErrorText = '请输入合法的 ISO 时间';
                });
                notifier.updateDraft(clearExamAt: true);
              }
            },
            onSelfLevelChanged: (value) {
              if (value != null) {
                notifier.updateDraft(selfLevel: value);
              }
            },
            onPreferredStyleChanged: (value) {
              if (value != null) {
                notifier.updateDraft(preferredStyle: value);
              }
            },
            onSubmit: notifier.fetchRecommendations,
          ),
          const SizedBox(height: 16),
          if (state.isFetchingRecommendations)
            const AppLoadingView(label: '正在获取推荐')
          else if (state.recommendations.hasError)
            AppErrorView(
              message: '推荐接口暂不可用：${state.recommendations.error}',
              onRetry: notifier.fetchRecommendations,
            )
          else if (recommendations.isEmpty)
            const _EmptyRecommendationsCard()
          else
            ..._buildRecommendationCards(
              recommendations: recommendations,
              isConfirming: state.isConfirming,
              activeConfirmCatalogId: state.activeConfirmCatalogId,
              onConfirm: notifier.confirmRecommendation,
            ),
          if (state.confirmation.hasError) ...[
            const SizedBox(height: 16),
            AppErrorView(
              message: '确认入课失败：${state.confirmation.error}',
              onRetry: state.lastConfirmCatalogId == null
                  ? null
                  : () => notifier.confirmRecommendation(
                        state.lastConfirmCatalogId!,
                      ),
            ),
          ],
          if (confirmation != null) ...[
            const SizedBox(height: 16),
            _CreatedCourseCard(
              result: confirmation,
              manifest: confirmedCard?.defaultResourceManifest ?? const [],
            ),
          ],
        ],
      ),
    );
  }

  List<Widget> _buildRecommendationCards({
    required List<RecommendationCardModel> recommendations,
    required bool isConfirming,
    required String? activeConfirmCatalogId,
    required Future<void> Function(
      String catalogId, {
      String? titleOverride,
    }) onConfirm,
  }) {
    final widgets = <Widget>[];
    for (var index = 0; index < recommendations.length; index++) {
      final item = recommendations[index];
      widgets.add(
        _RecommendationCard(
          item: item,
          isConfirming:
              isConfirming && activeConfirmCatalogId == item.catalogId,
          isActionDisabled: isConfirming,
          onConfirm: () => onConfirm(item.catalogId),
        ),
      );
      if (index < recommendations.length - 1) {
        widgets.add(const SizedBox(height: 12));
      }
    }
    return widgets;
  }

  RecommendationCardModel? _findCardByCatalogId(
    List<RecommendationCardModel> recommendations,
    String? catalogId,
  ) {
    if (catalogId == null) {
      return null;
    }

    for (final item in recommendations) {
      if (item.catalogId == catalogId) {
        return item;
      }
    }
    return null;
  }
}

class _RequestDraftCard extends StatelessWidget {
  const _RequestDraftCard({
    required this.goalTextController,
    required this.timeBudgetController,
    required this.examAtController,
    required this.timeBudgetErrorText,
    required this.examAtErrorText,
    required this.selfLevel,
    required this.preferredStyle,
    required this.isDraftLocked,
    required this.isLoading,
    required this.isSubmitDisabled,
    required this.onGoalTextChanged,
    required this.onTimeBudgetChanged,
    required this.onExamAtChanged,
    required this.onSelfLevelChanged,
    required this.onPreferredStyleChanged,
    required this.onSubmit,
  });

  final TextEditingController goalTextController;
  final TextEditingController timeBudgetController;
  final TextEditingController examAtController;
  final String? timeBudgetErrorText;
  final String? examAtErrorText;
  final SelfLevel selfLevel;
  final PreferredStyle preferredStyle;
  final bool isDraftLocked;
  final bool isLoading;
  final bool isSubmitDisabled;
  final ValueChanged<String> onGoalTextChanged;
  final ValueChanged<String> onTimeBudgetChanged;
  final ValueChanged<String> onExamAtChanged;
  final ValueChanged<SelfLevel?> onSelfLevelChanged;
  final ValueChanged<PreferredStyle?> onPreferredStyleChanged;
  final VoidCallback onSubmit;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Week 1 推荐条件',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 12),
            TextField(
              controller: goalTextController,
              enabled: !isDraftLocked,
              decoration: const InputDecoration(
                labelText: '学习目标',
                hintText: '例如：高等数学期末复习',
              ),
              onChanged: isDraftLocked ? null : onGoalTextChanged,
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: DropdownButtonFormField<SelfLevel>(
                    initialValue: selfLevel,
                    decoration: const InputDecoration(labelText: '基础水平'),
                    items: SelfLevel.values
                        .map(
                          (level) => DropdownMenuItem(
                            value: level,
                            child: Text(_selfLevelLabel(level)),
                          ),
                        )
                        .toList(),
                    onChanged: isDraftLocked ? null : onSelfLevelChanged,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: TextField(
                    controller: timeBudgetController,
                    enabled: !isDraftLocked,
                    keyboardType: TextInputType.number,
                    decoration: InputDecoration(
                      errorText: timeBudgetErrorText,
                      labelText: '时间预算（分钟）',
                    ),
                    onChanged: isDraftLocked ? null : onTimeBudgetChanged,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: DropdownButtonFormField<PreferredStyle>(
                    initialValue: preferredStyle,
                    decoration: const InputDecoration(labelText: '讲义偏好'),
                    items: PreferredStyle.values
                        .map(
                          (style) => DropdownMenuItem(
                            value: style,
                            child: Text(_preferredStyleLabel(style)),
                          ),
                        )
                        .toList(),
                    onChanged: isDraftLocked ? null : onPreferredStyleChanged,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: TextField(
                    controller: examAtController,
                    enabled: !isDraftLocked,
                    decoration: InputDecoration(
                      labelText: '考试时间（可选）',
                      hintText: '2026-06-15T09:00:00+08:00',
                      errorText: examAtErrorText,
                    ),
                    onChanged: isDraftLocked ? null : onExamAtChanged,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: isSubmitDisabled ? null : onSubmit,
                child: Text(isLoading ? '获取中...' : '获取推荐'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _RecommendationCard extends StatelessWidget {
  const _RecommendationCard({
    required this.item,
    required this.isConfirming,
    required this.isActionDisabled,
    required this.onConfirm,
  });

  final RecommendationCardModel item;
  final bool isConfirming;
  final bool isActionDisabled;
  final VoidCallback onConfirm;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              item.title,
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            Text('${item.provider} | ${item.level} | ${item.estimatedHours}h'),
            const SizedBox(height: 8),
            Text('匹配度 ${item.fitScore}'),
            const SizedBox(height: 8),
            for (final reason in item.reasons) Text('- $reason'),
            const SizedBox(height: 12),
            Text(
              '默认资料清单',
              style: Theme.of(context).textTheme.titleSmall,
            ),
            const SizedBox(height: 8),
            _ResourceManifestList(manifest: item.defaultResourceManifest),
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: isActionDisabled ? null : onConfirm,
                child: Text(isConfirming ? '确认中...' : '确认入课'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _CreatedCourseCard extends StatelessWidget {
  const _CreatedCourseCard({
    required this.result,
    required this.manifest,
  });

  final ConfirmRecommendationResultModel result;
  final List<ResourceManifestItemModel> manifest;

  @override
  Widget build(BuildContext context) {
    final course = result.course;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '课程已创建',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            Text('课程名：${course.title}'),
            Text('courseId：${course.courseId}'),
            Text('创建来源：${result.createdFromCatalogId}'),
            Text(
              '当前状态：${course.lifecycleStatus} / '
              '${course.pipelineStage} / ${course.pipelineStatus}',
            ),
            if (manifest.isNotEmpty) ...[
              const SizedBox(height: 12),
              Text(
                '待准备资料',
                style: Theme.of(context).textTheme.titleSmall,
              ),
              const SizedBox(height: 8),
              _ResourceManifestList(manifest: manifest),
            ],
            const SizedBox(height: 16),
            OutlinedButton(
              onPressed: () =>
                  context.go('/import?courseId=${course.courseId}'),
              child: const Text('前往自主导入页'),
            ),
          ],
        ),
      ),
    );
  }
}

class _ResourceManifestList extends StatelessWidget {
  const _ResourceManifestList({
    required this.manifest,
  });

  final List<ResourceManifestItemModel> manifest;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: manifest
          .map(
            (item) => Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Text(
                '- ${_resourceTypeLabel(item.resourceType)}'
                ' · ${item.isRequired ? '必需' : '可选'}'
                ' · ${item.description}',
              ),
            ),
          )
          .toList(),
    );
  }
}

class _EmptyRecommendationsCard extends StatelessWidget {
  const _EmptyRecommendationsCard();

  @override
  Widget build(BuildContext context) {
    return const Card(
      child: Padding(
        padding: EdgeInsets.all(16),
        child: Text('填写条件后点击“获取推荐”，查看真实推荐结果并完成确认入课。'),
      ),
    );
  }
}

String _selfLevelLabel(SelfLevel level) {
  switch (level) {
    case SelfLevel.beginner:
      return '基础薄弱';
    case SelfLevel.intermediate:
      return '基础一般';
    case SelfLevel.advanced:
      return '基础较好';
  }
}

String _preferredStyleLabel(PreferredStyle style) {
  switch (style) {
    case PreferredStyle.balanced:
      return '平衡讲义';
    case PreferredStyle.exam:
      return '应试冲刺';
    case PreferredStyle.detailed:
      return '详细展开';
    case PreferredStyle.quick:
      return '速学提纲';
  }
}

String _resourceTypeLabel(ResourceType resourceType) {
  switch (resourceType) {
    case ResourceType.mp4:
      return 'MP4';
    case ResourceType.pdf:
      return 'PDF';
    case ResourceType.pptx:
      return 'PPTX';
    case ResourceType.docx:
      return 'DOCX';
    case ResourceType.srt:
      return 'SRT';
  }
}
