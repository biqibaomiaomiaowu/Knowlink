import 'package:flutter/material.dart';

import '../../app/theme/app_theme.dart';

class PageTitle extends StatelessWidget {
  const PageTitle({
    required this.title,
    this.subtitle,
    this.icon,
    this.actions,
    super.key,
  });

  final String title;
  final String? subtitle;
  final IconData? icon;
  final List<Widget>? actions;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 22),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final compact = constraints.maxWidth < 720;
          final titleBlock = Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (icon != null) ...[
                SoftIcon(icon: icon!, size: 46, inset: true),
                const SizedBox(width: 14),
              ],
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.displaySmall,
                    ),
                    if (subtitle != null) ...[
                      const SizedBox(height: 8),
                      Text(
                        subtitle!,
                        maxLines: 3,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          color: AppTheme.muted,
                          fontSize: 15,
                          fontWeight: FontWeight.w600,
                          height: 1.55,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ],
          );
          final actionRow = Wrap(
            spacing: 10,
            runSpacing: 10,
            alignment: WrapAlignment.end,
            children: actions ?? const [],
          );
          if (actions == null || actions!.isEmpty) {
            return titleBlock;
          }
          if (compact) {
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                titleBlock,
                const SizedBox(height: 14),
                actionRow,
              ],
            );
          }
          return Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(child: titleBlock),
              const SizedBox(width: 20),
              actionRow,
            ],
          );
        },
      ),
    );
  }
}

class SectionCard extends StatelessWidget {
  const SectionCard({
    required this.child,
    this.padding = const EdgeInsets.all(22),
    this.inset = false,
    this.onTap,
    super.key,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final bool inset;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final content = Container(
      width: double.infinity,
      padding: padding,
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(AppTheme.radiusCard),
        boxShadow: inset ? AppTheme.insetShadow : AppTheme.raisedShadow,
      ),
      child: child,
    );
    if (onTap == null) {
      return content;
    }
    return HoverLift(
      child: Material(
        color: Colors.transparent,
        borderRadius: BorderRadius.circular(AppTheme.radiusCard),
        child: InkWell(
          onTap: onTap,
          mouseCursor: SystemMouseCursors.click,
          borderRadius: BorderRadius.circular(AppTheme.radiusCard),
          child: content,
        ),
      ),
    );
  }
}

class HoverLift extends StatefulWidget {
  const HoverLift({
    required this.child,
    this.enabled = true,
    this.offset = -4,
    this.scale = 1.01,
    this.duration = const Duration(milliseconds: 170),
    this.curve = Curves.easeOutCubic,
    this.mouseCursor = SystemMouseCursors.click,
    super.key,
  });

  final Widget child;
  final bool enabled;
  final double offset;
  final double scale;
  final Duration duration;
  final Curve curve;
  final MouseCursor mouseCursor;

  @override
  State<HoverLift> createState() => _HoverLiftState();
}

class _HoverLiftState extends State<HoverLift> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    final active = widget.enabled && _hovered;
    return MouseRegion(
      cursor: widget.enabled ? widget.mouseCursor : MouseCursor.defer,
      onEnter: widget.enabled ? (_) => _setHovered(true) : null,
      onExit: widget.enabled ? (_) => _setHovered(false) : null,
      child: AnimatedScale(
        scale: active ? widget.scale : 1,
        duration: widget.duration,
        curve: widget.curve,
        child: AnimatedContainer(
          duration: widget.duration,
          curve: widget.curve,
          transform: Matrix4.translationValues(
            0,
            active ? widget.offset : 0,
            0,
          ),
          child: widget.child,
        ),
      ),
    );
  }

  void _setHovered(bool hovered) {
    if (_hovered == hovered) {
      return;
    }
    setState(() {
      _hovered = hovered;
    });
  }
}

class SoftButton extends StatelessWidget {
  const SoftButton({
    required this.label,
    required this.onPressed,
    this.icon,
    this.primary = false,
    super.key,
  });

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final bool primary;

