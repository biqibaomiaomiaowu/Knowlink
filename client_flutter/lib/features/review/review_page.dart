import 'package:flutter/material.dart';

import '../../app/theme/app_theme.dart';
import '../../core/widgets/app_scaffold.dart';
import '../../core/widgets/knowlink_widgets.dart';

class ReviewPage extends StatelessWidget {
  const ReviewPage({
    required this.courseId,
    super.key,
  });

  final String courseId;

  @override
  Widget build(BuildContext context) {
    return AppScaffold(
      title: 'AI 复习推荐',
      activeTab: KnowLinkTab.review,
      courseId: courseId,
      body: LayoutBuilder(
        builder: (context, constraints) {
          final wide = constraints.maxWidth >= 1100;
          return SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Expanded(
                      child: PageTitle(
                        title: 'AI 复习推荐',
                        subtitle: '系统根据你的掌握度、错题情况、考试时间和回看记录，为你智能推荐今天最值得复习的内容。',
                      ),
                    ),
                    OutlinedButton.icon(
                      onPressed: () {},
                      icon: const Icon(Icons.history_rounded),
                      label: const Text('复习记录'),
                    ),
                  ],
                ),
                if (wide) const _ReviewWide() else const _ReviewNarrow(),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _ReviewWide extends StatelessWidget {
  const _ReviewWide();

  @override
  Widget build(BuildContext context) {
    return const Column(
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(flex: 3, child: _TopKnowledgeCard()),
            SizedBox(width: 16),
            Expanded(flex: 2, child: _ReasonCard()),
            SizedBox(width: 16),
            Expanded(flex: 3, child: _ResourceCard()),
            SizedBox(width: 16),
            Expanded(flex: 2, child: _ExerciseCard()),
          ],
        ),
        SizedBox(height: 16),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(child: _RouteCard()),
            SizedBox(width: 16),
            Expanded(child: _IntensityCard()),
          ],
        ),
      ],
    );
  }
}

class _ReviewNarrow extends StatelessWidget {
  const _ReviewNarrow();

  @override
  Widget build(BuildContext context) {
    return const Column(
      children: [
        _TopKnowledgeCard(),
        SizedBox(height: 16),
        _ReasonCard(),
        SizedBox(height: 16),
        _ResourceCard(),
        SizedBox(height: 16),
        _ExerciseCard(),
        SizedBox(height: 16),
        _RouteCard(),
        SizedBox(height: 16),
        _IntensityCard(),
      ],
    );
  }
}

class _TopKnowledgeCard extends StatelessWidget {
  const _TopKnowledgeCard();

  @override
  Widget build(BuildContext context) {
    return const SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _CardTitle('今日最该复习的知识点 TOP3'),
          SizedBox(height: 22),
          _KnowledgeRank(
            rank: '1',
            title: '栈（Stack）与递归',
            tag: '数据结构',
            mastery: '60%',
            errors: '8',
            color: Color(0xFFFACC15),
          ),
          SizedBox(height: 16),
          _KnowledgeRank(
            rank: '2',
            title: '动态规划 - 状态转移方程',
            tag: '算法',
            mastery: '55%',
            errors: '6',
            color: Color(0xFF94A3B8),
          ),
          SizedBox(height: 16),
          _KnowledgeRank(
            rank: '3',
            title: '二叉树的遍历',
            tag: '数据结构',
            mastery: '65%',
            errors: '5',
            color: Color(0xFFF97316),
          ),
        ],
      ),
    );
  }
}

class _KnowledgeRank extends StatelessWidget {
  const _KnowledgeRank({
    required this.rank,
    required this.title,
    required this.tag,
    required this.mastery,
    required this.errors,
    required this.color,
  });

  final String rank;
  final String title;
  final String tag;
  final String mastery;
  final String errors;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        border: Border.all(color: AppTheme.line),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          Container(
            width: 38,
            height: 38,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: color,
              borderRadius: BorderRadius.circular(7),
            ),
            child: Text(
              rank,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 22,
                fontWeight: FontWeight.w900,
              ),
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Wrap(
                  spacing: 8,
                  runSpacing: 6,
                  children: [
                    Text(
                      title,
                      style: const TextStyle(
                        color: AppTheme.ink,
                        fontWeight: FontWeight.w800,
                        fontSize: 16,
                      ),
                    ),
                    StatusPill(label: tag),
                  ],
                ),
                const SizedBox(height: 9),
                Text(
                  '掌握度：$mastery    错题数：$errors',
                  style: const TextStyle(
                    color: AppTheme.muted,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
          ),
          SizedBox(
            width: 48,
            height: 48,
            child: CircularProgressIndicator(
              value: double.parse(mastery.replaceAll('%', '')) / 100,
              strokeWidth: 3,
              color: AppTheme.brandBlue,
              backgroundColor: const Color(0xFFEFF2F7),
            ),
          ),
        ],
      ),
    );
  }
}

