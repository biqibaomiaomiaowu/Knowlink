import 'package:flutter/material.dart';

import '../../core/widgets/app_scaffold.dart';

class QaPage extends StatelessWidget {
  const QaPage({
    required this.courseId,
    required this.sessionId,
    super.key,
  });

  final String courseId;
  final String sessionId;

  @override
  Widget build(BuildContext context) {
    return AppScaffold(
      title: '上下文问答',
      body: Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Text(
            '课程 $courseId 的 QA 会话 $sessionId 会在这里展示，可在此接入块级追问、引用展示和复习卡片生成。',
          ),
        ),
      ),
    );
  }
}