  @override
  Widget build(BuildContext context) {
    return HoverLift(
      enabled: onPressed != null,
      child: Opacity(
        opacity: onPressed == null ? 0.55 : 1,
        child: Material(
          color: primary ? AppTheme.accent : AppTheme.surface,
          borderRadius: BorderRadius.circular(AppTheme.radiusControl),
          child: InkWell(
            onTap: onPressed,
            mouseCursor: onPressed == null
                ? SystemMouseCursors.basic
                : SystemMouseCursors.click,
            borderRadius: BorderRadius.circular(AppTheme.radiusControl),
            child: Container(
              constraints: const BoxConstraints(minHeight: 46),
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
              decoration: BoxDecoration(
                color: primary ? AppTheme.accent : AppTheme.surface,
                borderRadius: BorderRadius.circular(AppTheme.radiusControl),
                boxShadow: primary
                    ? const [
                        BoxShadow(
                          color: Color(0x476C63FF),
                          blurRadius: 16,
                          offset: Offset(8, 8),
                        ),
                        BoxShadow(
                          color: Color(0x6BFFFFFF),
                          blurRadius: 16,
                          offset: Offset(-7, -7),
                        ),
                      ]
                    : AppTheme.smallShadow,
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  if (icon != null) ...[
                    Icon(
                      icon,
                      size: 18,
                      color: primary ? Colors.white : AppTheme.text,
                    ),
                    const SizedBox(width: 8),
                  ],
                  Flexible(
                    child: Text(
                      label,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: primary ? Colors.white : AppTheme.text,
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
      ),
    );
  }
}

class GradientButton extends StatelessWidget {
  const GradientButton({
    required this.label,
    required this.onPressed,
    this.icon,
    super.key,
  });

  final String label;
  final IconData? icon;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return SoftButton(
      label: label,
      icon: icon,
      onPressed: onPressed,
      primary: true,
    );
  }
}

class SoftIcon extends StatelessWidget {
  const SoftIcon({
    required this.icon,
    this.color = AppTheme.accent,
    this.size = 44,
    this.inset = false,
    super.key,
  });

  final IconData icon;
  final Color color;
  final double size;
  final bool inset;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(AppTheme.radiusControl),
        boxShadow: inset ? AppTheme.insetShadow : AppTheme.raisedShadow,
      ),
      child: Icon(icon, color: color, size: size * 0.46),
    );
  }
}

class StatusPill extends StatelessWidget {
  const StatusPill({
    required this.label,
    this.color = AppTheme.accent,
    this.icon,
    super.key,
  });

  final String label;
  final Color color;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(maxWidth: 260, minHeight: 30),
      padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 7),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(999),
        boxShadow: AppTheme.insetShadow,
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, color: color, size: 15),
            const SizedBox(width: 6),
          ] else ...[
            Container(
              width: 8,
              height: 8,
              decoration: BoxDecoration(
                color: color,
                borderRadius: BorderRadius.circular(99),
                boxShadow: [
                  BoxShadow(
                    color: color.withValues(alpha: 0.16),
                    blurRadius: 0,
                    spreadRadius: 5,
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
          ],
          Flexible(
            child: Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: AppTheme.text,
                fontSize: 12,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class SourceChip extends StatelessWidget {
  const SourceChip({
    required this.icon,
    required this.label,
    this.color = AppTheme.accent,
    this.onTap,
    super.key,
  });

  final IconData icon;
  final String label;
  final Color color;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return SoftButton(
      label: label,
      icon: icon,
      onPressed: onTap ?? () {},
    );
  }
}

class ProgressRail extends StatelessWidget {
  const ProgressRail({
    required this.value,
    this.color = AppTheme.accent,
    super.key,
  });

  final double value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 12,
      padding: const EdgeInsets.all(3),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(999),
        boxShadow: AppTheme.insetShadow,
      ),
      child: FractionallySizedBox(
        alignment: Alignment.centerLeft,
        widthFactor: value.clamp(0, 1),
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(999),
          ),
        ),
      ),
    );
  }
}

class MetricBox extends StatelessWidget {
  const MetricBox({
    required this.icon,
    required this.label,
    required this.value,
    this.detail,
    this.color = AppTheme.accent,
    super.key,
  });

  final IconData icon;
  final String label;
  final String value;
  final String? detail;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return MetricCard(
      icon: icon,
      label: label,
      value: value,
      detail: detail,
      color: color,
    );
  }
}

class MetricCard extends StatelessWidget {
  const MetricCard({
    required this.icon,
    required this.label,
    required this.value,
    this.detail,
    this.color = AppTheme.accent,
    super.key,
  });

