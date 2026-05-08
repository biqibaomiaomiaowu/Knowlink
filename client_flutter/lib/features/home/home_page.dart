import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/theme/app_theme.dart';
import '../../core/widgets/app_scaffold.dart';
import '../../core/widgets/knowlink_widgets.dart';

class HomePage extends StatelessWidget {
  const HomePage({super.key});

  @override
  Widget build(BuildContext context) {
    return AppScaffold(
      title: 'KnowLink',
      activeTab: KnowLinkTab.home,
      body: LayoutBuilder(
        builder: (context, constraints) {
          final isWide = constraints.maxWidth >= 920;
          final content =
              isWide ? const _HomeWideLayout() : const _HomeNarrowLayout();
          return SingleChildScrollView(child: content);
        },
      ),
    );
  }
}

class _HomeWideLayout extends StatelessWidget {
  const _HomeWideLayout();

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Row(
          children: [
            Expanded(
              child: _HeroActionCard(
                icon: Icons.cloud_upload_outlined,
                title: '自主导入',
                description: '支持上传课程视频与学习资料，\n快速构建你的专属学习库。',
                onTap: () => context.go('/import'),
              ),
            ),
            const SizedBox(width: 32),
            Expanded(
              child: _HeroActionCard(
                icon: Icons.star_border_rounded,
                title: '智能课程推荐',
                description: '基于学习目标和学习记录，\n为你推荐合适的课程内容。',
                onTap: () => context.go('/recommend'),
                tint: const Color(0xFF6366F1),
              ),
            ),
          ],
        ),
        const SizedBox(height: 30),
        const Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(child: _RecentLearningCard()),
            SizedBox(width: 32),
            Expanded(child: _KnowledgeListCard()),
          ],
        ),
        const SizedBox(height: 30),
        const Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(child: _StatsCard()),
            SizedBox(width: 32),
            Expanded(child: _ReviewPromptCard()),
          ],
        ),
      ],
    );
  }
}

class _HomeNarrowLayout extends StatelessWidget {
  const _HomeNarrowLayout();

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        _HeroActionCard(
          icon: Icons.cloud_upload_outlined,
          title: '自主导入',
          description: '支持上传课程视频与学习资料，快速构建你的专属学习库。',
          onTap: () => context.go('/import'),
        ),
        const SizedBox(height: 16),
        _HeroActionCard(
          icon: Icons.star_border_rounded,
          title: '智能课程推荐',
          description: '基于学习目标和学习记录，为你推荐合适的课程内容。',
          onTap: () => context.go('/recommend'),
          tint: const Color(0xFF6366F1),
        ),
        const SizedBox(height: 16),
        const _RecentLearningCard(),
        const SizedBox(height: 16),
        const _KnowledgeListCard(),
        const SizedBox(height: 16),
        const _StatsCard(),
        const SizedBox(height: 16),
        const _ReviewPromptCard(),
      ],
    );
  }
}

class _HeroActionCard extends StatelessWidget {
  const _HeroActionCard({
    required this.icon,
    required this.title,
    required this.description,
    this.onTap,
    this.tint = AppTheme.brandBlue,
  });

  final IconData icon;
  final String title;
  final String description;
  final VoidCallback? onTap;
  final Color tint;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final compact = constraints.maxWidth < 560;
        final iconSize = compact ? 74.0 : 134.0;
        final iconGlyphSize = compact ? 40.0 : 68.0;
        final titleSize = compact ? 24.0 : 32.0;
        final descriptionSize = compact ? 15.0 : 18.0;

        return SectionCard(
          padding: EdgeInsets.symmetric(
            horizontal: compact ? 20 : 42,
            vertical: compact ? 20 : 26,
          ),
          child: InkWell(
            onTap: onTap,
            borderRadius: BorderRadius.circular(8),
            child: Row(
              children: [
                Container(
                  width: iconSize,
                  height: iconSize,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: tint.withValues(alpha: 0.1),
                    shape: BoxShape.circle,
                  ),
                  child: Icon(icon, color: tint, size: iconGlyphSize),
                ),
                SizedBox(width: compact ? 18 : 48),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        title,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          color: AppTheme.ink,
                          fontSize: titleSize,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      SizedBox(height: compact ? 8 : 14),
                      Text(
                        description,
                        maxLines: compact ? 3 : 4,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          color: AppTheme.muted,
                          fontSize: descriptionSize,
                          height: 1.45,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                ),
                if (!compact) ...[
                  const SizedBox(width: 12),
                  const Icon(
                    Icons.chevron_right_rounded,
                    color: Color(0xFF94A3B8),
                    size: 44,
                  ),
                ],
              ],
            ),
          ),
        );
      },
    );
  }
}

class _RecentLearningCard extends StatelessWidget {
  const _RecentLearningCard();

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionHeader(
            title: '最近学习',
            action: '查看更多',
          ),
          const SizedBox(height: 28),
          LayoutBuilder(
            builder: (context, constraints) {
              final compact = constraints.maxWidth < 420;
              final cover = _RecentCourseCover(compact: compact);
              const details = _RecentLearningDetails();

              if (compact) {
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    cover,
                    const SizedBox(height: 18),
                    details,
                  ],
                );
              }

              return Row(
                children: [
                  cover,
                  const SizedBox(width: 28),
                  const Expanded(child: details),
                ],
              );
            },
          ),
        ],
      ),
    );
  }
}

class _RecentCourseCover extends StatelessWidget {
  const _RecentCourseCover({required this.compact});

