import 'package:flutter/material.dart';

import '../../core/widgets/app_scaffold.dart';

class ParseProgressPage extends StatelessWidget {
  const ParseProgressPage({
    required this.courseId,
    super.key,
  });

  final String courseId;

  @override
  Widget build(BuildContext context) {
    return AppScaffold(
      title: '解析进度',
      body: Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Text(
            '课程 $courseId 的解析进度、来源整理、知识映射状态、重点提取摘要和下一步引导会显示在这里。',
          ),
        ),
      ),
    );
  }
}
