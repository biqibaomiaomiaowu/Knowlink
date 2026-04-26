import 'package:flutter/material.dart';

import '../../core/widgets/app_scaffold.dart';

class CourseImportPage extends StatelessWidget {
  const CourseImportPage({
    this.courseId,
    super.key,
  });

  final String? courseId;

  @override
  Widget build(BuildContext context) {
    return AppScaffold(
      title: '自主导入',
      body: Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                '这里承接课程名称、MP4、PDF、PPTX、DOCX 的真实上传链路，SRT 作为可选辅助输入。',
              ),
              if (courseId != null) ...[
                const SizedBox(height: 12),
                Text('当前课程：$courseId'),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