class _ReasonCard extends StatelessWidget {
  const _ReasonCard();

  @override
  Widget build(BuildContext context) {
    return const SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _CardTitle('推荐原因'),
          SizedBox(height: 24),
          _ReasonRow(
            icon: Icons.track_changes,
            title: '掌握度较低',
            detail: '知识点掌握度低于 70%',
            color: Color(0xFFF97316),
          ),
          _ReasonRow(
            icon: Icons.cancel_outlined,
            title: '错题较多',
            detail: '近期错题数较多',
            color: Color(0xFFEF4444),
          ),
          _ReasonRow(
            icon: Icons.calendar_month_outlined,
            title: '考试临近',
            detail: '距离考试还有 9 天',
            color: Color(0xFF22C55E),
          ),
          _ReasonRow(
            icon: Icons.play_circle_outline,
            title: '回看重点',
            detail: '近期回看过相关片段',
          ),
        ],
      ),
    );
  }
}

class _ReasonRow extends StatelessWidget {
  const _ReasonRow({
    required this.icon,
    required this.title,
    required this.detail,
    this.color = AppTheme.brandBlue,
  });

  final IconData icon;
  final String title;
  final String detail;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 22),
      child: Row(
        children: [
          SoftIcon(icon: icon, color: color, size: 44),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    color: AppTheme.ink,
                    fontWeight: FontWeight.w800,
                    fontSize: 16,
                  ),
                ),
                const SizedBox(height: 5),
                Text(
                  detail,
                  style: const TextStyle(
                    color: AppTheme.muted,
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

class _ResourceCard extends StatelessWidget {
  const _ResourceCard();

  @override
  Widget build(BuildContext context) {
    return const SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _CardTitle('推荐回看片段 / 复习资源推荐'),
          SizedBox(height: 20),
          _ResourceRow(
            duration: '12:45',
            title: '栈的基本操作与应用',
            meta: '第 3 章 栈与队列',
            source: '来源：视频 12:45 · 讲义 4.1.2',
            count: '回看 2 次',
          ),
          _ResourceRow(
            duration: '15:32',
            title: '动态规划状态设计技巧',
            meta: '第 6 章 动态规划',
            source: '来源：视频 15:32 · 讲义 6.3',
            count: '回看 1 次',
          ),
          _ResourceRow(
            duration: '10:18',
            title: '二叉树遍历详解',
            meta: '第 4 章 树',
            source: '来源：视频 10:18 · 教材 PDF 第 86 页',
            count: '回看 3 次',
          ),
        ],
      ),
    );
  }
}

class _ResourceRow extends StatelessWidget {
  const _ResourceRow({
    required this.duration,
    required this.title,
    required this.meta,
    required this.source,
    required this.count,
  });

