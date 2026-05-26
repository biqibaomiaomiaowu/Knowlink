import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/theme/app_theme.dart';
import '../../core/widgets/app_error_view.dart';
import '../../core/widgets/app_loading_view.dart';
import '../../core/widgets/app_scaffold.dart';
import '../../core/widgets/knowlink_widgets.dart';
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
      activeTab: KnowLinkTab.recommend,
      body: ListView(
        controller: _scrollController,
        children: [
          const _RecommendHero(),
          const SizedBox(height: 22),
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
          const SizedBox(height: 20),
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
          isActionDisabled: isConfirming || !item.nextAction.canConfirmCourse,
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
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                _StepBadge(number: '1'),
                SizedBox(width: 12),
                Expanded(
                  child: Text(
                    '设置你的学习偏好',
                    style: TextStyle(
                      color: AppTheme.ink,
                      fontSize: 20,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),
            LayoutBuilder(
              builder: (context, constraints) {
                final useGrid = constraints.maxWidth >= 900;
                final fields = [
                  _FieldShell(
                    label: '学习目标',
                    child: TextField(
                      controller: goalTextController,
                      enabled: !isDraftLocked,
                      decoration: const InputDecoration(
                        hintText: '掌握数据结构与算法基础',
                      ),
                      onChanged: isDraftLocked ? null : onGoalTextChanged,
                    ),
                  ),
                  _FieldShell(
                    label: '基础水平',
                    child: DropdownButtonFormField<SelfLevel>(
                      initialValue: selfLevel,
                      decoration: const InputDecoration(),
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
                  _FieldShell(
                    label: '时间周期',
                    child: TextField(
                      controller: timeBudgetController,
                      enabled: !isDraftLocked,
                      keyboardType: TextInputType.number,
                      decoration: InputDecoration(
                        hintText: '例如：480',
                        suffixText: '分钟',
                        errorText: timeBudgetErrorText,
                      ),
                      onChanged: isDraftLocked ? null : onTimeBudgetChanged,
                    ),
                  ),
                  _FieldShell(
                    label: '偏好难度 / 偏好选项',
                    child: DropdownButtonFormField<PreferredStyle>(
                      initialValue: preferredStyle,
                      decoration: const InputDecoration(),
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
                ];
                if (!useGrid) {
                  return Column(
                    children: [
                      for (final field in fields) ...[
                        field,
                        const SizedBox(height: 12),
                      ],
                      _FieldShell(
                        label: '考试时间（可选）',
                        child: TextField(
                          controller: examAtController,
                          enabled: !isDraftLocked,
                          decoration: InputDecoration(
                            hintText: '2026-06-15T09:00:00+08:00',
                            errorText: examAtErrorText,
                          ),
                          onChanged: isDraftLocked ? null : onExamAtChanged,
                        ),
                      ),
                    ],
                  );
                }
                return Column(
                  children: [
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        for (var i = 0; i < fields.length; i++) ...[
                          Expanded(child: fields[i]),
                          if (i != fields.length - 1) const SizedBox(width: 44),
                        ],
                      ],
                    ),
                    const SizedBox(height: 14),
                    SizedBox(
                      width: 380,
                      child: _FieldShell(
                        label: '考试时间（可选）',
                        child: TextField(
                          controller: examAtController,
                          enabled: !isDraftLocked,
                          decoration: InputDecoration(
                            hintText: '2026-06-15T09:00:00+08:00',
                            errorText: examAtErrorText,
                          ),
                          onChanged: isDraftLocked ? null : onExamAtChanged,
                        ),
                      ),
                    ),
                  ],
                );
              },
            ),
            const SizedBox(height: 16),
            Center(
              child: FilledButton.icon(
                onPressed: isSubmitDisabled ? null : onSubmit,
                icon: Icon(isLoading ? Icons.sync : Icons.refresh),
                label: Text(isLoading ? '获取中...' : '获取推荐'),
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
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                _StepBadge(number: '2'),
                SizedBox(width: 12),
                Expanded(
                  child: Text(
                    '为你推荐的课程',
                    style: TextStyle(
                      color: AppTheme.ink,
                      fontSize: 20,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 22),
            LayoutBuilder(
              builder: (context, constraints) {
                final isWide = constraints.maxWidth >= 900;
                final cover = _RecommendationCover(title: item.title);
                final detail = _RecommendationDetail(
                  item: item,
                  isConfirming: isConfirming,
                  isActionDisabled: isActionDisabled,
                  onConfirm: onConfirm,
                );
                if (!isWide) {
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      cover,
                      const SizedBox(height: 18),
                      detail,
                    ],
                  );
                }
                return Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    SizedBox(width: 265, child: cover),
                    const SizedBox(width: 24),
                    Expanded(child: detail),
                  ],
                );
              },
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
            OutlinedButton.icon(
              onPressed: () =>
                  context.go('/import?courseId=${course.courseId}'),
              icon: const Icon(Icons.upload_file_outlined),
              label: const Text('前往自主导入页'),
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
        padding: EdgeInsets.all(22),
        child: Text('填写条件后点击“重新生成推荐”，查看真实推荐结果并完成确认入课。'),
      ),
    );
  }
}

class _RecommendHero extends StatelessWidget {
  const _RecommendHero();

  @override
  Widget build(BuildContext context) {
    return const Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '智能课程推荐',
          style: TextStyle(
            color: AppTheme.ink,
            fontSize: 34,
            fontWeight: FontWeight.w800,
            letterSpacing: 0,
          ),
        ),
        SizedBox(height: 10),
        Text(
          '基于你的学习目标、基础水平、时间预算和内容偏好，为你推荐最合适的课程。',
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

class _FieldShell extends StatelessWidget {
  const _FieldShell({
    required this.label,
    required this.child,
  });

  final String label;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(
            color: AppTheme.ink,
            fontSize: 15,
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(height: 10),
        child,
      ],
    );
  }
}

class _RecommendationCover extends StatelessWidget {
  const _RecommendationCover({required this.title});

  final String title;

  @override
  Widget build(BuildContext context) {
    return AspectRatio(
      aspectRatio: 1.32,
      child: Container(
        padding: const EdgeInsets.all(22),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [Color(0xFF60A5FA), AppTheme.brandBlueDark],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Stack(
          children: [
            const Align(
              alignment: Alignment.topRight,
              child: Icon(
                Icons.play_circle_fill,
                color: Colors.white70,
                size: 34,
              ),
            ),
            Align(
              alignment: Alignment.bottomLeft,
              child: Icon(
                title.contains('结构')
                    ? Icons.account_tree_outlined
                    : Icons.school_outlined,
                color: Colors.white,
                size: 96,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _RecommendationDetail extends StatelessWidget {
  const _RecommendationDetail({
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
    final fitPct = item.fitScore.clamp(0, 100);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          item.title,
          style: const TextStyle(
            color: AppTheme.ink,
            fontSize: 28,
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(height: 10),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            SourceChip(icon: Icons.source_outlined, label: item.provider),
            SourceChip(icon: Icons.school_outlined, label: item.level),
            SourceChip(icon: Icons.sell_outlined, label: '匹配度 $fitPct%'),
          ],
        ),
        const SizedBox(height: 18),
        const Text(
          '推荐理由',
          style: TextStyle(
            color: AppTheme.ink,
            fontSize: 17,
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(height: 8),
        for (final reason in item.reasons.take(3))
          Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Text(
              reason,
              style: const TextStyle(
                color: Color(0xFF334155),
                fontSize: 15,
                height: 1.45,
              ),
            ),
          ),
        if (item.reasonMaterials.isNotEmpty) ...[
          const SizedBox(height: 14),
          const Text(
            '课程资料说明',
            style: TextStyle(
              color: AppTheme.ink,
              fontSize: 17,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 8),
          for (final material in item.reasonMaterials.take(4))
            Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Text(
                material,
                style: const TextStyle(
                  color: Color(0xFF334155),
                  fontSize: 15,
                  height: 1.45,
                ),
              ),
            ),
        ],
        const SizedBox(height: 18),
        LayoutBuilder(
          builder: (context, constraints) {
            final cards = [
              _MetricMiniCard(
                icon: Icons.schedule,
                label: '预计学习时长',
                value: '${item.estimatedHours} 小时',
                detail:
                    '约 ${((item.estimatedHours / 8).ceil()).clamp(1, 99)} 周',
              ),
              _MetricMiniCard(
                icon: Icons.ads_click,
                label: '匹配度',
                value: '$fitPct%',
                detail: '高度匹配',
              ),
              const _MetricMiniCard(
                icon: Icons.bar_chart,
                label: '适配性',
                value: '非常适合',
                detail: '你的学习情况',
              ),
            ];
            if (constraints.maxWidth < 620) {
              return Column(
                children: [
                  for (final card in cards) ...[
                    card,
                    const SizedBox(height: 8),
                  ],
                ],
              );
            }
            return Row(
              children: [
                for (var i = 0; i < cards.length; i++) ...[
                  Expanded(child: cards[i]),
                  if (i != cards.length - 1) const SizedBox(width: 1),
                ],
              ],
            );
          },
        ),
        if (item.defaultResourceManifest.isNotEmpty) ...[
          const SizedBox(height: 16),
          const Divider(),
          const SizedBox(height: 8),
          const Text(
            '补充资料上传（可选）',
            style: TextStyle(
              color: AppTheme.ink,
              fontSize: 18,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 6),
          _ResourceManifestList(manifest: item.defaultResourceManifest),
        ],
        const SizedBox(height: 18),
        Align(
          alignment: Alignment.center,
          child: SizedBox(
            width: 360,
            child: FilledButton.icon(
              icon: const Icon(Icons.menu_book_outlined),
              onPressed: isActionDisabled ? null : onConfirm,
              label: Text(isConfirming ? '确认中...' : item.nextAction.label),
            ),
          ),
        ),
      ],
    );
  }
}

class _MetricMiniCard extends StatelessWidget {
  const _MetricMiniCard({
    required this.icon,
    required this.label,
    required this.value,
    required this.detail,
  });

  final IconData icon;
  final String label;
  final String value;
  final String detail;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 18),
      decoration: BoxDecoration(
        border: Border.all(color: AppTheme.line),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        children: [
          Icon(icon, color: AppTheme.brandBlue, size: 26),
          const SizedBox(height: 10),
          Text(
            label,
            textAlign: TextAlign.center,
            style: const TextStyle(
              color: AppTheme.muted,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 10),
          Text(
            value,
            textAlign: TextAlign.center,
            style: const TextStyle(
              color: AppTheme.ink,
              fontSize: 22,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            detail,
            textAlign: TextAlign.center,
            style: const TextStyle(
              color: AppTheme.muted,
              fontSize: 13,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
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
      width: 30,
      height: 30,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF60A5FA), AppTheme.brandBlueDark],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(7),
      ),
      child: Text(
        number,
        style: const TextStyle(
          color: Colors.white,
          fontSize: 18,
          fontWeight: FontWeight.w800,
        ),
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
