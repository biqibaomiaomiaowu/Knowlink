import 'package:flutter/material.dart';

import '../../core/widgets/app_scaffold.dart';

class InquiryPage extends StatelessWidget {
  const InquiryPage({
    required this.courseId,
    super.key,
  });

  final String courseId;

  @override
  Widget build(BuildContext context) {
    return AppScaffold(
      title: 'AI 个性化问询',
      body: Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Text(
            '课程 $courseId 的问询题会覆盖学习目标、掌握程度、时间预算、讲义偏好和解释粒度，并在这里进入讲义生成。',
          ),
        ),
      ),
    );
  }
}
