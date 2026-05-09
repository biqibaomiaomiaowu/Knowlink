import 'package:flutter/material.dart';

import '../../app/theme/app_theme.dart';
import '../../core/widgets/app_scaffold.dart';
import '../../core/widgets/knowlink_widgets.dart';

class QuizPage extends StatelessWidget {
  const QuizPage({
    required this.quizId,
    super.key,
  });

  final String quizId;

  @override
  Widget build(BuildContext context) {
    return AppScaffold(
      title: '测验',
      activeTab: KnowLinkTab.quiz,
      quizId: quizId,
      body: LayoutBuilder(
        builder: (context, constraints) {
          final wide = constraints.maxWidth >= 960;
          return SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const PageTitle(
                  title: '测验',
                  subtitle: '系统围绕当前学习模块，自动生成练习题并提供反馈，帮助你巩固知识、提升掌握度。',
                ),
                StatusPill(label: '测验编号：$quizId'),
                const SizedBox(height: 16),
                if (wide)
                  const Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(child: _QuestionCard()),
                      SizedBox(width: 16),
                      Expanded(child: _AnalysisCard()),
                    ],
                  )
                else
                  const Column(
                    children: [
                      _QuestionCard(),
                      SizedBox(height: 16),
                      _AnalysisCard(),
                    ],
                  ),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _QuestionCard extends StatelessWidget {
  const _QuestionCard();

  @override
  Widget build(BuildContext context) {
    return const SectionCard(
      padding: EdgeInsets.all(26),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              StatusPill(label: '单选题'),
              SizedBox(width: 18),
              Text(
                '2/10',
                style: TextStyle(
                  color: AppTheme.ink,
                  fontSize: 18,
                  fontWeight: FontWeight.w800,
                ),
              ),
              Spacer(),
              Icon(Icons.bookmark_border_rounded, color: AppTheme.muted),
              SizedBox(width: 6),
              Text(
                '标记',
                style: TextStyle(
                  color: AppTheme.muted,
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
          SizedBox(height: 32),
          Text(
            '在顺序栈（SqStack）中，执行一次入栈操作的时间复杂度为？',
            style: TextStyle(
              color: AppTheme.ink,
              fontSize: 24,
              fontWeight: FontWeight.w800,
            ),
          ),
          SizedBox(height: 30),
          _OptionTile(label: 'A', value: 'O(1)', selected: true),
          _OptionTile(label: 'B', value: 'O(n)'),
          _OptionTile(label: 'C', value: 'O(log n)'),
          _OptionTile(label: 'D', value: 'O(n log n)'),
          SizedBox(height: 22),
          _CorrectBox(),
        ],
      ),
    );
  }
}

class _OptionTile extends StatelessWidget {
  const _OptionTile({
    required this.label,
    required this.value,
    this.selected = false,
  });

  final String label;
  final String value;
  final bool selected;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 86,
      margin: const EdgeInsets.only(bottom: 22),
      padding: const EdgeInsets.symmetric(horizontal: 18),
      decoration: BoxDecoration(
        color: selected ? const Color(0xFFF8FBFF) : Colors.white,
        border: Border.all(
          color: selected ? AppTheme.brandBlue : AppTheme.line,
          width: selected ? 1.4 : 1,
        ),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          Container(
            width: 38,
            height: 38,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: selected ? AppTheme.brandBlue : Colors.white,
              border: Border.all(
                color: selected ? AppTheme.brandBlue : AppTheme.muted,
              ),
              shape: BoxShape.circle,
            ),
            child: Text(
              label,
              style: TextStyle(
                color: selected ? Colors.white : AppTheme.ink,
                fontWeight: FontWeight.w800,
                fontSize: 18,
              ),
            ),
          ),
          const SizedBox(width: 22),
          Expanded(
            child: Text(
              value,
              style: const TextStyle(
                color: AppTheme.ink,
                fontSize: 22,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          if (selected)
            Container(
              width: 36,
              height: 36,
              decoration: const BoxDecoration(
                color: AppTheme.brandBlue,
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.check, color: Colors.white, size: 22),
            ),
        ],
      ),
    );
  }
}

class _CorrectBox extends StatelessWidget {
  const _CorrectBox();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: const Color(0xFFF0FDF4),
        border: Border.all(color: const Color(0xFFBBF7D0)),
        borderRadius: BorderRadius.circular(8),
      ),
      child: const Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.check_circle, color: Color(0xFF16A34A)),
              SizedBox(width: 10),
              Text(
                '正确',
                style: TextStyle(
                  color: Color(0xFF16A34A),
                  fontSize: 24,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ],
          ),
          SizedBox(height: 14),
          Text(
            '正确答案： A',
            style: TextStyle(
              color: AppTheme.ink,
              fontSize: 18,
              fontWeight: FontWeight.w800,
            ),
          ),
          SizedBox(height: 10),
          Text(
            '你的回答： A',
            style: TextStyle(
              color: AppTheme.muted,
              fontSize: 18,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}

class _AnalysisCard extends StatelessWidget {
  const _AnalysisCard();

  @override
  Widget build(BuildContext context) {
    return const SectionCard(
      padding: EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _BlockTitle(title: '解析'),
          SizedBox(height: 12),
          Text(
            '顺序栈的入栈操作主要包括：\n'
            '1. 判断栈是否已满（S.top == MAX - 1）；\n'
            '2. 将元素插入栈顶（S.data[++S.top] = e）。\n'
            '以上操作均为常数时间操作，因此入栈的时间复杂度为 O(1)。',
            style: TextStyle(
              color: Color(0xFF334155),
              fontSize: 16,
              height: 1.65,
              fontWeight: FontWeight.w600,
            ),
          ),
          Divider(height: 28),
          _BlockTitle(title: '来源引用'),
          SizedBox(height: 14),
          Wrap(
            spacing: 14,
            runSpacing: 12,
            children: [
              SourceChip(icon: Icons.play_arrow, label: '视频\n05:32-06:10'),
              SourceChip(icon: Icons.description, label: '教材 PDF\n第 42 页'),
              SourceChip(icon: Icons.file_copy, label: '第 4 章课件 PPT\n第 12 页'),
            ],
          ),
          SizedBox(height: 14),
          Center(
            child: Text(
              '查看来源',
              style: TextStyle(
                color: AppTheme.brandBlue,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
          Divider(height: 28),
          _BlockTitle(title: '专业提示'),
          SizedBox(height: 12),
          _TipBox(),
          SizedBox(height: 18),
          _BlockTitle(title: '常见混淆点'),
          SizedBox(height: 10),
          Text(
            '• 将链式栈与顺序栈的时间复杂度混淆；\n'
            '• 忽略了顺序栈需要判断栈满的边界条件。',
            style: TextStyle(
              color: Color(0xFF334155),
              fontSize: 15,
              height: 1.6,
              fontWeight: FontWeight.w600,
            ),
          ),
          SizedBox(height: 16),
          _MasteryChange(),
          SizedBox(height: 12),
          _WeaknessBar(),
          SizedBox(height: 12),
          GradientButton(label: '加入复习优先级', onPressed: null),
        ],
      ),
    );
  }
}

class _BlockTitle extends StatelessWidget {
  const _BlockTitle({required this.title});

  final String title;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 4,
          height: 22,
          decoration: BoxDecoration(
            color: AppTheme.brandBlue,
            borderRadius: BorderRadius.circular(3),
          ),
        ),
        const SizedBox(width: 10),
        Text(
          title,
          style: const TextStyle(
            color: AppTheme.ink,
            fontSize: 20,
            fontWeight: FontWeight.w800,
          ),
        ),
      ],
    );
  }
}

