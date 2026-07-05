import 'package:flutter/material.dart';

import '../../core/widgets/app_scaffold.dart';

class LessonStudyPage extends StatelessWidget {
  const LessonStudyPage({
    required this.courseId,
    required this.lessonId,
    super.key,
  });

  final String courseId;
  final String lessonId;

  @override
  Widget build(BuildContext context) {
    return AppScaffold(
      title: '课时学习',
      activeTab: KnowLinkTab.handout,
      courseId: courseId,
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              '课时学习',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 8),
            Text('课程 $courseId · 课时 $lessonId'),
          ],
        ),
      ),
    );
  }
}
