import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/theme/app_theme.dart';
import '../../shared/providers/course_flow_providers.dart';

enum KnowLinkTab {
  home,
  library,
  import,
  recommend,
  parse,
  inquiry,
  handout,
  quiz,
  review,
}

class AppScaffold extends ConsumerWidget {
  const AppScaffold({
    required this.title,
    required this.body,
    this.subtitle,
    this.activeTab,
    this.courseId,
    this.quizId,
    super.key,
  });

  final String title;
  final String? subtitle;
  final Widget body;
  final KnowLinkTab? activeTab;
  final String? courseId;
  final String? quizId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final tab = activeTab ?? _tabFromTitle(title);
    final flow = ref.watch(courseFlowProvider);
    final activeLesson = ref.watch(activeLessonProvider);
    final currentCourseId = courseId ?? flow.courseId;
    final items = _buildNavItems(
      courseId: currentCourseId,
      activeLesson: activeLesson,
      quizId: quizId,
    );
    return Scaffold(
      backgroundColor: AppTheme.page,
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) {
            final desktop = constraints.maxWidth > 1020;
            return Padding(
              padding: const EdgeInsets.all(24),
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(
                    maxWidth: 1520,
                    minHeight: 880,
                  ),
                  child: DecoratedBox(
                    decoration: BoxDecoration(
                      color: AppTheme.surface,
                      borderRadius: BorderRadius.circular(
                        constraints.maxWidth <= 1020 ? 28 : 36,
                      ),
                      boxShadow: AppTheme.shadowRaised,
                    ),
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(
                        constraints.maxWidth <= 1020 ? 28 : 36,
                      ),
                      child: Column(
                        children: [
                          const _KnowLinkTopBar(),
                          if (!desktop)
                            _KnowLinkMobileNav(
                              activeTab: tab,
                              items: items,
                            ),
                          Expanded(
                            child: desktop
                                ? Row(
                                    children: [
                                      _KnowLinkSidebar(
                                        activeTab: tab,
                                        items: items,
                                      ),
                                      Expanded(child: _ContentPane(body: body)),
                                    ],
                                  )
                                : _ContentPane(body: body),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            );
          },
        ),
      ),
    );
  }

  List<_NavItem> _buildNavItems({
    required String? courseId,
    required LessonResumeTarget? activeLesson,
    required String? quizId,
  }) {
    return _prototypeNavItems(
      courseId: courseId,
      activeLesson: activeLesson,
      quizId: quizId,
    );
  }

  /*
    final currentCourseId = courseId;
    final currentLesson = activeLesson;
    final lessonStudyPath = currentCourseId != null &&
            currentLesson != null &&
            currentLesson.courseId == currentCourseId
        ? '/courses/$currentCourseId/lessons/${currentLesson.lessonId}/handout'
        : '/courses';
    final quizPath = quizId == null
        ? currentCourseId == null
            ? '/courses'
            : '/courses/$currentCourseId/quiz'
        : '/quizzes/$quizId';
    return [
      const _NavItem(
        KnowLinkTab.home,
        Icons.home_outlined,
        '瀛︿範鎬昏',
        '/',
      ),
      const _NavItem(
        KnowLinkTab.library,
        Icons.library_books_outlined,
        '璇剧▼搴?,
        '/courses',
      ),
      _NavItem(
        KnowLinkTab.handout,
        Icons.menu_book_outlined,
        '璇炬椂瀛︿範',
        lessonStudyPath,
      ),
      _NavItem(
        KnowLinkTab.quiz,
        Icons.check_box_outlined,
        '娴嬭瘯涓績',
        quizPath,
      ),
      _NavItem(
        KnowLinkTab.inquiry,
        Icons.forum_outlined,
        'AI 闂瓟',
        currentCourseId == null ? '/courses' : '/courses/$currentCourseId/qa',
      ),
      _NavItem(
        KnowLinkTab.review,
        Icons.calendar_today_outlined,
        '澶嶄範涓績',
        currentCourseId == null
            ? '/courses'
            : '/courses/$currentCourseId/review',
      ),
    ];
  }
  */

  List<_NavItem> _prototypeNavItems({
    required String? courseId,
    required LessonResumeTarget? activeLesson,
    required String? quizId,
  }) {
    final currentCourseId = courseId;
    final currentLesson = activeLesson;
    final lessonStudyPath = currentCourseId != null &&
            currentLesson != null &&
            currentLesson.courseId == currentCourseId
        ? '/courses/$currentCourseId/lessons/${currentLesson.lessonId}/handout'
        : '/courses';
    final quizPath = quizId == null
        ? currentCourseId == null
            ? '/courses'
            : '/courses/$currentCourseId/quiz'
        : '/quizzes/$quizId';
    return [
      const _NavItem(
        KnowLinkTab.home,
        Icons.home_outlined,
        '学习总览',
        '/',
      ),
      const _NavItem(
        KnowLinkTab.library,
        Icons.library_books_outlined,
        '课程库',
        '/courses',
      ),
      _NavItem(
        KnowLinkTab.handout,
        Icons.menu_book_outlined,
        '课时学习',
        lessonStudyPath,
      ),
      _NavItem(
        KnowLinkTab.quiz,
        Icons.check_box_outlined,
        '测试中心',
        quizPath,
      ),
      _NavItem(
        KnowLinkTab.inquiry,
        Icons.forum_outlined,
        'AI 问答',
        currentCourseId == null ? '/courses' : '/courses/$currentCourseId/qa',
      ),
      _NavItem(
        KnowLinkTab.review,
        Icons.calendar_today_outlined,
        '复习中心',
        currentCourseId == null
            ? '/courses'
            : '/courses/$currentCourseId/review',
      ),
    ];
  }

