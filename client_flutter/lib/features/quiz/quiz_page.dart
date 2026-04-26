import 'package:flutter/material.dart';

import '../../core/widgets/app_scaffold.dart';

class QuizPage extends StatelessWidget {
  const QuizPage({
    required this.quizId,
    super.key,
  });

  final String quizId;

  @override
  Widget build(BuildContext context) {
    return AppScaffold(
      title: '测验',
      body: Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Text(
            '测验 $quizId 的题目、提交、掌握度变化和复习联动结果会显示在这里。',
          ),
        ),
      ),
    );
  }
}
