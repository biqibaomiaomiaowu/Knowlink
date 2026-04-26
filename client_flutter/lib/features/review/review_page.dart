import 'package:flutter/material.dart';

import '../../core/widgets/app_scaffold.dart';

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
      body: Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Text(
            '课程 $courseId 的 Top3 复习任务、推荐回看片段、再练入口与复习顺序/强度会显示在这里。',
          ),
        ),
      ),
    );
  }
}