  KnowLinkTab _tabFromTitle(String title) {
    if (title.contains('课程库')) {
      return KnowLinkTab.library;
    }
    if (title.contains('导入')) {
      return KnowLinkTab.import;
    }
    if (title.contains('推荐') && !title.contains('复习')) {
      return KnowLinkTab.recommend;
    }
    if (title.contains('解析')) {
      return KnowLinkTab.parse;
    }
    if (title.contains('问询') || title.contains('问答')) {
      return KnowLinkTab.inquiry;
    }
    if (title.contains('课时学习') || title.contains('讲义')) {
      return KnowLinkTab.handout;
    }
    if (title.contains('测试') || title.contains('测验')) {
      return KnowLinkTab.quiz;
    }
    if (title.contains('复习')) {
      return KnowLinkTab.review;
    }
    return KnowLinkTab.home;
  }
}

class _ContentPane extends StatelessWidget {
  const _ContentPane({required this.body});

  final Widget body;

  @override
  Widget build(BuildContext context) {
    return ColoredBox(
      color: AppTheme.surface,
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: body,
      ),
    );
  }
}

class _KnowLinkMobileNav extends StatelessWidget {
  const _KnowLinkMobileNav({
    required this.activeTab,
    required this.items,
  });

  final KnowLinkTab activeTab;
  final List<_NavItem> items;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 72,
      decoration: const BoxDecoration(
        color: AppTheme.surface,
        boxShadow: AppTheme.shadowInsetLook,
      ),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
        child: Row(
          children: [
            for (final item in items) ...[
              _PrototypeNavButton(
                item: item,
                isActive: item.tab == activeTab,
                horizontal: true,
              ),
              const SizedBox(width: 8),
            ],
          ],
        ),
      ),
    );
  }
}

class _KnowLinkSidebar extends StatelessWidget {
  const _KnowLinkSidebar({
    required this.activeTab,
    required this.items,
  });

  final KnowLinkTab activeTab;
  final List<_NavItem> items;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 244,
      padding: const EdgeInsets.fromLTRB(14, 18, 14, 18),
      decoration: const BoxDecoration(
        color: AppTheme.surface,
        boxShadow: AppTheme.shadowInsetLook,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 10),
            child: Text(
              'LEARNING CENTER',
              style: TextStyle(
                color: AppTheme.muted,
                fontSize: 12,
                fontWeight: FontWeight.w800,
                letterSpacing: 1.1,
              ),
            ),
          ),
          const SizedBox(height: 16),
          for (final item in items) ...[
            _PrototypeNavButton(
              item: item,
              isActive: item.tab == activeTab,
              horizontal: false,
            ),
            const SizedBox(height: 16),
          ],
        ],
      ),
    );
  }
}

class _PrototypeNavButton extends StatelessWidget {
  const _PrototypeNavButton({
    required this.item,
    required this.isActive,
    required this.horizontal,
  });

  final _NavItem item;
  final bool isActive;
  final bool horizontal;

