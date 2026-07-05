import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/app/theme/app_theme.dart';
import 'package:knowlink_client/core/widgets/app_scaffold.dart';
import 'package:knowlink_client/core/widgets/knowlink_widgets.dart';

void main() {
  testWidgets('AppScaffold keeps the Soft UI frame contract', (tester) async {
    await tester.binding.setSurfaceSize(const Size(1600, 960));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(
          home: AppScaffold(
            title: '学习总览',
            body: SizedBox.shrink(),
          ),
        ),
      ),
    );

    final frame = tester.widget<ConstrainedBox>(
      find.byWidgetPredicate(
        (widget) =>
            widget is ConstrainedBox &&
            widget.constraints.maxWidth == 1520 &&
            widget.constraints.minHeight == 880,
      ),
    );
    expect(frame.constraints.maxWidth, 1520);
    expect(frame.constraints.minHeight, 880);
    expect(find.text('KnowLink'), findsOneWidget);
    expect(find.text('搜索'), findsNothing);
    expect(find.byIcon(Icons.notifications_none_outlined), findsNothing);
  });

  testWidgets('shared widgets match the Soft UI component metrics', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: AppTheme.light(),
        home: const Scaffold(
          body: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              PageTitle(
                title: '学习总览',
                subtitle: '保持 Soft UI 原型字号和间距',
                icon: Icons.home_outlined,
              ),
              SectionCard(
                child: Column(
                  children: [
                    StatusPill(label: '运行中'),
                    MetricBox(
                      icon: Icons.timeline_outlined,
                      label: 'TOTAL',
                      value: '42',
                    ),
                    ProgressRail(value: 0.42),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );

    expect(tester.getSize(find.byType(SoftIcon).first), const Size(46, 46));
    expect(tester.getSize(find.byType(StatusPill)).height, 30);
    expect(tester.getSize(find.byType(ProgressRail)).height, 12);
  });
}