class _TipBox extends StatelessWidget {
  const _TipBox();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FBFF),
        border: Border.all(color: const Color(0xFFBFDBFE)),
        borderRadius: BorderRadius.circular(8),
      ),
      child: const Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.lightbulb_outline, color: AppTheme.brandBlue),
          SizedBox(width: 12),
          Expanded(
            child: Text(
              '顺序栈的入栈和出栈操作都是 O(1)，但需要注意栈满和栈空的边界条件判断，这是避免越界错误的关键。',
              style: TextStyle(
                color: Color(0xFF334155),
                height: 1.5,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _MasteryChange extends StatelessWidget {
  const _MasteryChange();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        border: Border.all(color: AppTheme.line),
        borderRadius: BorderRadius.circular(8),
      ),
      child: const Row(
        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
        children: [
          _ScorePoint(value: '60%', label: '作答前'),
          Icon(Icons.trending_up, color: Color(0xFF16A34A), size: 34),
          _ScorePoint(
            value: '78%',
            label: '作答后',
            color: Color(0xFF16A34A),
          ),
        ],
      ),
    );
  }
}

class _ScorePoint extends StatelessWidget {
  const _ScorePoint({
    required this.value,
    required this.label,
    this.color = AppTheme.ink,
  });

  final String value;
  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(
          value,
          style: TextStyle(
            color: color,
            fontSize: 24,
            fontWeight: FontWeight.w900,
          ),
        ),
        Text(
          label,
          style: const TextStyle(
            color: AppTheme.muted,
            fontWeight: FontWeight.w700,
          ),
        ),
      ],
    );
  }
}

class _WeaknessBar extends StatelessWidget {
  const _WeaknessBar();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: const Color(0xFFFFFBEB),
        border: Border.all(color: const Color(0xFFFED7AA)),
        borderRadius: BorderRadius.circular(8),
      ),
      child: const Row(
        children: [
          Icon(Icons.auto_awesome, color: Color(0xFFF97316)),
          SizedBox(width: 10),
          Expanded(
            child: Text(
              '薄弱知识点：边界条件判断',
              style: TextStyle(
                color: Color(0xFF92400E),
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
          StatusPill(label: '错题强化', color: Color(0xFFF97316)),
        ],
      ),
    );
  }
}
