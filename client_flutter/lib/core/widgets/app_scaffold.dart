import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/theme/app_theme.dart';

enum KnowLinkTab {
  home,
  import,
  recommend,
  parse,
  inquiry,
  handout,
  quiz,
  review,
}

class AppScaffold extends StatelessWidget {
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
  Widget build(BuildContext context) {
    final tab = activeTab ?? _tabFromTitle(title);
    return Scaffold(
      backgroundColor: AppTheme.page,
      body: SafeArea(
        child: Column(
          children: [
            const _KnowLinkTopBar(),
            Expanded(
              child: ColoredBox(
                color: AppTheme.page,
                child: Center(
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 1448),
                    child: Padding(
                      padding: const EdgeInsets.fromLTRB(24, 20, 24, 16),
                      child: body,
                    ),
                  ),
                ),
              ),
            ),
            _KnowLinkBottomNav(
              activeTab: tab,
              courseId: courseId,
              quizId: quizId,
            ),
          ],
        ),
      ),
    );
  }

  KnowLinkTab _tabFromTitle(String title) {
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
    if (title.contains('讲义')) {
      return KnowLinkTab.handout;
    }
    if (title.contains('测验')) {
      return KnowLinkTab.quiz;
    }
    if (title.contains('复习')) {
      return KnowLinkTab.review;
    }
    return KnowLinkTab.home;
  }
}

class _KnowLinkTopBar extends StatelessWidget {
  const _KnowLinkTopBar();

  static const double _wideSearchWidth = 460;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 78,
      decoration: const BoxDecoration(
        color: Colors.white,
        border: Border(bottom: BorderSide(color: AppTheme.line)),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final compact = constraints.maxWidth < 560;
          final showSearch = constraints.maxWidth >= 760;
          final logoSize = compact ? 40.0 : 48.0;

          return Row(
            children: [
              _LogoMark(size: logoSize),
              const SizedBox(width: 12),
              Flexible(
                fit: FlexFit.loose,
                child: Text(
                  'KnowLink',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: AppTheme.ink,
                    fontSize: compact ? 22 : 28,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 0,
                  ),
                ),
              ),
              const Spacer(),
              if (showSearch) ...[
                Flexible(
                  flex: 2,
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(
                      maxWidth: _wideSearchWidth,
                    ),
                    child: const _SearchBox(),
                  ),
                ),
                const SizedBox(width: 24),
              ] else
                const _CompactSearchButton(),
              const _NotificationButton(),
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
      alignment: Alignment.center,
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF60A5FA), AppTheme.brandBlueDark],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(8),
        boxShadow: const [
          BoxShadow(
            color: Color(0x332563EB),
            blurRadius: 14,
            offset: Offset(0, 6),
          ),
        ],
      ),
      child: Text(
        'K',
        style: TextStyle(
          color: Colors.white,
          fontSize: size * 0.58,
          fontWeight: FontWeight.w800,
        ),
      ),
    );
  }
}

class _SearchBox extends StatelessWidget {
  const _SearchBox();

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 52,
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color(0xFFCBD5E1)),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 18),
      child: const Row(
        children: [
          Icon(Icons.search, color: AppTheme.muted),
          SizedBox(width: 12),
          Expanded(
            child: Text(
              '搜索课程、知识点或学习资料',
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                color: Color(0xFF94A3B8),
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _CompactSearchButton extends StatelessWidget {
  const _CompactSearchButton();

  @override
  Widget build(BuildContext context) {
    return IconButton(
      tooltip: '搜索',
      onPressed: () {},
      icon: const Icon(Icons.search, color: AppTheme.muted, size: 28),
    );
  }
}

class _NotificationButton extends StatelessWidget {
  const _NotificationButton();

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 38,
      height: 42,
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          Positioned.fill(
            child: IconButton(
              tooltip: '通知',
              onPressed: () {},
              icon: const Icon(
                Icons.notifications_none,
                color: AppTheme.ink,
                size: 30,
              ),
            ),
          ),
          Positioned(
            right: -1,
            top: 1,
            child: Container(
              width: 18,
              height: 18,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: const Color(0xFFEF4444),
                borderRadius: BorderRadius.circular(9),
                border: Border.all(color: Colors.white, width: 2),
              ),
              child: const Text(
                '3',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 10,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _KnowLinkBottomNav extends StatelessWidget {
  const _KnowLinkBottomNav({
    required this.activeTab,
    required this.courseId,
    required this.quizId,
  });

  static const double _itemWidth = 166;
  static const double _navWidth = _itemWidth * 8;

  final KnowLinkTab activeTab;
  final String? courseId;
  final String? quizId;

  @override
  Widget build(BuildContext context) {
    final currentCourseId = courseId;
    final items = [
      const _NavItem(KnowLinkTab.home, Icons.home_outlined, '首页', '/'),
      const _NavItem(
        KnowLinkTab.import,
        Icons.file_upload_outlined,
        '导入',
        '/import',
      ),
      const _NavItem(
        KnowLinkTab.recommend,
        Icons.auto_awesome_outlined,
        '推荐',
        '/recommend',
      ),
      _NavItem(
        KnowLinkTab.parse,
        Icons.bar_chart_outlined,
        '解析',
        currentCourseId == null ? null : '/courses/$currentCourseId/progress',
      ),
      _NavItem(
        KnowLinkTab.inquiry,
        Icons.forum_outlined,
        '问询',
        currentCourseId == null ? null : '/courses/$currentCourseId/inquiry',
      ),
      _NavItem(
        KnowLinkTab.handout,
        Icons.menu_book_outlined,
        '讲义',
        currentCourseId == null ? null : '/courses/$currentCourseId/handout',
      ),
      _NavItem(
        KnowLinkTab.quiz,
        Icons.check_box_outlined,
        '测验',
        quizId == null ? null : '/quizzes/$quizId',
      ),
      _NavItem(
        KnowLinkTab.review,
        Icons.calendar_today_outlined,
        '复习',
        currentCourseId == null ? null : '/courses/$currentCourseId/review',
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