  final bool compact;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: compact ? double.infinity : 196,
      height: compact ? 150 : 196,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(8),
        gradient: const LinearGradient(
          colors: [Color(0xFF0F172A), Color(0xFF123B78)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      ),
      child: Stack(
        children: [
          Positioned(
            left: compact ? 22 : 25,
            top: compact ? 30 : 45,
            child: Text(
              'C',
              style: TextStyle(
                color: Colors.white,
                fontSize: compact ? 62 : 78,
                fontWeight: FontWeight.w900,
              ),
            ),
          ),
          Positioned(
            left: compact ? 86 : 96,
            top: compact ? 56 : 82,
            child: Text(
              '数据结构',
              style: TextStyle(
                color: Colors.white,
                fontSize: compact ? 22 : 24,
                fontWeight: FontWeight.w900,
              ),
            ),
          ),
          const Positioned(
            right: 20,
            bottom: 28,
            child: StatusPill(label: 'C语言版', color: Colors.white),
          ),
        ],
      ),
    );
  }
}

class _RecentLearningDetails extends StatelessWidget {
  const _RecentLearningDetails();

  @override
  Widget build(BuildContext context) {
    return const Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '数据结构（C语言版）',
          style: TextStyle(
            color: AppTheme.ink,
            fontSize: 24,
            fontWeight: FontWeight.w800,
          ),
        ),
        SizedBox(height: 16),
        Text(
          '已学 7 章 / 共 10 章',
          style: TextStyle(
            color: AppTheme.muted,
            fontSize: 16,
            fontWeight: FontWeight.w600,
          ),
        ),
        SizedBox(height: 24),
        Row(
          children: [
            Expanded(child: ProgressRail(value: 0.76)),
            SizedBox(width: 28),
            Text(
              '76%',
              style: TextStyle(
                color: AppTheme.muted,
                fontSize: 20,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ),
        SizedBox(height: 26),
        Wrap(
          spacing: 18,
          runSpacing: 12,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            Text(
              '上次学习： 2024-05-20  20:30',
              style: TextStyle(
                color: AppTheme.muted,
                fontSize: 16,
                fontWeight: FontWeight.w600,
              ),
            ),
            OutlinedButton(
              onPressed: null,
              child: Text('继续学习'),
            ),
          ],
        ),
      ],
    );
  }
}

class _KnowledgeListCard extends StatelessWidget {
  const _KnowledgeListCard();

  @override
  Widget build(BuildContext context) {
    return const SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _SectionHeader(title: '今日推荐知识点'),
          SizedBox(height: 18),
          _KnowledgeRow(
            icon: Icons.account_tree_outlined,
            title: '链表的定义与基本操作',
            meta: '数据结构（C语言版） · 第 3 章',
          ),
          _KnowledgeRow(
            icon: Icons.layers_outlined,
            title: '栈的应用：括号匹配',
            meta: '数据结构（C语言版） · 第 4 章',
          ),
          _KnowledgeRow(
            icon: Icons.device_hub_outlined,
            title: '二叉树的遍历（前序/中序/后序）',
            meta: '数据结构（C语言版） · 第 5 章',
          ),
        ],
      ),
    );
  }
}

class _KnowledgeRow extends StatelessWidget {
  const _KnowledgeRow({
    required this.icon,
    required this.title,
    required this.meta,
  });

  final IconData icon;
  final String title;
  final String meta;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 10),
      child: Row(
        children: [
          SoftIcon(icon: icon, size: 64),
          const SizedBox(width: 22),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    color: AppTheme.ink,
                    fontSize: 18,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 7),
                Text(
                  meta,
                  style: const TextStyle(
                    color: AppTheme.muted,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          ),
          const Icon(Icons.chevron_right_rounded, color: AppTheme.muted),
        ],
      ),
    );
  }
}

class _StatsCard extends StatelessWidget {
  const _StatsCard();

  @override
  Widget build(BuildContext context) {
    return const SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _SectionHeader(title: '学习统计'),
          SizedBox(height: 22),
          Row(
            children: [
              Expanded(
                child: MetricBox(
                  icon: Icons.schedule_rounded,
                  label: '总学习时长',
                  value: '128 h 36 min',
                  detail: '较上周 ↑ 18.6%',
                ),
              ),
              SizedBox(width: 24),
              Expanded(
                child: MetricBox(
                  icon: Icons.check_circle_outline,
                  label: '课程完成度',
                  value: '8 / 12',
                  detail: '66.7%',
                  color: Color(0xFF22C55E),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _ReviewPromptCard extends StatelessWidget {
  const _ReviewPromptCard();

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      child: Row(
        children: [
          const Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _SectionHeader(title: 'AI 复习推荐'),
                SizedBox(height: 20),
                Text(
                  '根据你的学习情况，AI 为你生成了个性化复习计划，巩固薄弱知识点，提升学习效果。',
                  style: TextStyle(
                    color: AppTheme.muted,
                    fontSize: 16,
                    height: 1.7,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                SizedBox(height: 28),
                SizedBox(
                  width: 140,
                  child: GradientButton(
                    label: '去复习',
                    onPressed: null,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 24),
          Container(
            width: 132,
            height: 132,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: const Color(0xFFEFF6FF),
              borderRadius: BorderRadius.circular(66),
            ),
            child: const Icon(
              Icons.smart_toy_outlined,
              color: AppTheme.brandBlue,
              size: 78,
            ),
          ),
        ],
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({
    required this.title,
    this.action,
  });

  final String title;
  final String? action;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Text(
            title,
            style: const TextStyle(
              color: AppTheme.ink,
              fontSize: 23,
              fontWeight: FontWeight.w800,
            ),
          ),
        ),
        if (action != null)
          TextButton.icon(
            onPressed: null,
            label: Text(action!),
            icon: const Icon(Icons.chevron_right_rounded),
            iconAlignment: IconAlignment.end,
          ),
      ],
    );
  }
}