  final String duration;
  final String title;
  final String meta;
  final String source;
  final String count;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 18),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 96,
            height: 72,
            alignment: Alignment.bottomRight,
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: const Color(0xFF111827),
              borderRadius: BorderRadius.circular(6),
            ),
            child: Text(
              duration,
              style: const TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    color: AppTheme.ink,
                    fontWeight: FontWeight.w800,
                    fontSize: 16,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  meta,
                  style: const TextStyle(
                    color: AppTheme.muted,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  runSpacing: 6,
                  children: [
                    StatusPill(label: source),
                    Text(
                      count,
                      style: const TextStyle(
                        color: AppTheme.brandBlue,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ExerciseCard extends StatelessWidget {
  const _ExerciseCard();

  @override
  Widget build(BuildContext context) {
    return const SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _CardTitle('推荐再练题目 / 复习路线建议'),
          SizedBox(height: 18),
          _ExerciseRow(
            number: '1',
            title: '有效的括号',
            difficulty: '简单',
            meta: '课程测验题 20\n正确率 45%',
          ),
          _ExerciseRow(
            number: '2',
            title: '最长递增子序列',
            difficulty: '中等',
            meta: '讲义关联题 08\n正确率 38%',
            color: Color(0xFFF97316),
          ),
          _ExerciseRow(
            number: '3',
            title: '二叉树的层序遍历',
            difficulty: '简单',
            meta: '资料例题 12\n正确率 62%',
          ),
          Center(
            child: Text(
              '查看更多练习题  →',
              style: TextStyle(
                color: AppTheme.brandBlue,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ExerciseRow extends StatelessWidget {
  const _ExerciseRow({
    required this.number,
    required this.title,
    required this.difficulty,
    required this.meta,
    this.color = const Color(0xFF22C55E),
  });

  final String number;
  final String title;
  final String difficulty;
  final String meta;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        border: Border.all(color: AppTheme.line),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          StatusPill(label: number),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Wrap(
                  spacing: 8,
                  children: [
                    Text(
                      title,
                      style: const TextStyle(
                        color: AppTheme.ink,
                        fontWeight: FontWeight.w800,
                        fontSize: 16,
                      ),
                    ),
                    StatusPill(label: difficulty, color: color),
                  ],
                ),
                const SizedBox(height: 10),
                Text(
                  meta,
                  style: const TextStyle(
                    color: AppTheme.muted,
                    height: 1.6,
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

class _RouteCard extends StatelessWidget {
  const _RouteCard();

  @override
  Widget build(BuildContext context) {
    return const SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _CardTitle('复习路线建议 / 复习顺序'),
          SizedBox(height: 24),
          Row(
            children: [
              Expanded(
                child: _RouteStep(
                  number: '1',
                  icon: Icons.play_circle_outline,
                  title: '第一步',
                  detail: '回看知识点视频\n建议用时 20 分钟',
                ),
              ),
              _RouteArrow(),
              Expanded(
                child: _RouteStep(
                  number: '2',
                  icon: Icons.quiz_outlined,
                  title: '第二步',
                  detail: '完成推荐练习题\n建议用时 30 分钟',
                ),
              ),
              _RouteArrow(),
              Expanded(
                child: _RouteStep(
                  number: '3',
                  icon: Icons.edit_note_rounded,
                  title: '第三步',
                  detail: '错题巩固与总结\n建议用时 15 分钟',
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _RouteStep extends StatelessWidget {
  const _RouteStep({
    required this.number,
    required this.icon,
    required this.title,
    required this.detail,
  });

  final String number;
  final IconData icon;
  final String title;
  final String detail;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 190,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        border: Border.all(color: AppTheme.line),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Stack(
        children: [
          StatusPill(label: number),
          Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(icon, color: AppTheme.muted, size: 48),
                const SizedBox(height: 14),
                Text(
                  title,
                  style: const TextStyle(
                    color: AppTheme.ink,
                    fontWeight: FontWeight.w800,
                    fontSize: 17,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  detail,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    color: AppTheme.muted,
                    height: 1.5,
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

class _RouteArrow extends StatelessWidget {
  const _RouteArrow();

  @override
  Widget build(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.symmetric(horizontal: 14),
      child: Icon(Icons.arrow_forward_ios_rounded, color: Color(0xFFCBD5E1)),
    );
  }
}

class _IntensityCard extends StatelessWidget {
  const _IntensityCard();

  @override
  Widget build(BuildContext context) {
    return const SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _CardTitle('调整复习强度'),
          SizedBox(height: 4),
          Text(
            '根据你的时间和状态，自定义本轮复习的强度',
            style: TextStyle(
              color: AppTheme.muted,
              fontWeight: FontWeight.w600,
            ),
          ),
          SizedBox(height: 24),
          Row(
            children: [
              Expanded(
                child: _ModeTile(
                  title: '轻松模式',
                  detail: '重点回看 + 少量练习\n约 30 分钟',
                ),
              ),
              SizedBox(width: 18),
              Expanded(
                child: _ModeTile(
                  title: '标准模式',
                  detail: '回看 + 练习 + 错题巩固\n约 60 分钟',
                  selected: true,
                ),
              ),
              SizedBox(width: 18),
              Expanded(
                child: _ModeTile(
                  title: '强化模式',
                  detail: '深入练习 + 拓展提升\n约 90 分钟',
                ),
              ),
            ],
          ),
          SizedBox(height: 28),
          GradientButton(
              label: '开始本轮复习', icon: Icons.play_circle, onPressed: null),
        ],
      ),
    );
  }
}

class _ModeTile extends StatelessWidget {
  const _ModeTile({
    required this.title,
    required this.detail,
    this.selected = false,
  });

  final String title;
  final String detail;
  final bool selected;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minHeight: 132),
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: selected ? const Color(0xFFF8FBFF) : Colors.white,
        border: Border.all(
          color: selected ? AppTheme.brandBlue : AppTheme.line,
          width: selected ? 1.4 : 1,
        ),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Stack(
        children: [
          if (selected)
            const Positioned(
              right: 0,
              top: 0,
              child: Icon(Icons.check_circle, color: AppTheme.brandBlue),
            ),
          Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    color: AppTheme.ink,
                    fontWeight: FontWeight.w800,
                    fontSize: 16,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  detail,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    color: AppTheme.muted,
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

class _CardTitle extends StatelessWidget {
  const _CardTitle(this.title);

  final String title;

  @override
  Widget build(BuildContext context) {
    return Text(
      title,
      style: const TextStyle(
        color: AppTheme.ink,
        fontSize: 20,
        fontWeight: FontWeight.w800,
      ),
    );
  }
}