  @override
  Widget build(BuildContext context) {
    final enabled = item.path != null;
    final color = isActive
        ? AppTheme.ink
        : enabled
            ? AppTheme.muted
            : AppTheme.subtle;
    return SizedBox(
      width: horizontal ? 116 : null,
      height: 48,
      child: Material(
        color: Colors.transparent,
        borderRadius: BorderRadius.circular(16),
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: enabled ? () => _goToPath(context, item.path!) : null,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 220),
            curve: Curves.easeOut,
            padding: const EdgeInsets.symmetric(horizontal: 14),
            decoration: BoxDecoration(
              color: AppTheme.surface,
              borderRadius: BorderRadius.circular(16),
              boxShadow: isActive ? AppTheme.shadowSmall : null,
            ),
            child: Row(
              mainAxisAlignment:
                  horizontal ? MainAxisAlignment.center : MainAxisAlignment.start,
              children: [
                Icon(
                  item.icon,
                  color: isActive ? AppTheme.brandBlue : color,
                  size: 20,
                ),
                const SizedBox(width: 12),
                Flexible(
                  child: Text(
                    item.label,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: color,
                      fontSize: 14,
                      fontWeight: FontWeight.w700,
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

void _goToPath(BuildContext context, String path) {
  try {
    GoRouter.of(context).go(path);
  } catch (_) {
    // Widget tests can mount pages without a router.
  }
}

class _KnowLinkTopBar extends StatelessWidget {
  const _KnowLinkTopBar();

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 78,
      decoration: const BoxDecoration(
        color: AppTheme.surface,
        boxShadow: AppTheme.shadowInsetLook,
      ),
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final compact = constraints.maxWidth < 560;
          final logoSize = compact ? 44.0 : 52.0;

          return Row(
            children: [
              _LogoMark(size: logoSize),
              const SizedBox(width: 18),
              Flexible(
                fit: FlexFit.loose,
                child: Text(
                  'KnowLink',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: AppTheme.ink,
                    fontSize: compact ? 22 : 30,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 0,
                  ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _LogoMark extends StatelessWidget {
  const _LogoMark({this.size = 48});

  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(18),
        boxShadow: AppTheme.shadowRaised,
      ),
      child: Stack(
        alignment: Alignment.center,
        children: [
          const Positioned.fill(
            child: Padding(
              padding: EdgeInsets.all(10),
              child: DecoratedBox(
                decoration: BoxDecoration(
                  color: AppTheme.surface,
                  shape: BoxShape.circle,
                  boxShadow: AppTheme.shadowInsetLook,
                ),
              ),
            ),
          ),
          Text(
            'K',
            style: TextStyle(
              color: AppTheme.brandBlue,
              fontSize: size * 0.42,
              fontWeight: FontWeight.w800,
            ),
          ),
        ],
      ),
    );
  }
}

// ignore: unused_element
class _KnowLinkBottomNav extends StatelessWidget {
  const _KnowLinkBottomNav({
    required this.activeTab,
    required this.courseId,
    required this.activeLesson,
    required this.quizId,
  });

  static const double _itemWidth = 166;
  static const double _navWidth = _itemWidth * 6;

  final KnowLinkTab activeTab;
  final String? courseId;
  final LessonResumeTarget? activeLesson;
  final String? quizId;

  @override
  Widget build(BuildContext context) {
    final currentCourseId = courseId;
    final currentLesson = activeLesson;
    final lessonStudyPath = currentCourseId != null &&
            currentLesson != null &&
            currentLesson.courseId == currentCourseId
        ? '/courses/$currentCourseId/lessons/${currentLesson.lessonId}/handout'
        : '/courses';
    final quizPath = quizId == null
        ? currentCourseId == null
            ? '/courses'
            : '/courses/$currentCourseId/quiz'
        : '/quizzes/$quizId';
    final items = [
      const _NavItem(
        KnowLinkTab.home,
        Icons.home_outlined,
        '学习总览',
        '/',
      ),
      const _NavItem(
        KnowLinkTab.library,
        Icons.library_books_outlined,
        '课程库',
        '/courses',
      ),
      _NavItem(
        KnowLinkTab.handout,
        Icons.menu_book_outlined,
        '课时学习',
        lessonStudyPath,
      ),
      _NavItem(
        KnowLinkTab.quiz,
        Icons.check_box_outlined,
        '测试中心',
        quizPath,
      ),
      _NavItem(
        KnowLinkTab.inquiry,
        Icons.forum_outlined,
        'AI 问答',
        currentCourseId == null ? '/courses' : '/courses/$currentCourseId/qa',
      ),
      _NavItem(
        KnowLinkTab.review,
        Icons.calendar_today_outlined,
        '复习中心',
        currentCourseId == null
            ? '/courses'
            : '/courses/$currentCourseId/review',
      ),
    ];

    return Container(
      height: 86,
      decoration: const BoxDecoration(
        color: Colors.white,
        border: Border(top: BorderSide(color: AppTheme.line)),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 10),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final nav = Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: items
                .map(
                  (item) => _BottomNavButton(
                    item: item,
                    isActive: item.tab == activeTab,
                    onTap: item.path == null
                        ? null
                        : () => _go(context, item.path!),
                  ),
                )
                .toList(),
          );
          if (constraints.maxWidth >= _navWidth) {
            return nav;
          }
          return SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: SizedBox(width: _navWidth, child: nav),
          );
        },
      ),
    );
  }

  void _go(BuildContext context, String path) {
    try {
      GoRouter.of(context).go(path);
    } catch (_) {
      // Widget tests can mount pages without a router.
    }
  }
}

class _NavItem {
  const _NavItem(this.tab, this.icon, this.label, this.path);

  final KnowLinkTab tab;
  final IconData icon;
  final String label;
  final String? path;
}

class _BottomNavButton extends StatelessWidget {
  const _BottomNavButton({
    required this.item,
    required this.isActive,
    required this.onTap,
  });

  final _NavItem item;
  final bool isActive;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final isEnabled = onTap != null;
    final color = isActive
        ? AppTheme.brandBlue
        : isEnabled
            ? AppTheme.muted
            : const Color(0xFFCBD5E1);
    return SizedBox(
      width: 166,
      height: 66,
      child: Material(
        color: isActive ? const Color(0xFFEFF6FF) : Colors.transparent,
        borderRadius: BorderRadius.circular(18),
        child: InkWell(
          borderRadius: BorderRadius.circular(18),
          onTap: onTap,
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(item.icon, color: color, size: 24),
              const SizedBox(height: 4),
              Text(
                item.label,
                style: TextStyle(
                  color: color,
                  fontWeight: FontWeight.w800,
                  fontSize: 15,
                  letterSpacing: 0,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
