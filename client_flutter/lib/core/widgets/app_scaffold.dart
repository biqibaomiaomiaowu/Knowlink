import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/theme/app_theme.dart';
import 'knowlink_widgets.dart';

enum KnowLinkTab {
  home,
  library,
  workspace,
  lesson,
  test,
  chat,
  review,
  import,
  recommend,
  parse,
  inquiry,
  handout,
  quiz,
}

class AppScaffold extends StatelessWidget {
  const AppScaffold({
    required this.title,
    required this.body,
    this.subtitle,
    this.activeTab,
    this.courseId,
    this.lessonId,
    this.quizId,
    super.key,
  });

  final String title;
  final String? subtitle;
  final Widget body;
  final KnowLinkTab? activeTab;
  final String? courseId;
  final String? lessonId;
  final String? quizId;

  @override
  Widget build(BuildContext context) {
    final tab = activeTab ?? _tabFromTitle(title);
    return Scaffold(
      backgroundColor: AppTheme.page,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 1520),
              child: DecoratedBox(
                decoration: BoxDecoration(
                  color: AppTheme.surface,
                  borderRadius: BorderRadius.circular(36),
                  boxShadow: AppTheme.raisedShadow,
                ),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(36),
                  child: LayoutBuilder(
                    builder: (context, constraints) {
                      final isDesktop = constraints.maxWidth >= 900;
                      return Column(
                        children: [
                          _KnowLinkTopbar(
                            activeTab: tab,
                            courseId: courseId,
                            lessonId: lessonId,
                            showMobileNav: !isDesktop,
                          ),
                          Expanded(
                            child: isDesktop
                                ? Row(
                                    children: [
                                      _Sidebar(
                                        activeTab: tab,
                                        courseId: courseId,
                                        lessonId: lessonId,
                                      ),
                                      Expanded(child: _Content(child: body)),
                                    ],
                                  )
                                : _Content(child: body),
                          ),
                        ],
                      );
                    },
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  KnowLinkTab _tabFromTitle(String title) {
    if (title.contains('课程库')) {
      return KnowLinkTab.library;
    }
    if (title.contains('工作区') || title.contains('工作台')) {
      return KnowLinkTab.workspace;
    }
    if (title.contains('课时') || title.contains('讲义')) {
      return KnowLinkTab.lesson;
    }
    if (title.contains('测验') || title.contains('测试')) {
      return KnowLinkTab.test;
    }
    if (title.contains('问答') || title.contains('QA')) {
      return KnowLinkTab.chat;
    }
    if (title.contains('复习')) {
      return KnowLinkTab.review;
    }
    return KnowLinkTab.home;
  }
}

class _KnowLinkTopbar extends StatelessWidget {
  const _KnowLinkTopbar({
    required this.activeTab,
    required this.courseId,
    required this.lessonId,
    required this.showMobileNav,
  });

  final KnowLinkTab activeTab;
  final String? courseId;
  final String? lessonId;
  final bool showMobileNav;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: const BoxDecoration(
        color: AppTheme.surface,
        boxShadow: [
          BoxShadow(
            color: Color(0x99A3B1C6),
            blurRadius: 6,
            offset: Offset(3, 3),
            blurStyle: BlurStyle.inner,
          ),
          BoxShadow(
            color: Color(0x85FFFFFF),
            blurRadius: 6,
            offset: Offset(-3, -3),
            blurStyle: BlurStyle.inner,
          ),
        ],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const SizedBox(
            height: 78,
            child: Padding(
              padding: EdgeInsets.symmetric(horizontal: 24),
              child: Row(
                children: [
                  _Logo(),
                  SizedBox(width: 16),
                  Expanded(
                    child: Text(
                      'KnowLink',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: AppTheme.text,
                        fontSize: 30,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 0,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
          if (showMobileNav)
            _MobileNav(
              activeTab: activeTab,
              courseId: courseId,
              lessonId: lessonId,
            ),
        ],
      ),
    );
  }
}

class _Sidebar extends StatelessWidget {
  const _Sidebar({
    required this.activeTab,
    required this.courseId,
    required this.lessonId,
  });

  final KnowLinkTab activeTab;
  final String? courseId;
  final String? lessonId;

  @override
  Widget build(BuildContext context) {
    final items = _navItems(courseId: courseId, lessonId: lessonId);
    return SizedBox(
      width: 244,
      child: DecoratedBox(
        decoration: const BoxDecoration(
          color: AppTheme.surface,
          boxShadow: [
            BoxShadow(
              color: Color(0x99A3B1C6),
              blurRadius: 6,
              offset: Offset(3, 3),
              blurStyle: BlurStyle.inner,
            ),
            BoxShadow(
              color: Color(0x85FFFFFF),
              blurRadius: 6,
              offset: Offset(-3, -3),
              blurStyle: BlurStyle.inner,
            ),
          ],
        ),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(14, 18, 14, 18),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Padding(
                padding: EdgeInsets.symmetric(horizontal: 10),
                child: Text(
                  '学习中心',
                  style: TextStyle(
                    color: AppTheme.muted,
                    fontSize: 12,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 0,
                  ),
                ),
              ),
              const SizedBox(height: 14),
              ...items.map(
                (item) => Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: _NavButton(
                    item: item,
                    active: item.tab == _canonical(activeTab),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _MobileNav extends StatelessWidget {
  const _MobileNav({
    required this.activeTab,
    required this.courseId,
    required this.lessonId,
  });

  final KnowLinkTab activeTab;
  final String? courseId;
  final String? lessonId;

  @override
  Widget build(BuildContext context) {
    final items = _navItems(courseId: courseId, lessonId: lessonId);
    return SizedBox(
      height: 70,
      child: ListView.separated(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 14),
        scrollDirection: Axis.horizontal,
        itemCount: items.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (context, index) {
          final item = items[index];
          return _NavButton(
            item: item,
            active: item.tab == _canonical(activeTab),
            compact: true,
          );
        },
      ),
    );
  }
}

class _Content extends StatelessWidget {
  const _Content({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return ColoredBox(
      color: AppTheme.surface,
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: child,
      ),
    );
  }
}

class _Logo extends StatelessWidget {
  const _Logo();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 52,
      height: 52,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(18),
        boxShadow: AppTheme.raisedShadow,
      ),
      child: Container(
        width: 32,
        height: 32,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.circular(999),
          boxShadow: AppTheme.insetShadow,
        ),
        child: const Text(
          'K',
          style: TextStyle(
            color: AppTheme.accent,
            fontSize: 18,
            fontWeight: FontWeight.w800,
          ),
        ),
      ),
    );
  }
}

class _NavButton extends StatelessWidget {
  const _NavButton({
    required this.item,
    required this.active,
    this.compact = false,
  });

  final _NavItem item;
  final bool active;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final enabled = item.path != null;
    return HoverLift(
      enabled: enabled,
      child: Material(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(AppTheme.radiusControl),
        child: InkWell(
          onTap: enabled ? () => context.go(item.path!) : null,
          mouseCursor:
              enabled ? SystemMouseCursors.click : SystemMouseCursors.basic,
          borderRadius: BorderRadius.circular(AppTheme.radiusControl),
          child: Container(
            width: compact ? null : double.infinity,
            constraints: BoxConstraints(
              minWidth: compact ? 120 : 0,
              minHeight: 48,
            ),
            padding: const EdgeInsets.symmetric(horizontal: 14),
            decoration: BoxDecoration(
              color: AppTheme.surface,
              borderRadius: BorderRadius.circular(AppTheme.radiusControl),
              boxShadow: active ? AppTheme.smallShadow : const [],
            ),
            child: Row(
              mainAxisSize: compact ? MainAxisSize.min : MainAxisSize.max,
              children: [
                Icon(
                  item.icon,
                  color: active ? AppTheme.accent : AppTheme.muted,
                  size: 20,
                ),
                const SizedBox(width: 10),
                Flexible(
                  child: Text(
                    item.label,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: active ? AppTheme.text : AppTheme.muted,
                      fontWeight: FontWeight.w800,
                      fontSize: 14,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _NavItem {
  const _NavItem({
    required this.tab,
    required this.icon,
    required this.label,
    required this.path,
  });

  final KnowLinkTab tab;
  final IconData icon;
  final String label;
  final String? path;
}

List<_NavItem> _navItems({
  required String? courseId,
  required String? lessonId,
}) {
  final activeCourse = courseId ?? 'course-1';
  final activeLesson = lessonId ?? 'lesson-1';
  return [
    const _NavItem(
      tab: KnowLinkTab.home,
      icon: Icons.home_outlined,
      label: '学习总览',
      path: '/',
    ),
    const _NavItem(
      tab: KnowLinkTab.library,
      icon: Icons.library_books_outlined,
      label: '课程库',
      path: '/courses',
    ),
    _NavItem(
      tab: KnowLinkTab.workspace,
      icon: Icons.dashboard_customize_outlined,
      label: '课程工作区',
      path: '/courses/$activeCourse',
    ),
    _NavItem(
      tab: KnowLinkTab.lesson,
      icon: Icons.play_circle_outline,
      label: '课时学习',
      path: '/courses/$activeCourse/lessons/$activeLesson',
    ),
    _NavItem(
      tab: KnowLinkTab.test,
      icon: Icons.fact_check_outlined,
      label: '测试中心',
      path: '/courses/$activeCourse/test',
    ),
    _NavItem(
      tab: KnowLinkTab.chat,
      icon: Icons.forum_outlined,
      label: 'AI 问答',
      path: '/courses/$activeCourse/chat',
    ),
    _NavItem(
      tab: KnowLinkTab.review,
      icon: Icons.auto_stories_outlined,
      label: '复习中心',
      path: '/courses/$activeCourse/review',
    ),
  ];
}

KnowLinkTab _canonical(KnowLinkTab tab) {
  return switch (tab) {
    KnowLinkTab.import => KnowLinkTab.library,
    KnowLinkTab.recommend => KnowLinkTab.home,
    KnowLinkTab.parse => KnowLinkTab.workspace,
    KnowLinkTab.inquiry => KnowLinkTab.chat,
    KnowLinkTab.handout => KnowLinkTab.lesson,
    KnowLinkTab.quiz => KnowLinkTab.test,
    _ => tab,
  };
}
