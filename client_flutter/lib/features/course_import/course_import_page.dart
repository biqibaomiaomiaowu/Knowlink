import 'package:flutter/material.dart';

import '../../core/widgets/app_scaffold.dart';

class CourseImportPage extends StatelessWidget {
  const CourseImportPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const AppScaffold(
      title: '自主导入',
      body: Card(
        child: Padding(
          padding: EdgeInsets.all(16),
          child: Text('这里接课程名称、MP4、PDF、PPTX、DOCX 的真实上传链路，SRT 作为可选辅助输入。'),
        ),
      ),
    );
  }
}