  final IconData icon;
  final String label;
  final String value;
  final String? detail;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minHeight: 104, minWidth: 190),
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(26),
        boxShadow: AppTheme.insetShadow,
      ),
      child: Row(
        children: [
          SoftIcon(icon: icon, color: color),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: AppTheme.muted,
                    fontSize: 12,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 0.8,
                  ),
                ),
                const SizedBox(height: 7),
                Text(
                  value,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: AppTheme.text,
                    fontSize: 30,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                if (detail != null) ...[
                  const SizedBox(height: 4),
                  Text(
                    detail!,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: AppTheme.muted,
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class MaterialRow extends StatelessWidget {
  const MaterialRow({
    required this.name,
    required this.type,
    required this.meta,
    this.citationEnabled = true,
    super.key,
  });

  final String name;
  final String type;
  final String meta;
  final bool citationEnabled;

  @override
  Widget build(BuildContext context) {
    final color = switch (type) {
      'PDF' => AppTheme.danger,
      'DOC' => AppTheme.success,
      'PPT' || 'MP4' => AppTheme.accent,
      _ => AppTheme.text,
    };
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(22),
        boxShadow: AppTheme.insetShadow,
      ),
      child: Row(
        children: [
          Container(
            width: 44,
            height: 44,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: AppTheme.surface,
              borderRadius: BorderRadius.circular(AppTheme.radiusControl),
              boxShadow: AppTheme.raisedShadow,
            ),
            child: Text(
              type,
              style: TextStyle(
                color: color,
                fontSize: 11,
                fontWeight: FontWeight.w900,
              ),
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  name,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: AppTheme.text,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  '$meta · ${citationEnabled ? '引用开启' : '引用关闭'}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: AppTheme.muted,
                    fontSize: 12,
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

class ChatBubble extends StatelessWidget {
  const ChatBubble({
    required this.role,
    required this.content,
    super.key,
  });

  final String role;
  final String content;

  @override
  Widget build(BuildContext context) {
    final isUser = role == 'user';
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        constraints: const BoxConstraints(maxWidth: 620),
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
        decoration: BoxDecoration(
          color: isUser ? AppTheme.accent : AppTheme.surface,
          borderRadius: BorderRadius.circular(20),
          boxShadow: isUser
              ? const [
                  BoxShadow(
                    color: Color(0x336C63FF),
                    blurRadius: 12,
                    offset: Offset(6, 6),
                  ),
                ]
              : AppTheme.smallShadow,
        ),
        child: Text(
          content,
          style: TextStyle(
            color: isUser ? Colors.white : AppTheme.text,
            fontWeight: FontWeight.w700,
            height: 1.45,
          ),
        ),
      ),
    );
  }
}

class QuestionCard extends StatelessWidget {
  const QuestionCard({
    required this.index,
    required this.title,
    required this.options,
    super.key,
  });

  final int index;
  final String title;
  final List<String> options;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(24),
        boxShadow: AppTheme.insetShadow,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '$index. $title',
            style: const TextStyle(
              color: AppTheme.text,
              fontSize: 17,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 12),
          ...options.map(
            (option) => Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppTheme.surface,
                  borderRadius: BorderRadius.circular(AppTheme.radiusControl),
                  boxShadow: AppTheme.smallShadow,
                ),
                child: Text(
                  option,
                  style: const TextStyle(
                    color: AppTheme.text,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class ReviewTaskCard extends StatelessWidget {
  const ReviewTaskCard({
    required this.priority,
    required this.title,
    required this.sourceLesson,
    required this.weakPoints,
    required this.estimatedMinutes,
    required this.reason,
    super.key,
  });

  final int priority;
  final String title;
  final String sourceLesson;
  final List<String> weakPoints;
  final int estimatedMinutes;
  final String reason;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(24),
        boxShadow: AppTheme.insetShadow,
      ),
      child: Row(
        children: [
          Container(
            width: 42,
            height: 42,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: AppTheme.surface,
              borderRadius: BorderRadius.circular(AppTheme.radiusControl),
              boxShadow: AppTheme.raisedShadow,
            ),
            child: Text(
              '$priority',
              style: const TextStyle(
                color: AppTheme.accent,
                fontWeight: FontWeight.w900,
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
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: AppTheme.text,
                    fontSize: 16,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  '$sourceLesson · ${weakPoints.join(' / ')} · $estimatedMinutes 分钟',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: AppTheme.muted,
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  reason,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: AppTheme.muted,
                    fontSize: 12,
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

class StepLabel extends StatelessWidget {
  const StepLabel({
    required this.number,
    required this.title,
    super.key,
  });

  final int number;
  final String title;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        StatusPill(label: '$number'),
        const SizedBox(width: 12),
        Expanded(
          child: Text(
            title,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.titleMedium,
          ),
        ),
      ],
    );
  }
}
