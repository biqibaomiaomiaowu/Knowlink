import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/widgets/app_scaffold.dart';

class HandoutPage extends StatelessWidget {
  const HandoutPage({
    required this.courseId,
    super.key,
  });

  final String courseId;

  @override
  Widget build(BuildContext context) {
    return AppScaffold(
      title: '个性化互动讲义',
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Text('课程 $courseId 的视频区、讲义块和 QA 面板会在这里联动。'),
            ),
          ),
          const SizedBox(height: 12),
          FilledButton(
            onPressed: () => context.go('/courses/$courseId/qa/6001'),
            child: const Text('进入独立 QA 页面'),
          ),
        ],
      ),
    );
  }
}
