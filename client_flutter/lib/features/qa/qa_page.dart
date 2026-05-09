import 'package:flutter/material.dart';

import '../../app/theme/app_theme.dart';
import '../../core/widgets/app_scaffold.dart';
import '../../core/widgets/knowlink_widgets.dart';

class QaPage extends StatelessWidget {
  const QaPage({
    required this.courseId,
    required this.sessionId,
    super.key,
  });

  final String courseId;
  final String sessionId;

  @override
  Widget build(BuildContext context) {
    return AppScaffold(
      title: 'AI 思考问答',
      activeTab: KnowLinkTab.inquiry,
      courseId: courseId,
      body: LayoutBuilder(
        builder: (context, constraints) {
          final wide = constraints.maxWidth >= 1050;
          return SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const PageTitle(
                  title: 'AI 思考问答',
                  subtitle: '基于当前知识点、视频片段和资料引用，进行可追溯的学习追问。',
                ),
                if (wide)
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(flex: 2, child: _CourseOutline(courseId)),
                      const SizedBox(width: 16),
                      const Expanded(flex: 4, child: _LearningContext()),
                      const SizedBox(width: 16),
                      Expanded(flex: 3, child: _QaPanel(sessionId)),
                    ],
                  )
                else
                  Column(
                    children: [
                      _CourseOutline(courseId),
                      const SizedBox(height: 16),
                      const _LearningContext(),
                      const SizedBox(height: 16),
                      _QaPanel(sessionId),
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

class _CourseOutline extends StatelessWidget {
  const _CourseOutline(this.courseId);

  final String courseId;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Expanded(
                child: Text(
                  '讲义结构',
                  style: TextStyle(
                    color: AppTheme.ink,
                    fontSize: 20,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              StatusPill(label: '课程 $courseId'),
            ],
          ),
          const Divider(height: 18),
          const _OutlineStatusRow(
            icon: Icons.menu_book_outlined,
            title: '课程结构',
            detail: '暂无已同步的讲义结构。',
          ),
          const _OutlineStatusRow(
            icon: Icons.center_focus_strong_outlined,
            title: '当前知识点',
            detail: '暂无已绑定的知识点上下文。',
          ),
          const _OutlineStatusRow(
            icon: Icons.link_outlined,
            title: '来源引用',
            detail: '暂无来自会话的引用记录。',
          ),
          const SizedBox(height: 12),
          Text(
            '课程编号：$courseId',
            style: const TextStyle(
              color: AppTheme.muted,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}

class _OutlineStatusRow extends StatelessWidget {
  const _OutlineStatusRow({
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
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppTheme.line),
      ),
      child: Row(
        children: [
          SoftIcon(icon: icon, size: 38),
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
                Text(
                  detail,
                  style: const TextStyle(
                    color: AppTheme.muted,
                    height: 1.35,
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

class _LearningContext extends StatelessWidget {
  const _LearningContext();

  @override
  Widget build(BuildContext context) {
    return const Column(
      children: [
        _VideoCard(),
        SizedBox(height: 16),
        _KnowledgeTabs(),
      ],
    );
  }
}

class _VideoCard extends StatelessWidget {
  const _VideoCard();

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Expanded(
                child: Text(
                  '当前学习上下文',
                  style: TextStyle(
                    color: AppTheme.ink,
                    fontSize: 24,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
              StatusPill(label: '等待会话'),
              SizedBox(width: 12),
              StatusPill(label: '未绑定资料', color: Color(0xFF64748B)),
            ],
          ),
          const SizedBox(height: 22),
          Container(
            height: 470,
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: const Color(0xFF070A0F),
              borderRadius: BorderRadius.circular(8),
            ),
            child: const Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Expanded(
                  child: _DarkEmptyPanel(
                    icon: Icons.play_circle_outline,
                    title: '暂无当前视频片段',
                    detail: '进入真实课程讲义或问询流程后，将展示本会话绑定的学习位置。',
                  ),
                ),
                SizedBox(width: 24),
                Expanded(
                  child: _DarkEmptyPanel(
                    icon: Icons.description_outlined,
                    title: '暂无资料片段',
                    detail: '真实来源引用会随会话消息一起展示，不在这里预填示例内容。',
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          const Row(
            children: [
              Icon(Icons.play_arrow, color: AppTheme.ink),
              SizedBox(width: 10),
              Text('--:-- / --:--', style: TextStyle(color: AppTheme.ink)),
              SizedBox(width: 16),
              Expanded(child: ProgressRail(value: 0)),
              SizedBox(width: 18),
              Text('1.0x', style: TextStyle(color: AppTheme.ink)),
              SizedBox(width: 16),
              Icon(Icons.volume_up_outlined, color: AppTheme.ink),
              SizedBox(width: 16),
              Icon(Icons.fullscreen_rounded, color: AppTheme.ink),
            ],
          ),
        ],
      ),
    );
  }
}

class _DarkEmptyPanel extends StatelessWidget {
  const _DarkEmptyPanel({
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
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        color: const Color(0xFF151A21),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xFF1F2937)),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, color: const Color(0xFF93C5FD), size: 54),
          const SizedBox(height: 18),
          Text(
            title,
            textAlign: TextAlign.center,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 20,
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 10),
          Text(
            detail,
            textAlign: TextAlign.center,
            style: const TextStyle(
              color: Color(0xFFCBD5E1),
              height: 1.55,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}

class _KnowledgeTabs extends StatelessWidget {
  const _KnowledgeTabs();

  @override
  Widget build(BuildContext context) {
    return const SectionCard(
      padding: EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              _TabLabel('知识点解析', active: true),
              _TabLabel('例题讲解'),
              _TabLabel('关联题'),
              _TabLabel('扩展阅读'),
            ],
          ),
          Divider(height: 26),
          Text(
            '知识点解析',
            style: TextStyle(
              color: AppTheme.ink,
              fontSize: 20,
              fontWeight: FontWeight.w800,
            ),
          ),
          SizedBox(height: 12),
          _ContextEmptyBox(
            icon: Icons.psychology_alt_outlined,
            title: '暂无可展示的知识点解析',
            detail: '该独立会话页不会预填课程内容或来源引用。',
          ),
        ],
      ),
    );
  }
}

class _TabLabel extends StatelessWidget {
  const _TabLabel(this.label, {this.active = false});

  final String label;
  final bool active;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(right: 28),
      padding: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        border: Border(
          bottom: BorderSide(
            color: active ? AppTheme.brandBlue : Colors.transparent,
            width: 2,
          ),
        ),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: active ? AppTheme.brandBlue : AppTheme.ink,
          fontWeight: FontWeight.w800,
        ),
      ),
    );
  }
}

class _QaPanel extends StatelessWidget {
  const _QaPanel(this.sessionId);

  final String sessionId;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        SectionCard(
          padding: const EdgeInsets.all(18),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Row(
                children: [
                  Icon(Icons.smart_toy_outlined, color: AppTheme.muted),
                  SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      'AI 思考问答（基于当前知识点）',
                      style: TextStyle(
                        color: AppTheme.ink,
                        fontSize: 18,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 18),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: const Color(0xFFF8FAFC),
                  border: Border.all(color: AppTheme.line),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '暂无会话消息',
                      style: TextStyle(
                        color: AppTheme.ink,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    SizedBox(height: 6),
                    Text(
                      '等待本会话的真实消息与来源引用。',
                      style: TextStyle(
                        color: AppTheme.muted,
                        height: 1.45,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 12),
              Container(
                height: 42,
                padding: const EdgeInsets.symmetric(horizontal: 12),
                decoration: BoxDecoration(
                  color: const Color(0xFFF8FAFC),
                  border: Border.all(color: AppTheme.line),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Row(
                  children: [
                    Expanded(
                      child: Text(
                        '继续提问...',
                        style: TextStyle(color: Color(0xFF94A3B8)),
                      ),
                    ),
                    IconButton(
                      tooltip: '发送',
                      onPressed: null,
                      icon: Icon(
                        Icons.send_rounded,
                        color: AppTheme.muted,
                        size: 20,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'QA 会话：$sessionId',
                style: const TextStyle(
                  color: AppTheme.muted,
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        _SessionContextPanel(sessionId),
      ],
    );
  }
}

class _SessionContextPanel extends StatelessWidget {
  const _SessionContextPanel(this.sessionId);

  final String sessionId;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Expanded(
                child: Text(
                  '会话上下文',
                  style: TextStyle(
                    color: AppTheme.ink,
                    fontSize: 20,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          _ContextEmptyBox(
            icon: Icons.forum_outlined,
            title: '会话编号',
            detail: sessionId,
          ),
          const SizedBox(height: 12),
          const _ContextEmptyBox(
            icon: Icons.link_off_outlined,
            title: '暂无来源定位',
            detail: '来源跳转只在真实引用返回后启用。',
            color: Color(0xFF64748B),
          ),
          const SizedBox(height: 12),
          const _ContextEmptyBox(
            icon: Icons.quiz_outlined,
            title: '暂无练习入口',
            detail: '练习推荐需要真实知识点上下文。',
            color: Color(0xFF7C3AED),
          ),
        ],
      ),
    );
  }
}

class _ContextEmptyBox extends StatelessWidget {
  const _ContextEmptyBox({
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
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        border: Border.all(color: AppTheme.line),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          SoftIcon(icon: icon, color: color, size: 46),
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
                const SizedBox(height: 5),
                Text(
                  detail,
                  maxLines: 3,
                  overflow: TextOverflow.ellipsis,
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
